"""Pluggable token persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from qtsurfer.api.client._generated.models import AuthTokenResponse


@runtime_checkable
class TokenStore(Protocol):
    """Pluggable token persistence strategy for :class:`AuthenticatedSession`.

    The SDK ships an :class:`InMemoryTokenStore` as the default. Adopters
    implement this Protocol (or subclass it) to back tokens by an on-disk
    file, a secret manager, etc. The SDK calls :meth:`load` once per
    session-startup to seed any previously cached token, :meth:`save`
    after every successful ``auth()`` / refresh, and :meth:`clear` when
    the session is explicitly invalidated.

    Implementations are expected to be thread-safe if used from multiple
    threads.
    """

    def load(self) -> AuthTokenResponse | None:
        """Return the persisted token, or :data:`None` if none."""

    def save(self, token: AuthTokenResponse) -> None:
        """Persist the token returned by ``POST /v1/auth/token``."""

    def clear(self) -> None:
        """Drop any persisted token."""


class InMemoryTokenStore:
    """Default :class:`TokenStore` — holds the most recent token in a
    single in-memory slot. Lost on process exit. Sufficient for
    short-lived scripts and for tests.
    """

    def __init__(self) -> None:
        self._token: AuthTokenResponse | None = None

    def load(self) -> AuthTokenResponse | None:
        return self._token

    def save(self, token: AuthTokenResponse) -> None:
        self._token = token

    def clear(self) -> None:
        self._token = None
