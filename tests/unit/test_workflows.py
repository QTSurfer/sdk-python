"""Unit tests for the high-level SDK workflows.

The auth/session layer is mocked via `pytest-httpx` so these run offline.
They verify the SDK routes calls through `AuthenticatedSession.call`
(refresh-on-401) and builds correct requests — not real network behaviour
(see tests/integration for live checks).
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from qtsurfer_sdk import _workflows as wf
from qtsurfer_sdk import auth

BASE = "https://api.example/v1"


@pytest.fixture
def token(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token",
        json={
            "access_token": "jwt-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": [],
            "tier": "free",
        },
    )
    s = auth("test-apikey", base_url=BASE)
    return s


def test_auth_mints_jwt(token):
    assert token.token is not None
    assert token.token.access_token == "jwt-token"


def test_exchanges_returns_list(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/exchanges",
        json=[{"id": "binance", "name": "Binance", "description": "Binance exchange"}],
        headers={"content-type": "application/json"},
    )
    ex = wf.exchanges(token)
    assert len(ex) == 1
    assert ex[0].id == "binance"
