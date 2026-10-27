"""End-to-end forward tests for the HTTP witness proxy.

Two regression guards, both of which were missing when the proxy shipped:

1. The closure bug: `_record` referenced a `_notifier` that proxy_all had
   shadowed into a local, so every forwarded request that produced a risk
   indicator raised NameError -> 500. There was no forward test at all, so
   a buffered-JSON passthrough (the real MCP-over-HTTP case) was never run.

2. The introspection false-positive: a `tools/list` response is a tool
   *catalogue*; keyword-scanning it flags credential_access ("credentials"
   param) and lateral_movement ("nmap" in a description) on a pentest
   toolset. tools/list must now record without risk-scoring.

The upstream is stubbed so no network/MCP server is needed.
"""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentwit.proxy.http_proxy import create_proxy_app
from agentwit.witness.log import WitnessLogger

# A catalogue shaped like the real server: tool metadata legitimately
# containing security keywords that used to trip the scorer.
_CATALOG = {
    "jsonrpc": "2.0", "id": 1,
    "result": {"result": {"tools": [
        {"name": "cloud-scan",
         "inputSchema": {"properties": {"credentials": {"type": "object"}}}},
        {"name": "htb-advisor", "description": "needs an nmap result"},
    ]}},
}


class _StubResponse:
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
    def __init__(self, *a, **k) -> None:
        pass

    def build_request(self, method, url, headers, content, params):
        return {"method": method, "url": url}

    async def send(self, req, stream=False):
        return _StubResponse(_CATALOG)

    async def aclose(self) -> None:
        return None


def _make(tmp_path, monkeypatch, sub, webhook_url=None):
    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    logger = WitnessLogger(session_dir=str(tmp_path / sub), actor="test")
    app = create_proxy_app(
        target_url="http://upstream.invalid:3000",
        witness_logger=logger,
        webhook_url=webhook_url,
        config={"notify": {"routes": []}},
    )
    return TestClient(app), logger


def _last_event(logger) -> dict:
    lines = (logger.session_path / "witness.jsonl").read_text().splitlines()
    return json.loads(lines[-1])


def test_tools_call_forwards_and_reaches_notifier_branch(tmp_path, monkeypatch):
    """A tools/call with a flagged arg scores -> _record hits `if _notifier:`.
    This is the exact line that raised NameError when the name was shadowed;
    the request must still return 200."""
    client, _ = _make(tmp_path, monkeypatch, "wl")
    with client:
        r = client.post(
            "/mcp",
            content=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "run_command",
                           "arguments": {"cmd": "bash -lc id"}},
            }),
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 200, r.text


def test_tools_call_with_webhook_route(tmp_path, monkeypatch):
    """Same, with webhook_url set so the bypass branch's notifier assignment
    exists — guards the shadow from the other side."""
    client, _ = _make(tmp_path, monkeypatch, "wl2",
                      webhook_url="https://hooks.slack.com/services/x/y/z")
    with client:
        r = client.post(
            "/mcp",
            content=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "run_command",
                           "arguments": {"cmd": "sudo cat /etc/shadow"}},
            }),
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 200, r.text


def test_tools_list_is_recorded_but_not_risk_scored(tmp_path, monkeypatch):
    """The catalogue response contains 'credentials' and 'nmap', which used to
    flag credential_access / lateral_movement on every tools/list. It must now
    be recorded (chain intact) with NO risk indicators."""
    client, logger = _make(tmp_path, monkeypatch, "wl3")
    with client:
        r = client.post(
            "/mcp",
            content=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 200, r.text
    ev = _last_event(logger)
    assert ev["action"] == "tools/list"
    assert not ev.get("risk_indicators"), ev.get("risk_indicators")
