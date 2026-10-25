"""Tests for the loopback control-plane UI server."""
from __future__ import annotations

import json
import os
import stat
import threading
import urllib.error
import urllib.request as U

import pytest

from agentwit.config import init_home
from agentwit.ui.server import serve


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTWIT_HOME", str(tmp_path))
    init_home(tmp_path)
    httpd, token = serve(host="127.0.0.1", port=0, home=tmp_path)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}", token, tmp_path
    httpd.shutdown()
    httpd.server_close()


def _req(base, path, method="GET", body=None, headers=None, host=None):
    h = dict(headers or {})
    if host is not None:
        h["Host"] = host
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["Content-Type"] = "application/json"
    r = U.Request(base + path, data=data, headers=h, method=method)
    try:
        with U.urlopen(r) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw and path.startswith("/api") else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_only_binds_loopback(tmp_path):
    with pytest.raises(ValueError):
        serve(host="0.0.0.0", port=0, home=tmp_path)


def test_get_endpoints(server):
    base, _, _ = server
    assert _req(base, "/api/config")[0] == 200
    assert _req(base, "/api/status")[0] == 200
    assert _req(base, "/api/detections")[0] == 200


def test_token_injected_into_page(server):
    base, token, _ = server
    html = _req(base, "/")[1].decode()
    assert "__CSRF__" not in html and token in html


def test_bad_host_rejected(server):
    base, _, _ = server
    assert _req(base, "/api/config", host="evil.example.com")[0] == 403


def test_post_requires_csrf(server):
    base, _, _ = server
    assert _req(base, "/api/config", method="POST", body={"proxy": {}})[0] == 403


def test_invalid_config_rejected(server):
    base, token, _ = server
    sc, _ = _req(base, "/api/config", method="POST",
                 body={"proxy": {"port": 99999}}, headers={"X-Agentwit-Token": token})
    assert sc == 400


def test_valid_config_persists(server):
    base, token, _ = server
    cfg = _req(base, "/api/config")[1]
    cfg["proxy"]["port"] = 9100
    assert _req(base, "/api/config", method="POST", body=cfg,
                headers={"X-Agentwit-Token": token})[0] == 200
    assert _req(base, "/api/config")[1]["proxy"]["port"] == 9100


def test_secret_write_never_echoes_value(server):
    base, token, home = server
    sc, resp = _req(base, "/api/secret", method="POST",
                    body={"name": "AGENTWIT_X_WEBHOOK", "value": "https://hooks.slack.com/SEKRET"},
                    headers={"X-Agentwit-Token": token})
    assert sc == 200
    assert "SEKRET" not in json.dumps(resp)
    assert resp["name"] == "AGENTWIT_X_WEBHOOK"
    sp = home / "secrets.env"
    assert "SEKRET" in sp.read_text()
    if os.name == "posix":
        assert stat.S_IMODE(sp.stat().st_mode) == 0o600


def test_bad_secret_name_rejected(server):
    base, token, _ = server
    assert _req(base, "/api/secret", method="POST",
                body={"name": "bad name!", "value": "x"},
                headers={"X-Agentwit-Token": token})[0] == 400
