"""Scopes survive persistence and discovery keeps typed venue envelopes."""

import json

import pytest
from qtsurfer.api.client.models import AuthTokenResponse, KeyScopes, PoolListResponse

from qtsurfer_sdk import AuthenticatedSession, QTSError, auth

BASE = "https://api.example/v1"
SCOPES = {"backtests": ["read", "write", "execute"], "exchanges": ["read"]}


@pytest.mark.parametrize("scopes", [SCOPES, {}, []])
def test_token_store_roundtrip_preserves_scopes_and_session_metadata(httpx_mock, scopes):
    payload = {
        "access_token": "jwt",
        "token_type": "Bearer",
        "expires_in": 3600,
        "tier": "pro",
        "scopes": scopes,
    }
    if isinstance(scopes, dict):
        httpx_mock.add_response(url=BASE + "/auth/token", json=payload)

    class JsonStore:
        data = json.dumps(payload) if isinstance(scopes, list) else None

        def load(self):
            return AuthTokenResponse.from_dict(json.loads(self.data)) if self.data else None

        def save(self, token):
            self.data = json.dumps(token.to_dict())

        def clear(self):
            self.data = None

    store = JsonStore()
    session = auth("ak", base_url=BASE, store=store)
    restarted = AuthenticatedSession("ak", base_url=BASE, store=store)
    token = restarted.ensure_token()
    assert token.tier == session.token.tier
    assert token.access_token == restarted.client.token == "jwt"
    assert isinstance(token.scopes, KeyScopes)
    assert token.scopes.to_dict() == (SCOPES if scopes else {})
    store.save(token)
    assert json.loads(store.data)["scopes"] == (SCOPES if scopes else {})


def test_scope_map_from_get_account_and_discovery(httpx_mock):
    httpx_mock.add_response(
        url=BASE + "/auth/token",
        json={
            "access_token": "jwt",
            "token_type": "Bearer",
            "expires_in": 3600,
            "tier": "pro",
            "scopes": SCOPES,
        },
    )
    httpx_mock.add_response(
        url=BASE + "/account",
        json={
            "userId": "user",
            "tier": "pro",
            "scopes": SCOPES,
            "maxExecute": 1,
            "maxRangeDays": 7,
            "maxSweepCartesian": 10,
            "maxImportRangeHours": 24,
            "maxDatasets": 10,
            "maxDatasetBytes": 1000,
            "maxTotalStorageBytes": 2000,
            "_links": {"self": {"href": "/v1/account"}, "usage": {"href": "/v1/account/usage"}},
        },
    )
    httpx_mock.add_response(
        url=BASE + "/exchange/robinhood/uniswap-v3/instruments",
        json={
            "data": [],
            "meta": {
                "exchange": "robinhood",
                "segment": "uniswap-v3",
                "venueType": "dex",
                "updatedAt": "2026-10-17T10:00:00Z",
                "minTvlUsd": 10000,
                "limit": 50,
            },
            "_links": {"self": {"href": "/v1/exchange/robinhood/uniswap-v3/instruments"}},
        },
    )
    session = auth("ak", base_url=BASE)
    assert session.get_account().scopes.to_dict() == SCOPES
    assert isinstance(session.list_instruments("robinhood", "uniswap-v3"), PoolListResponse)


def test_workflow_error_preserves_reason_next_and_retry_after(httpx_mock):
    httpx_mock.add_response(
        url=BASE + "/auth/token",
        json={"access_token": "jwt", "token_type": "Bearer", "expires_in": 3600, "tier": "pro"},
    )
    httpx_mock.add_response(
        url=BASE + "/exchange/binance/instruments",
        status_code=400,
        json={
            "code": 400,
            "message": "Use import",
            "reason": "OUTSIDE_WINDOW",
            "next": {"method": "POST", "path": "/datasets/imports", "body": {"type": "cex"}},
        },
        headers={"Retry-After": "30"},
    )
    session = auth("ak", base_url=BASE)
    with pytest.raises(QTSError) as result:
        session.list_instruments("binance")
    error = result.value
    assert error.reason == "OUTSIDE_WINDOW"
    assert error.next_call.path == "/datasets/imports"
    assert error.next_call.body.to_dict() == {"type": "cex"}
    assert error.retry_after == "30"
