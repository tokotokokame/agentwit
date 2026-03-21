"""Streamable HTTP transparent proxy.

Forwards all incoming HTTP requests to a target MCP server, records every
request/response pair via a WitnessLogger, and streams SSE responses back
to the caller without buffering.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from ..security.bypass_detector import BypassDetector
from ..monitor.backup import SessionBackup
from ..witness.log import WitnessLogger

logger = logging.getLogger(__name__)

_AUDIT_PATH = Path.home() / ".agentwit" / "audit.jsonl"


def create_proxy_app(
    target_url: str,
    witness_logger: WitnessLogger,
    actor: str = "proxy",
    webhook_url: str | None = None,
    webhook_on: str = "HIGH,CRITICAL",
) -> FastAPI:
    """Create and return a FastAPI app that transparently proxies to *target_url*.

    Args:
        target_url: Base URL of the upstream MCP server (e.g.
            ``"http://localhost:3000"``).
        witness_logger: An active :class:`~agentwit.witness.log.WitnessLogger`
            instance used to record all events.
        actor: Identifier written into each witness log event.

    Returns:
        A configured :class:`fastapi.FastAPI` application ready to be served
        with uvicorn.
    """
    app = FastAPI(title="agentwit proxy", version="0.1.0")
    target = target_url.rstrip("/")
    bypass_detector = BypassDetector()

    # Shared async HTTP client (created at startup, closed at shutdown).
    client: httpx.AsyncClient

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal client
        client = httpx.AsyncClient(base_url=target, timeout=60.0, follow_redirects=True)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await client.aclose()
        # セッション終了時に自動バックアップ
        try:
            SessionBackup().backup(witness_logger.session_path)
        except Exception as exc:
            logger.warning("agentwit session backup failed: %s", exc)

    # ------------------------------------------------------------------
    # Single catch-all route
    # ------------------------------------------------------------------

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy_all(path: str, request: Request) -> Response:
        """Forward any request to the upstream server and record the exchange."""
        upstream_url = f"/{path}"

        # バイパス検知: 受信リクエストにプロキシヘッダーがなければ記録
        bypass_alert = bypass_detector.check_request(dict(request.headers))
        if bypass_alert:
            _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _AUDIT_PATH.open("a", encoding="utf-8") as _af:
                _af.write(json.dumps({
                    **bypass_alert,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": f"/{path}",
                }) + "\n")
            if webhook_url:
                from ..notifier.webhook import WebhookNotifier
                _notifier = WebhookNotifier(url=webhook_url, min_severity="high")
                asyncio.ensure_future(_notifier.notify_if_threshold(
                    {"actor": actor, "tool": None,
                     "session_id": witness_logger.session_id,
                     "timestamp": datetime.now(timezone.utc).isoformat()},
                    [{"pattern": "proxy_bypass", "severity": "high", **bypass_alert}],
                ))

        # Build forwarded headers (drop host so httpx sets it correctly).
        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() != "host"
        }
        # リクエスト転送時にプロキシヘッダーを付与
        bypass_detector.inject_header(forward_headers)

        body = await request.body()

        # Parse JSON body for MCP introspection.
        json_body: dict = {}
        if body and "application/json" in request.headers.get("content-type", ""):
            try:
                json_body = json.loads(body)
            except json.JSONDecodeError:
                pass

        # Identify the action and tool name.
        action: str = json_body.get("method", request.method)
        tool: str | None = None
        if action == "tools/call":
            tool = (
                json_body.get("params", {}).get("name")
                or json_body.get("params", {}).get("tool")
            )

        try:
            upstream_request = client.build_request(
                method=request.method,
                url=upstream_url,
                headers=forward_headers,
                content=body,
                params=dict(request.query_params),
            )
            upstream_response = await client.send(upstream_request, stream=True)
        except httpx.RequestError as exc:
            error_payload = {
                "error": str(exc),
                "params": json_body,
            }
            event = await witness_logger.alog_event(
                action=action,
                tool=tool,
                full_payload=error_payload,
                risk_indicators=[{"pattern": "proxy_error", "severity": "low", "matched": str(exc)}],
            )
            return Response(
                content=json.dumps({"error": "upstream request failed", "detail": str(exc)}),
                status_code=502,
                media_type="application/json",
                headers={"X-Agentwit-Witness-Id": event.get("witness_id", "")},
            )

        content_type = upstream_response.headers.get("content-type", "")
        is_sse = "text/event-stream" in content_type

        # Copy upstream response headers, but skip ones that would conflict.
        _skip = {"content-encoding", "transfer-encoding", "content-length"}
        response_headers: dict[str, str] = {
            k: v
            for k, v in upstream_response.headers.items()
            if k.lower() not in _skip
        }

        if is_sse:
            # --- Streaming SSE path -------------------------------------------
            witness_id_holder: list[str] = [""]

            async def sse_stream() -> AsyncIterator[bytes]:
                chunks: list[str] = []
                async for chunk in upstream_response.aiter_bytes():
                    chunks.append(chunk.decode(errors="replace"))
                    yield chunk

                raw_text = "".join(chunks)
                payload = {
                    "params": json_body,
                    "result": {"raw_sse": raw_text},
                }
                event = await witness_logger.alog_event(
                    action=action,
                    tool=tool,
                    full_payload=payload,
                )
                witness_id_holder[0] = event.get("witness_id", "")

            response_headers["X-Agentwit-Witness-Id"] = witness_id_holder[0]
            return StreamingResponse(
                sse_stream(),
                status_code=upstream_response.status_code,
                headers=response_headers,
                media_type=content_type,
            )

        else:
            # --- Regular (buffered) response path --------------------------------
            response_body = await upstream_response.aread()

            response_json: dict = {}
            if "application/json" in content_type:
                try:
                    response_json = json.loads(response_body)
                except json.JSONDecodeError:
                    pass

            full_payload: dict = {
                "params": json_body,
                "result": response_json or {"raw": response_body.decode(errors="replace")},
            }

            event = await witness_logger.alog_event(
                action=action,
                tool=tool,
                full_payload=full_payload,
            )

            response_headers["X-Agentwit-Witness-Id"] = event.get("witness_id", "")

            return Response(
                content=response_body,
                status_code=upstream_response.status_code,
                headers=response_headers,
                media_type=content_type or None,
            )

    return app
