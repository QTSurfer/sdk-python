"""Offline integration tests for the ``auth()`` helper.

Drives the helper through the public ``qtsurfer_sdk.auth`` entry point
against a real local HTTP server on a free port — exercising the full
``qtsurfer-api-client`` stack (``httpx`` transport, generated client,
response parsing) without ever leaving the test process.

No live calls to api.qtsurfer.com / .net.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from qtsurfer.api.client._generated.models import AuthTokenResponse

from qtsurfer_sdk import QTSAuthError, auth


class _Stub:
    """Shared scratch space between the test and the request handler."""

    def __init__(self) -> None:
        self.token_responses: list[dict[str, Any] | int] = []
        self.token_call_count = 0
        self.last_apikey: str | None = None
        self.last_authorization: str | None = None


def _make_handler(stub: _Stub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 (signature)
            pass

        def do_POST(self):  # noqa: N802
            if self.path.endswith("/auth/token"):
                stub.last_apikey = self.headers.get("X-API-Key")
                stub.token_call_count += 1
                if not stub.token_responses:
                    self._respond(500, {"error": "no_stub"})
                    return
                resp = stub.token_responses.pop(0)
                if isinstance(resp, int):
                    self._respond(resp, {"code": "invalid_apikey", "message": "x"})
                else:
                    self._respond(200, resp)
            else:
                self._respond(404, {"error": "unknown"})

        def do_GET(self):  # noqa: N802
            stub.last_authorization = self.headers.get("Authorization")
            self._respond(200, [{"id": "binance", "name": "Binance"}])

        def _respond(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


@pytest.fixture
def stub_server():
    stub = _Stub()
    server = HTTPServer(("127.0.0.1", 0), _make_handler(stub))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield stub, f"http://127.0.0.1:{port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_end_to_end_mint_exposes_token_on_session(stub_server):
    stub, base_url = stub_server
    stub.token_responses.append(
        {
            "access_token": "jwt-int",
            "token_type": "Bearer",
            "expires_in": 3600,
            "tier": "pro",
        }
    )

    session = auth("ak_int", base_url=base_url)

    assert session.token is not None
    assert session.token.access_token == "jwt-int"
    assert isinstance(session.token, AuthTokenResponse)
    assert stub.last_apikey == "ak_int"


def test_end_to_end_token_store_plugin_receives_saved_token(stub_server):
    stub, base_url = stub_server
    stub.token_responses.append(
        {
            "access_token": "jwt-store",
            "token_type": "Bearer",
            "expires_in": 3600,
            "tier": "free",
        }
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
    assert saved[0].access_token == "jwt-store"


def test_end_to_end_mint_401_raises_qts_auth_error(stub_server):
    stub, base_url = stub_server
    stub.token_responses.append(401)

    with pytest.raises(QTSAuthError) as ex:
        auth("ak_bad", base_url=base_url)

    assert "401" in str(ex.value)


def test_end_to_end_authenticated_request_sends_bearer(stub_server):
    stub, base_url = stub_server
    stub.token_responses.append(
        {
            "access_token": "jwt-bearer",
            "token_type": "Bearer",
            "expires_in": 3600,
            "tier": "free",
        }
    )

    session = auth("ak", base_url=base_url)
    # Issue an arbitrary GET through the session's underlying client.
    resp = session.call(lambda c: c.get_httpx_client().get("/exchanges"))

    assert resp.status_code == 200
    assert stub.last_authorization == "Bearer jwt-bearer"
