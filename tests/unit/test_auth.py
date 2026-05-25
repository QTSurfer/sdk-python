"""Unit tests for the ``auth(apikey)`` helper.

Covers:
- explicit apikey vs ``QTSURFER_APIKEY`` env fallback
- explicit apikey overrides env
- missing apikey raises ``QTSAuthError``
- token store: ``save`` called on mint, ``load`` seeds without mint
- refresh-on-401 happy path (mock 401 -> refresh -> retry -> 200)
- refresh-on-401 failure path (mock 401 -> refresh -> 401 -> raise)
- non-401 errors are not retried
- ``clear()`` wipes cache + store + bearer token on the client
"""

from __future__ import annotations

import os

import pytest

from qtsurfer.api.client._generated.models import AuthTokenResponse
from qtsurfer_sdk import (
    APIKEY_ENV_VAR,
    AuthenticatedSession,
    InMemoryTokenStore,
    QTSAuthError,
    auth,
)
from qtsurfer_sdk._session import _resolve_apikey


# ---- Fixtures ----------------------------------------------------------------


def _jwt_payload(access: str = "jwt-1", tier: str = "free") -> dict:
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": 3600,
        "tier": tier,
    }


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(APIKEY_ENV_VAR, raising=False)


@pytest.fixture
def base_url() -> str:
    return "https://api.example.test/v1"


# ---- Apikey resolution -------------------------------------------------------


class TestApikeyResolution:
    def test_explicit_apikey_used(self, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "ak_env")
        assert _resolve_apikey("ak_arg") == "ak_arg"

    def test_env_var_used_when_no_arg(self, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "ak_env")
        assert _resolve_apikey(None) == "ak_env"

    def test_blank_arg_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "ak_env")
        assert _resolve_apikey("   ") == "ak_env"

    def test_raises_when_both_missing(self):
        assert APIKEY_ENV_VAR not in os.environ  # ensured by autouse fixture
        with pytest.raises(QTSAuthError) as ex:
            _resolve_apikey(None)
        assert APIKEY_ENV_VAR in str(ex.value)

    def test_raises_when_both_blank(self, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "  ")
        with pytest.raises(QTSAuthError):
            _resolve_apikey("")


# ---- auth() entry point ------------------------------------------------------


class TestAuthHelper:
    def test_mints_with_explicit_apikey(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-from-arg", "pro"),
        )
        session = auth("ak_explicit", base_url=base_url)

        assert session.token is not None
        assert session.token.access_token == "jwt-from-arg"
        # Apikey is in the X-API-Key header on the mint request.
        request = httpx_mock.get_request()
        assert request.headers["X-API-Key"] == "ak_explicit"

    def test_picks_up_apikey_from_env_when_no_arg(self, httpx_mock, base_url, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "ak_from_env")
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-env"),
        )
        session = auth(base_url=base_url)
        assert session.token.access_token == "jwt-env"
        request = httpx_mock.get_request()
        assert request.headers["X-API-Key"] == "ak_from_env"

    def test_explicit_arg_overrides_env(self, httpx_mock, base_url, monkeypatch):
        monkeypatch.setenv(APIKEY_ENV_VAR, "ak_env")
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload(),
        )
        auth("ak_arg", base_url=base_url)
        request = httpx_mock.get_request()
        assert request.headers["X-API-Key"] == "ak_arg"

    def test_raises_qts_auth_error_when_no_apikey(self):
        with pytest.raises(QTSAuthError):
            auth()

    def test_raises_qts_auth_error_on_mint_401(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            status_code=401,
            json={"code": "invalid_apikey", "message": "nope"},
        )
        with pytest.raises(QTSAuthError) as ex:
            auth("ak_bad", base_url=base_url)
        assert "401" in str(ex.value)


# ---- Token store -------------------------------------------------------------


class TestTokenStore:
    def test_save_called_on_mint(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-saved"),
        )
        saved: list[AuthTokenResponse] = []

        class RecordingStore:
            def load(self):
                return None

            def save(self, token):
                saved.append(token)

            def clear(self):
                saved.clear()

        auth("ak", base_url=base_url, store=RecordingStore())
        assert len(saved) == 1
        assert saved[0].access_token == "jwt-saved"

    def test_load_seeds_without_minting(self, base_url, httpx_mock):
        cached = AuthTokenResponse.from_dict(_jwt_payload("jwt-cached", "elite"))

        class CachedStore:
            def load(self):
                return cached

            def save(self, token):
                pass

            def clear(self):
                pass

        # No mocked response; if SDK tries to mint, httpx_mock will fail.
        session = auth("ak", base_url=base_url, store=CachedStore())
        assert session.token is cached
        assert session.client.token == "jwt-cached"

    def test_clear_wipes_session_and_store(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-c"),
        )
        store = InMemoryTokenStore()
        session = auth("ak", base_url=base_url, store=store)
        assert store.load() is not None

        session.clear()
        assert store.load() is None
        assert session.token is None
        assert session.client.token == ""


# ---- Refresh on 401 ----------------------------------------------------------


class TestRefreshOn401:
    def _setup_two_mints(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-1"),
        )
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-2"),
        )

    def test_401_then_200_refreshes_and_retries(self, httpx_mock, base_url):
        self._setup_two_mints(httpx_mock, base_url)
        # First exchanges call: 401; second: 200.
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            status_code=401,
            json={"error": "expired"},
        )
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            json=[{"id": "binance", "name": "Binance"}],
        )

        session = auth("ak", base_url=base_url)

        def call_exchanges(client):
            return client.get_httpx_client().get("/exchanges")

        resp = session.call(call_exchanges)
        assert resp.status_code == 200

        # Two mints (initial + refresh on 401).
        mint_requests = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/auth/token")]
        assert len(mint_requests) == 2

        # Second exchanges request carries the refreshed bearer.
        exchanges_requests = [
            r for r in httpx_mock.get_requests() if r.url.path.endswith("/exchanges")
        ]
        assert len(exchanges_requests) == 2
        assert exchanges_requests[-1].headers["Authorization"] == "Bearer jwt-2"

    def test_401_then_401_surfaces_failure(self, httpx_mock, base_url):
        self._setup_two_mints(httpx_mock, base_url)
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            status_code=401,
            json={"error": "expired"},
        )
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            status_code=401,
            json={"error": "still expired"},
        )

        session = auth("ak", base_url=base_url)

        def call_exchanges(client):
            return client.get_httpx_client().get("/exchanges")

        resp = session.call(call_exchanges)
        # Second 401 surfaces as-is (no third attempt).
        assert resp.status_code == 401

        mint_requests = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/auth/token")]
        exchanges_requests = [
            r for r in httpx_mock.get_requests() if r.url.path.endswith("/exchanges")
        ]
        assert len(mint_requests) == 2
        assert len(exchanges_requests) == 2

    def test_non_401_errors_are_not_retried(self, httpx_mock, base_url):
        httpx_mock.add_response(
            url=f"{base_url}/auth/token",
            method="POST",
            json=_jwt_payload("jwt-1"),
        )
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            status_code=404,
            json={"error": "gone"},
        )

        session = auth("ak", base_url=base_url)
        resp = session.call(lambda c: c.get_httpx_client().get("/exchanges"))
        assert resp.status_code == 404

        mint_requests = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/auth/token")]
        exchanges_requests = [
            r for r in httpx_mock.get_requests() if r.url.path.endswith("/exchanges")
        ]
        # Only the initial mint and a single call.
        assert len(mint_requests) == 1
        assert len(exchanges_requests) == 1

    def test_401_via_raised_exception_is_caught(self, httpx_mock, base_url):
        """If the wrapped fn raises with a status_code=401 attribute,
        the wrapper still refreshes + retries.
        """
        self._setup_two_mints(httpx_mock, base_url)
        httpx_mock.add_response(
            url=f"{base_url}/exchanges",
            method="GET",
            json=[{"id": "binance", "name": "Binance"}],
        )

        session = auth("ak", base_url=base_url)

        calls = {"n": 0}

        class FakeUnauthorized(Exception):
            status_code = 401

        def fn(client):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FakeUnauthorized("token expired")
            return client.get_httpx_client().get("/exchanges")

        resp = session.call(fn)
        assert resp.status_code == 200
        assert calls["n"] == 2

        mint_requests = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/auth/token")]
        assert len(mint_requests) == 2
