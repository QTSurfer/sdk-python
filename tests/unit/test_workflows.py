"""Unit tests for the high-level SDK workflows.

The auth/session layer is mocked via `pytest-httpx` so these run offline.
They verify the SDK routes calls through `AuthenticatedSession.call`
(refresh-on-401) and builds correct requests — not real network behaviour
(see tests/integration for live checks).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from qtsurfer_sdk import (
    EquityCurveOutMode,
    GetLiveRunPaperEquityMeasure,
    QTSError,
    QTSInsufficientScopeError,
    QTSUploadError,
    auth,
)
from qtsurfer_sdk import _workflows as wf

BASE = "https://api.example/v1"


@pytest.fixture
def token(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token",
        json={
            "access_token": "jwt-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": {},
            "tier": "free",
        },
    )
    s = auth("test-apikey", base_url=BASE)
    return s


def test_auth_mints_jwt(token):
    assert token.token is not None
    assert token.token.access_token == "jwt-token"


def test_list_exchanges_returns_list(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/exchanges",
        json=[
            {
                "id": "binance",
                "name": "Binance",
                "description": "Binance exchange",
                "venueType": "cex",
                "segments": ["spot"],
                "liveSegments": ["spot"],
            }
        ],
        headers={"content-type": "application/json"},
    )
    ex = wf.list_exchanges(token)
    assert len(ex) == 1
    assert ex[0].id == "binance"


def test_live_list_methods_use_distinct_endpoints_and_return_typed_pages(token, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/live", json={"runs": []})
    httpx_mock.add_response(url=f"{BASE}/live/public", json={"runs": []})

    owned = token.list_live()
    public = token.list_public_live()

    assert owned.runs == []
    assert public.runs == []
    live_paths = [
        request.url.path
        for request in httpx_mock.get_requests()
        if request.url.path.startswith("/v1/live")
    ]
    assert live_paths == [
        "/v1/live",
        "/v1/live/public",
    ]


def test_start_live_passes_sandbox_override_and_duration(token, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/strategy/strategy-1/live",
        method="POST",
        status_code=201,
        json={
            "strategyId": "strategy-1",
            "runId": "run-1",
            "visibility": "private",
            "stage": "SANDBOX",
            "state": "STARTING",
            "desired": "RUNNING",
            "sources": [],
            "params": {},
            "paramsVersion": 0,
            "relay": False,
            "startedAtMs": 1_728_000_000_000,
            "sandboxMinutes": 60,
        },
    )

    from qtsurfer.api.client.models import StartLiveRequest

    run = token.start_live(
        "strategy-1", StartLiveRequest(sources=[], sandbox=True, sandbox_minutes=60)
    )

    assert run.run_id == "run-1"
    assert run.sandbox_minutes == 60
    request = httpx_mock.get_request(url=f"{BASE}/strategy/strategy-1/live", method="POST")
    assert request is not None
    assert json.loads(request.read()) == {
        "sources": [],
        "sandbox": True,
        "sandboxMinutes": 60,
        "relay": False,
        "stream": False,
        "visibility": "private",
    }


@pytest.mark.parametrize(
    ("method", "path", "status", "http_method"),
    [
        ("get_dataset", "/datasets/missing", 404, "GET"),
        ("get_strategy", "/strategy/missing", 404, "GET"),
        ("get_live", "/strategy/missing/live", 404, "GET"),
        ("update_live_params", "/live/missing/params", 409, "PUT"),
    ],
)
def test_workflow_http_errors_raise_qts_error(token, httpx_mock, method, path, status, http_method):
    httpx_mock.add_response(
        url=f"{BASE}{path}",
        method=http_method,
        status_code=status,
        json={"code": status, "message": "Request failed"},
    )

    with pytest.raises(QTSError, match="Request failed") as exc_info:
        if method == "update_live_params":
            token.update_live_params("missing", {"x": "1"})
        else:
            getattr(token, method)("missing")

    assert exc_info.value.status == status


def test_workflow_scope_error_preserves_required_scope(token, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/datasets/missing",
        status_code=403,
        json={
            "code": "insufficient_scope",
            "message": "This operation requires datasets:read.",
            "required": "datasets:read",
        },
    )

    with pytest.raises(QTSInsufficientScopeError) as exc_info:
        token.get_dataset("missing")

    assert exc_info.value.status == 403
    assert exc_info.value.code.value == "insufficient_scope"
    assert exc_info.value.required == "datasets:read"


def test_workflow_error_preserves_retryable_flag(token, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/backtest/binance/ticker/execute",
        method="POST",
        status_code=429,
        headers={"Retry-After": "5"},
        json={"code": "RATE_LIMITED", "message": "Try again later", "retryable": True},
    )

    with pytest.raises(QTSError, match="Try again later") as exc_info:
        token.execute(
            exchange_id="binance",
            type_="ticker",
            prepare_job_id="prepare-1",
            strategy_id="strategy-1",
        )

    assert exc_info.value.retryable is True
    assert exc_info.value.retry_after == "5"


def test_plan_required_error_preserves_optional_upgrade_url(token, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/strategy/strategy-1/validate",
        method="POST",
        status_code=402,
        json={
            "code": 402,
            "message": "The strategy requires Pro indicators.",
            "retryable": False,
            "upgradeUrl": "https://www.qtsurfer.com/pricing",
        },
    )

    with pytest.raises(QTSError, match="requires Pro indicators") as exc_info:
        token.validate_strategy("strategy-1")

    assert exc_info.value.status == 402
    assert exc_info.value.retryable is False
    assert exc_info.value.upgrade_url == "https://www.qtsurfer.com/pricing"


def test_live_paper_equity_command_and_deleted_catalogues(token, httpx_mock):
    equity_url = f"{BASE}/live/run-1/paper/equity"
    equity_query = (
        "currency=USDT&instrument=BTC%2FUSDT&measure=totalPnl&sinceMs=0"
        "&outMode=SHORT&differential=true&limit=4"
    )
    next_equity_query = (
        "currency=USDT&instrument=BTC%2FUSDT&measure=totalPnl&sinceMs=0"
        "&outMode=SHORT&differential=true&limit=4&cursor=next"
    )
    httpx_mock.add_response(
        url=f"{BASE}/live/run-1/paper",
        json={
            "runId": "run-1",
            "stage": "LIVE",
            "accounts": [],
        },
    )
    httpx_mock.add_response(
        url=f"{equity_url}?{equity_query}",
        json={
            "meta": {
                "inputPointCount": 0,
                "outputPointCount": 0,
                "resampled": False,
                "differential": True,
                "outMode": "SHORT",
            },
            "measure": "totalPnl",
            "gaps": [],
            "timestamps": [],
            "equities": [],
            "currency": "USDT",
            "instrument": "BTC/USDT",
            "_links": {"next": {"href": f"{equity_url}?{next_equity_query}"}},
        },
    )
    httpx_mock.add_response(
        url=f"{equity_url}?{next_equity_query}",
        json={
            "meta": {
                "inputPointCount": 0,
                "outputPointCount": 0,
                "resampled": False,
                "differential": True,
                "outMode": "SHORT",
            },
            "measure": "totalPnl",
            "gaps": [],
            "timestamps": [],
            "equities": [],
            "currency": "USDT",
            "instrument": "BTC/USDT",
        },
    )
    httpx_mock.add_response(
        url=f"{BASE}/live/run-1/commands",
        method="POST",
        status_code=202,
        json={"runId": "run-1", "commandId": "cmd-1", "effectiveAtMs": 123},
    )
    httpx_mock.add_response(url=f"{BASE}/strategies?includeDeleted=true", json={"strategies": []})
    httpx_mock.add_response(url=f"{BASE}/datasets?includeDeleted=true", json={"datasets": []})

    assert token.get_live_run_paper("run-1").run_id == "run-1"
    equity = token.get_live_run_paper_equity(
        "run-1",
        currency="USDT",
        instrument="BTC/USDT",
        measure=GetLiveRunPaperEquityMeasure.TOTALPNL,
        since_ms=0,
        out_mode=EquityCurveOutMode.SHORT,
        differential=True,
        limit=4,
    )
    next_equity = token.get_next_live_run_paper_equity("run-1", equity)
    assert next_equity.equities == []
    assert next_equity.instrument == "BTC/USDT"
    command = token.send_live_command("run-1", "rebalance", properties={"targetWeight": 0.25})
    assert command.command_id == "cmd-1"
    assert token.list_strategies(include_deleted=True).strategies == []
    assert token.list_datasets(include_deleted=True).datasets == []

    requests = httpx_mock.get_requests()
    command_request = next(
        request for request in requests if request.url.path.endswith("/commands")
    )
    assert command_request.read() == b'{"command":"rebalance","properties":{"targetWeight":0.25}}'
    continued = next(request for request in requests if request.url.params.get("cursor") == "next")
    assert continued.url.params["currency"] == "USDT"
    assert continued.url.params["instrument"] == "BTC/USDT"
    assert continued.url.params["measure"] == "totalPnl"
    assert continued.url.params["sinceMs"] == "0"
    assert continued.url.params["outMode"] == "SHORT"
    assert continued.url.params["differential"] == "true"
    assert continued.url.params["limit"] == "4"


def test_live_signal_continuation_preserves_filters(token, httpx_mock):
    signals_url = f"{BASE}/live/run-1/signals"
    initial_query = "sinceMs=123&instrument=ETH%2FUSDT&type=paper&limit=4"
    next_query = "sinceMs=123&instrument=ETH%2FUSDT&type=paper&cursor=next&limit=4"
    httpx_mock.add_response(
        url=f"{signals_url}?{initial_query}",
        json={"signals": [], "_links": {"next": {"href": f"{signals_url}?{next_query}"}}},
    )
    httpx_mock.add_response(url=f"{signals_url}?{next_query}", json={"signals": []})

    page = token.get_live_signals(
        "run-1", since_ms=123, instrument="ETH/USDT", signal_type="paper", limit=4
    )
    assert token.get_next_live_signals("run-1", page).signals == []


def test_list_exchanges_refreshes_and_retries_401(token, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token",
        json={
            "access_token": "jwt-refreshed",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": {},
            "tier": "free",
        },
    )
    httpx_mock.add_response(url=f"{BASE}/exchanges", status_code=401)
    httpx_mock.add_response(
        url=f"{BASE}/exchanges",
        json=[
            {
                "id": "binance",
                "name": "Binance",
                "description": "Binance exchange",
                "venueType": "cex",
                "segments": ["spot"],
                "liveSegments": ["spot"],
            }
        ],
        headers={"content-type": "application/json"},
    )

    exchanges = wf.list_exchanges(token)

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
            "scopes": {},
            "tier": "free",
        },
    )
    httpx_mock.add_response(url=f"{BASE}/strategy", method="POST", status_code=401)
    httpx_mock.add_response(
        url=f"{BASE}/strategy",
        method="POST",
        json={"strategyId": "strategy-1", "declaredProperties": [], "requires": ["indicators.pro"]},
    )

    compiled = wf.compile_strategy(token, "public class Strategy {}")

    assert compiled.strategy_id == "strategy-1"
    assert [requirement.value for requirement in compiled.requires] == ["indicators.pro"]
    requests = [
        request for request in httpx_mock.get_requests() if request.url.path == "/v1/strategy"
    ]
    assert len(requests) == 2
    assert requests[-1].headers["Authorization"] == "Bearer jwt-refreshed"


def test_compile_strategy_scope_error_is_typed(token, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/strategy",
        method="POST",
        status_code=403,
        json={
            "code": "insufficient_scope",
            "message": "This operation requires strategies:write.",
            "required": "strategies:write",
        },
    )

    with pytest.raises(QTSInsufficientScopeError) as exc_info:
        token.compile_strategy("public class Strategy {}")

    assert exc_info.value.required == "strategies:write"


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


def test_get_backtest_result_returns_raw_response_for_running_state(token, httpx_mock: HTTPXMock):
    url = f"{BASE}/backtest/binance/ticker/execute/job-1"
    httpx_mock.add_response(
        url=url,
        status_code=202,
        json={"state": {"status": "Running"}, "results": {"totalTrades": 0}},
    )

    response = wf.get_backtest_result(
        token,
        exchange_id="binance",
        type_="ticker",
        job_id="job-1",
    )

    assert response.status_code == 202
    assert response.json()["state"]["status"] == "Running"


def test_open_dataset_upload_returns_typed_session(token, httpx_mock: HTTPXMock):
    url = f"{BASE}/datasets/dataset-1/uploads"
    httpx_mock.add_response(
        url=url,
        method="POST",
        status_code=201,
        json={
            "uploadId": "upload-2",
            "upload": {"url": "https://uploads.example/upload-2", "expiresInMinutes": 15},
        },
    )

    upload = token.open_dataset_upload("dataset-1")

    assert upload is not None
    assert upload.upload_id == "upload-2"
    assert upload.upload.url == "https://uploads.example/upload-2"


def test_upload_dataset_file_puts_exact_bytes_without_authorization(
    tmp_path: Path, httpx_mock: HTTPXMock
):
    from qtsurfer.api.client._generated.models import DatasetUploadSession, DatasetUploadTarget

    source = tmp_path / "ticks.csv"
    source.write_bytes(b"timestamp,close\n1700000000,100.5\n")
    httpx_mock.add_response(url="https://uploads.example/upload-2", method="PUT", status_code=200)
    upload = DatasetUploadSession(
        upload_id="upload-2",
        upload=DatasetUploadTarget(url="https://uploads.example/upload-2", expires_in_minutes=15),
    )

    wf.upload_dataset_file(upload, source)

    request = httpx_mock.get_request(url="https://uploads.example/upload-2", method="PUT")
    assert request is not None
    assert request.content == source.read_bytes()
    assert "Authorization" not in request.headers
    assert "X-API-Key" not in request.headers


def test_upload_dataset_file_rejects_non_success_response(httpx_mock: HTTPXMock):
    from qtsurfer.api.client._generated.models import DatasetUploadSession, DatasetUploadTarget

    httpx_mock.add_response(url="https://uploads.example/upload-2", method="PUT", status_code=403)
    upload = DatasetUploadSession(
        upload_id="upload-2",
        upload=DatasetUploadTarget(url="https://uploads.example/upload-2", expires_in_minutes=15),
    )

    with pytest.raises(QTSUploadError, match="HTTP 403") as exc:
        wf.upload_dataset_file(upload, io.BytesIO(b"csv"))

    assert exc.value.status == 403
    assert "uploads.example" not in str(exc.value)


def test_upload_dataset_file_hides_presigned_url_on_transport_failure(httpx_mock: HTTPXMock):
    from qtsurfer.api.client._generated.models import DatasetUploadSession, DatasetUploadTarget

    url = "https://uploads.example/secret-signature"
    httpx_mock.add_exception(httpx.ConnectError(f"connection failed for {url}"), url=url)
    upload = DatasetUploadSession(
        upload_id="upload-2",
        upload=DatasetUploadTarget(url=url, expires_in_minutes=15),
    )

    with pytest.raises(QTSUploadError, match="transport failed") as exc:
        wf.upload_dataset_file(upload, io.BytesIO(b"csv"))

    assert "secret-signature" not in str(exc.value)
    assert exc.value.__cause__ is None


def test_upload_dataset_file_reports_missing_path(tmp_path: Path):
    from qtsurfer.api.client._generated.models import DatasetUploadSession, DatasetUploadTarget

    upload = DatasetUploadSession(
        upload_id="upload-2",
        upload=DatasetUploadTarget(url="https://uploads.example/upload-2", expires_in_minutes=15),
    )

    with pytest.raises(QTSUploadError, match="source could not be read"):
        wf.upload_dataset_file(upload, tmp_path / "missing.csv")
