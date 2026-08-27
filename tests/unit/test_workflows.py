"""Unit tests for the high-level SDK workflows.

The auth/session layer is mocked via `pytest-httpx` so these run offline.
They verify the SDK routes calls through `AuthenticatedSession.call`
(refresh-on-401) and builds correct requests — not real network behaviour
(see tests/integration for live checks).
"""

from __future__ import annotations

import json

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


def test_exchanges_refreshes_and_retries_401(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token",
        json={
            "access_token": "jwt-refreshed",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": [],
            "tier": "free",
        },
    )
    httpx_mock.add_response(url=f"{BASE}/exchanges", status_code=401)
    httpx_mock.add_response(
        url=f"{BASE}/exchanges",
        json=[{"id": "binance", "name": "Binance", "description": "Binance exchange"}],
        headers={"content-type": "application/json"},
    )

    exchanges = wf.exchanges(token)

    assert exchanges is not None
    assert exchanges[0].id == "binance"
    requests = [
        request for request in httpx_mock.get_requests() if request.url.path == "/v1/exchanges"
    ]
    assert len(requests) == 2
    assert requests[-1].headers["Authorization"] == "Bearer jwt-refreshed"


def test_compile_strategy_refreshes_and_returns_typed_model(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token",
        json={
            "access_token": "jwt-refreshed",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": [],
            "tier": "free",
        },
    )
    httpx_mock.add_response(url=f"{BASE}/strategy", method="POST", status_code=401)
    httpx_mock.add_response(
        url=f"{BASE}/strategy",
        method="POST",
        json={"strategyId": "strategy-1", "declaredProperties": []},
    )

    compiled = wf.compile_strategy(token, "public class Strategy {}")

    assert compiled.strategy_id == "strategy-1"
    requests = [
        request for request in httpx_mock.get_requests() if request.url.path == "/v1/strategy"
    ]
    assert len(requests) == 2
    assert requests[-1].headers["Authorization"] == "Bearer jwt-refreshed"


def test_prepare_passes_dataset_version_id(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/backtest/user/ticker/prepare",
        method="POST",
        status_code=202,
        json={"jobId": "prepare-1"},
    )

    accepted = wf.prepare(
        token,
        exchange_id="user",
        dataset_id="dataset-1",
        dataset_version_id="version-1",
        from_="2026-08-01",
        to="2026-08-02",
    )

    assert accepted is not None
    assert accepted.job_id == "prepare-1"
    request = httpx_mock.get_request(url=f"{BASE}/backtest/user/ticker/prepare", method="POST")
    assert request is not None
    payload = json.loads(request.read())
    assert payload["datasetId"] == "dataset-1"
    assert payload["datasetVersionId"] == "version-1"


def test_sweep_serializes_plain_python_arguments(token, httpx_mock: HTTPXMock):
    url = f"{BASE}/backtest/binance/ticker/executeSweep/prepare-1"
    httpx_mock.add_response(
        url=url,
        method="POST",
        status_code=202,
        json={
            "sweepId": "sweep-1",
            "requestId": "prepare-1",
            "totalRuns": 2,
            "shards": 1,
            "seed": 42,
            "queued": True,
        },
    )

    accepted = wf.sweep(
        token,
        exchange_id="binance",
        type_="ticker",
        request_id="prepare-1",
        strategy_id="strategy-1",
        params={"cycle.seconds": {"values": [10, 20]}},
    )

    assert accepted is not None
    assert accepted.sweep_id == "sweep-1"
    request = httpx_mock.get_request(url=url, method="POST")
    assert request is not None
    payload = request.read().decode()
    assert '"params":{"cycle.seconds":{"values":[10,20]}}' in payload
    assert '"sampler":"grid"' in payload
    assert '"objective":"sharpe"' in payload
    assert '"samples"' not in payload
    assert '"seed"' not in payload
    assert '"walkForward"' not in payload


def test_backtest_result_returns_raw_response_for_running_state(token, httpx_mock: HTTPXMock):
    url = f"{BASE}/backtest/binance/ticker/execute/job-1"
    httpx_mock.add_response(
        url=url,
        status_code=202,
        json={"state": {"status": "Running"}, "results": {"totalTrades": 0}},
    )

    response = wf.backtest_result(
        token,
        exchange_id="binance",
        type_="ticker",
        job_id="job-1",
    )

    assert response.status_code == 202
    assert response.json()["state"]["status"] == "Running"
