"""Streamable HTTP transparent proxy.

Forwards all incoming HTTP requests to a target MCP server, records every
request/response pair via a WitnessLogger, and streams SSE responses back
to the caller without buffering.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from ..witness.log import WitnessLogger


def create_proxy_app(
    target_url: str,
    witness_logger: WitnessLogger,
    actor: str = "proxy",
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

    # Shared async HTTP client (created at startup, closed at shutdown).
    client: httpx.AsyncClient

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal client
        client = httpx.AsyncClient(base_url=target, timeout=60.0, follow_redirects=True)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await client.aclose()

    # ------------------------------------------------------------------
    # Single catch-all route
    # ------------------------------------------------------------------

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy_all(path: str, request: Request) -> Response:
        """Forward any request to the upstream server and record the exchange."""
        upstream_url = f"/{path}"

        # Build forwarded headers (drop host so httpx sets it correctly).
        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() != "host"
        }

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
