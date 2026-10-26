"""End-to-end forward test for the HTTP witness proxy.

Regression guard for the closure bug where `_record` referenced a
`_notifier` that proxy_all had shadowed into a local — every forwarded
request raised NameError and returned 500. There was previously no test
that actually drove a request through create_proxy_app's route, so a
buffered-JSON passthrough (the real MCP-over-HTTP case) was never
exercised. This stubs the upstream so no network/MCP server is needed.
"""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentwit.proxy.http_proxy import create_proxy_app
from agentwit.witness.log import WitnessLogger


class _StubResponse:
    """Minimal stand-in for httpx.Response in streaming mode."""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()
        self.status_code = 200
        self.headers = httpx.Headers({"content-type": "application/json"})

    async def aiter_bytes(self):
        yield self._body

    async def aread(self) -> bytes:
        return self._body

    async def aclose(self) -> None:
        return None


class _StubClient:
    """Replaces the proxy's httpx.AsyncClient; records nothing upstream."""

    def __init__(self, *a, **k) -> None:
        pass

    def build_request(self, method, url, headers, content, params):
        return {"method": method, "url": url}

    async def send(self, req, stream=False):
        # Include a token the scorer flags (shell_exec) so _record() reaches
        # its `if _notifier:` branch — the exact line that raised NameError
        # on the live server. A benign {"tools": []} would skip it entirely
        # and let the bug through, which is how it shipped.
        return _StubResponse(
            {"jsonrpc": "2.0", "id": 1,
             "result": {"tools": [{"name": "run_command", "desc": "bash"}]}}
        )

    async def aclose(self) -> None:
        return None


@pytest.fixture()
def proxy_client(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    logger = WitnessLogger(session_dir=str(tmp_path / "wl"), actor="test")
    # No webhook_url -> the daemon/NotificationHub configuration that
    # triggered the original NameError.
    app = create_proxy_app(
        target_url="http://upstream.invalid:3000",
        witness_logger=logger,
        config={"notify": {"routes": []}},
    )
    with TestClient(app) as client:
        yield client


def test_forwarded_post_returns_200_not_500(proxy_client):
    r = proxy_client.post(
        "/mcp",
        content=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        ),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"]["tools"][0]["name"] == "run_command"


def test_forwarded_post_with_legacy_webhook_route(tmp_path, monkeypatch):
    """Same path, but with webhook_url set so the bypass branch's notifier
    assignment exists — guards against re-shadowing from the other side."""
    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    logger = WitnessLogger(session_dir=str(tmp_path / "wl2"), actor="test")
    app = create_proxy_app(
        target_url="http://upstream.invalid:3000",
        witness_logger=logger,
        webhook_url="https://hooks.slack.com/services/x/y/z",
        config={"notify": {"routes": []}},
    )
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            content=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 200, r.text
