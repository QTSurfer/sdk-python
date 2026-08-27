"""``auth(apikey)`` helper and :class:`AuthenticatedSession`.

One-call setup: exchange a long-lived API key for a short-lived JWT,
returning a session that transparently refreshes the JWT on 401 and
lets callers plug in a custom :class:`TokenStore`.

Mirrors the surface of the Java and TypeScript SDKs so adopters get the
same ergonomics across languages.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import TypeVar

from qtsurfer.api.client._generated import AuthenticatedClient as _GenAuthClient
from qtsurfer.api.client._generated.api.auth.authenticate import (
    sync_detailed as _auth_sync_detailed,
)
from qtsurfer.api.client._generated.models import AuthTokenError, AuthTokenResponse
from qtsurfer.api.client._generated.types import Response

from qtsurfer_sdk._errors import QTSAuthError
from qtsurfer_sdk._tokens import InMemoryTokenStore, TokenStore

APIKEY_ENV_VAR = "QTSURFER_APIKEY"
DEFAULT_BASE_URL = "https://api.qtsurfer.com/v1"

T = TypeVar("T")


class AuthenticatedSession:
    """Authenticated SDK session.

    Returned by :func:`auth`. Owns a JWT (in memory by default, or in
    the provided :class:`TokenStore`), exposes the underlying
    ``qtsurfer-api-client`` ``AuthenticatedClient`` for typed API calls,
    and transparently re-exchanges the API key for a fresh JWT when a
    call returns 401.

    Refresh policy: one shot — refresh once, retry the wrapped call
    once, surface the error if the retry also 401s. No loops.

    Thread-safety: :meth:`refresh` is guarded by an internal lock so
    concurrent callers piggy-back on a single in-flight mint.

    The returned :attr:`client` is the *same* object whose ``token``
    attribute is mutated on refresh, so any in-flight code holding a
    reference to it continues to see the latest JWT.
    """

    def __init__(
        self,
        apikey: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        store: TokenStore | None = None,
    ) -> None:
        self._apikey = apikey
        self.base_url = base_url
        self.store: TokenStore = store if store is not None else InMemoryTokenStore()
        self._lock = threading.RLock()
        self._cached: AuthTokenResponse | None = None
        # The mint client carries the apikey in the X-API-Key header (the
        # generated client treats `token` as the value of `auth_header_name`,
        # with an empty prefix giving us a raw `X-API-Key: <apikey>` header).
        self._mint_client = _GenAuthClient(
            base_url=base_url,
            token=apikey,
            prefix="",
            auth_header_name="X-API-Key",
        )
        # The session client carries the JWT — populated on first auth.
        # Use an empty placeholder token until `ensure_token` runs; the
        # auth_header_name + prefix defaults give `Authorization: Bearer ...`.
        self.client = _GenAuthClient(base_url=base_url, token="")

    # ---- Token lifecycle ----

    @property
    def token(self) -> AuthTokenResponse | None:
        """Currently cached token, or ``None`` if no exchange has happened."""
        return self._cached

    def refresh(self) -> AuthTokenResponse:
        """Force a fresh JWT exchange. Bypasses the cache; writes the new
        token to :attr:`store` and updates :attr:`client` so subsequent
        calls carry the new Bearer header.
        """
        with self._lock:
            resp: Response[
                AuthTokenResponse | AuthTokenError | None
            ] = _auth_sync_detailed(client=self._mint_client)
            if resp.status_code != 200 or not isinstance(resp.parsed, AuthTokenResponse):
                raise QTSAuthError(
                    f"auth() failed: HTTP {resp.status_code}",
                    status=int(resp.status_code),
                )
            self._cached = resp.parsed
            self.store.save(resp.parsed)
            self._apply_bearer(resp.parsed.access_token)
            return resp.parsed

    def ensure_token(self) -> AuthTokenResponse:
        """Return the cached token, seeding from :attr:`store` on first
        use and minting a new one if neither cache nor store hold one.
        """
        if self._cached is not None:
            return self._cached
        stored = self.store.load()
        if stored is not None:
            self._cached = stored
            self._apply_bearer(stored.access_token)
            return stored
        return self.refresh()

    def clear(self) -> None:
        """Drop the cached token (in memory and in the store)."""
        with self._lock:
            self._cached = None
            self.store.clear()
            self._apply_bearer("")

    def _apply_bearer(self, token: str) -> None:
        """Update both the api-client's ``token`` attribute *and* the live
        httpx.Client's headers, so a refresh swaps the Bearer header even
        after the client has been used (the api-client builds the header
        lazily on first ``get_httpx_client()`` and caches the dict — without
        this, refresh would only land on a brand-new client).
        """
        self.client.token = token
        # Use the private accessor (no public one in the generated client).
        httpx_client = getattr(self.client, "_client", None)
        if httpx_client is not None:
            if token:
                httpx_client.headers["Authorization"] = f"Bearer {token}"
            else:
                httpx_client.headers.pop("Authorization", None)

    # ---- Refresh-on-401 plumbing ----

    def call(self, fn: Callable[[_GenAuthClient], T]) -> T:
        """Run ``fn(self.client)`` once, refresh-on-401 once on failure.

        ``fn`` receives the session's underlying ``AuthenticatedClient``
        (its ``token`` attribute is kept in sync on every refresh). If
        the call returns a ``Response`` whose ``status_code`` is 401, or
        raises an exception that surfaces a 401, the SDK refreshes the
        JWT once and re-invokes ``fn`` exactly once.

        A second 401 is surfaced to the caller as-is — no retry loops.
        """
        self.ensure_token()
        try:
            result = fn(self.client)
        except Exception as exc:
            if not _is_unauthorized(exc):
                raise
            self._cached = None
            self.refresh()
            return fn(self.client)
        if _result_is_unauthorized(result):
            self._cached = None
            self.refresh()
            return fn(self.client)
        return result

    # ---- High-level workflows (parity with sdk-java / sdk-ts) ----

    def exchanges(self):
        """List the exchanges the platform serves."""
        from qtsurfer_sdk import _workflows as wf
        return wf.exchanges(self)

    def instruments(self, exchange_id: str, segment: str | None = None):
        """List an exchange's instruments, optionally for a segment."""
        from qtsurfer_sdk import _workflows as wf
        return wf.instruments(self, exchange_id, segment)

    def compile_strategy(self, source: str):
        """Compile and register a Java strategy."""
        from qtsurfer_sdk import _workflows as wf
        return wf.compile_strategy(self, source)

    def validate_strategy(self, strategy_id: str):
        from qtsurfer_sdk import _workflows as wf
        return wf.validate_strategy(self, strategy_id)

    def strategy_state(self, strategy_id: str):
        from qtsurfer_sdk import _workflows as wf
        return wf.strategy_state(self, strategy_id)

    def list_strategies(self):
        from qtsurfer_sdk import _workflows as wf
        return wf.list_strategies(self)

    def delete_strategy(self, strategy_id: str):
        from qtsurfer_sdk import _workflows as wf
        return wf.delete_strategy(self, strategy_id)

    def get_strategy_code(self, strategy_id: str) -> str:
        from qtsurfer_sdk import _workflows as wf
        return wf.get_strategy_code(self, strategy_id)

    def prepare(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.prepare(self, **kwargs)

    def prepare_status(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.prepare_status(self, **kwargs)

    def execute(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.execute(self, **kwargs)

    def backtest_result(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.backtest_result(self, **kwargs)

    def cancel_backtest(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.cancel_backtest(self, **kwargs)

    def sweep(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.sweep(self, **kwargs)

    def sweep_result(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.sweep_result(self, **kwargs)

    def sweep_sensitivity(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.sweep_sensitivity(self, **kwargs)

    def sweep_run_equity_curve(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.sweep_run_equity_curve(self, **kwargs)

    def cancel_sweep(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.cancel_sweep(self, **kwargs)

    def create_dataset(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.create_dataset(self, **kwargs)

    def list_datasets(self):
        from qtsurfer_sdk import _workflows as wf
        return wf.list_datasets(self)

    def get_dataset(self, dataset_id: str):
        from qtsurfer_sdk import _workflows as wf
        return wf.get_dataset(self, dataset_id)

    def delete_dataset(self, dataset_id: str):
        from qtsurfer_sdk import _workflows as wf
        return wf.delete_dataset(self, dataset_id)

    def finalize_upload(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.finalize_upload(self, **kwargs)

    def dataset_upload(self, **kwargs):
        from qtsurfer_sdk import _workflows as wf
        return wf.dataset_upload(self, **kwargs)


def auth(
    apikey: str | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
    store: TokenStore | None = None,
) -> AuthenticatedSession:
    """Exchange a long-lived API key for an authenticated session.

    If ``apikey`` is ``None`` or empty, the SDK reads
    ``QTSURFER_APIKEY`` from the environment. The returned
    :class:`AuthenticatedSession` caches the JWT (in memory by default,
    or in the provided :class:`TokenStore`), exposes the underlying
    ``qtsurfer-api-client`` ``AuthenticatedClient`` via
    :attr:`AuthenticatedSession.client`, and transparently refreshes
    the JWT on 401 via :meth:`AuthenticatedSession.call`.

    :param apikey: Long-lived API key. When omitted, read from
        ``QTSURFER_APIKEY``.
    :param base_url: API base URL. Defaults to
        ``https://api.qtsurfer.com/v1``.
    :param store: Custom :class:`TokenStore`. Defaults to
        :class:`InMemoryTokenStore`.
    :raises QTSAuthError: when no apikey is available, or the initial JWT
        exchange fails.
    """
    resolved = _resolve_apikey(apikey)
    session = AuthenticatedSession(resolved, base_url=base_url, store=store)
    session.ensure_token()
    return session


def _resolve_apikey(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit
    env = os.environ.get(APIKEY_ENV_VAR)
    if env and env.strip():
        return env
    raise QTSAuthError(
        f"auth() requires an apikey (argument or {APIKEY_ENV_VAR} env var)"
    )


def _result_is_unauthorized(result: object) -> bool:
    """Detect a 401 across the response types callers commonly return.

    * The generated ``qtsurfer-api-client`` ``Response`` (``*_detailed``).
    * Raw ``httpx.Response`` (when callers reach into ``client.get_httpx_client()``).
    * Any other object exposing a numeric ``status_code`` attribute.
    """
    status = getattr(result, "status_code", None)
    return status == 401


def _is_unauthorized(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return True
    status = getattr(exc, "status", None)
    if status == 401:
        return True
    cause = exc.__cause__
    if cause is not None and getattr(cause, "status_code", None) == 401:
        return True
    return False
