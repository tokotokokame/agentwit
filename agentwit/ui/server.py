"""Loopback control-plane for agentwit — standard library only.

Serves a small single-page console and a handful of JSON endpoints for
reading and changing ~/.agentwit/config.yaml, adding secrets, and viewing
recent detections. It is deliberately minimal and defensive, because a
monitoring tool's own control plane must not become the soft spot:

  * binds 127.0.0.1 only (never a routable address);
  * checks the Host header so a remote page cannot drive it via DNS
    rebinding;
  * every mutating request must carry the CSRF token minted at startup,
    which also blocks other local web pages from POSTing here;
  * config writes are schema-validated and rejected if invalid;
  * secret values are written to secrets.env (0600) and never read back
    over the wire — the API returns names only.

No third-party dependency.
"""
from __future__ import annotations

import json
import secrets as _secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import (
    config_home,
    load_config,
    save_config,
    validate_config,
    set_secret,
    list_secret_names,
)

_STATIC = Path(__file__).parent / "static"
_MAX_BODY = 256 * 1024  # generous for config, bounded against abuse


def _recent_detections(home: Path, limit: int = 50) -> list[dict]:
    """Flagged events from the newest witness session (already redacted)."""
    logs = home / "witness_logs"
    if not logs.is_dir():
        return []
    sessions = sorted(
        (p for p in logs.glob("session_*") if p.is_dir()),
        key=lambda p: p.name, reverse=True,
    )
    out: list[dict] = []
    for sess in sessions:
        wl = sess / "witness.jsonl"
        if not wl.exists():
            continue
        try:
            for line in wl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                if e.get("risk_indicators"):
                    out.append({
                        "timestamp": e.get("timestamp", ""),
                        "tool": e.get("tool") or "",
                        "patterns": [i.get("pattern") for i in e["risk_indicators"]],
                        "severity": _worst(e["risk_indicators"]),
                    })
        except (OSError, json.JSONDecodeError):
            continue
        if out:
            break
    return out[-limit:][::-1]


def _worst(indicators: list[dict]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return max((str(i.get("severity", "low")).lower() for i in indicators),
               key=lambda s: order.get(s, 0), default="low")


def _status(home: Path) -> dict:
    try:
        from ..plugins import load_plugins
        plugins = [getattr(p, "name", type(p).__name__) for p in load_plugins()]
    except Exception:
        plugins = []
    backups = []
    bdir = home / "backups"
    if bdir.is_dir():
        for p in sorted(bdir.iterdir(), key=lambda x: x.name, reverse=True)[:20]:
            try:
                backups.append({"name": p.name, "size": p.stat().st_size})
            except OSError:
                pass
    return {"home": str(home), "plugins": plugins, "backups": backups,
            "secrets": list_secret_names(home)}


def make_handler(home: Path, csrf_token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "agentwit-ui"

        # --- guards -------------------------------------------------------
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost", "")

        def _send(self, code: int, obj, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # keep the console quiet
            pass

        # --- GET ----------------------------------------------------------
        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            if self.path in ("/", "/index.html"):
                # The token is NOT embedded in the page. It travels in the URL
                # fragment (printed in the terminal) and the page reads it from
                # location.hash — a blind GET / by another local process never
                # sees it. The fragment is never sent to the server.
                html = (_STATIC / "index.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if self.path == "/api/config":
                return self._send(200, load_config(home, resolve_secrets=False))
            if self.path == "/api/status":
                return self._send(200, _status(home))
            if self.path == "/api/detections":
                return self._send(200, {"detections": _recent_detections(home)})
            return self._send(404, {"error": "not found"})

        # --- POST ---------------------------------------------------------
        def do_POST(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            sent = self.headers.get("X-Agentwit-Token") or ""
            if not _secrets.compare_digest(sent, csrf_token):  # constant-time
                return self._send(403, {"error": "bad or missing CSRF token"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"error": "bad content-length"})
            if length <= 0 or length > _MAX_BODY:
                return self._send(413, {"error": "bad body size"})
            try:
                data = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid json"})

            if self.path == "/api/config":
                errors, warnings = validate_config(data)
                if errors:
                    return self._send(400, {"error": "invalid config", "details": errors})
                save_config(data, home)
                return self._send(200, {"ok": True, "warnings": warnings})

            if self.path == "/api/secret":
                name, value = data.get("name"), data.get("value")
                if not isinstance(name, str) or not isinstance(value, str):
                    return self._send(400, {"error": "name and value required"})
                try:
                    set_secret(name, value, home)
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
                return self._send(200, {"ok": True, "name": name})  # never echo value

            return self._send(404, {"error": "not found"})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8799,
          home: Path | None = None) -> tuple[ThreadingHTTPServer, str]:
    """Build the server and return (httpd, csrf_token). Caller runs serve_forever."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("the UI only binds loopback (127.0.0.1)")
    home = home or config_home()
    token = _secrets.token_urlsafe(32)
    httpd = ThreadingHTTPServer((host, port), make_handler(home, token))
    return httpd, token
