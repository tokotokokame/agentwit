"""SSE transparent proxy.

Handles Server-Sent Events streams between an agent and an MCP server,
recording each SSE event to the witness log without interrupting the stream.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from agentwit.witness.log import WitnessLogger


class SseProxy:
    """Transparent SSE proxy that records events to the witness log.

    Attributes:
        target_url: The upstream SSE endpoint URL.
        witness_logger: Logger instance for recording events.
    """

    def __init__(self, target_url: str, witness_logger: "WitnessLogger") -> None:
        """Initialise the SSE proxy.

        Args:
            target_url: Upstream SSE endpoint.
            witness_logger: A :class:`~agentwit.witness.log.WitnessLogger`.
        """
        self.target_url = target_url
        self.witness_logger = witness_logger

    async def stream(self, timeout: float = 30.0, max_retries: int = 3) -> None:
        """Open the upstream SSE stream, record events, and retry on timeout.

        Retries up to *max_retries* times on :exc:`httpx.TimeoutException`
        with exponential backoff (1 s → 2 s → 4 s).  After all retries are
        exhausted a ``sse_timeout`` record is appended to ``audit.jsonl`` in
        the witness session directory and the exception is re-raised.

        Args:
            timeout: Per-request timeout in seconds (default 30).
            max_retries: Maximum number of retry attempts (default 3).
        """
        delays = (1, 2, 4)
        last_exc: httpx.TimeoutException | None = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("GET", self.target_url) as response:
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data_str = line[len("data:"):].strip()
                            if not data_str:
                                continue
                            try:
                                msg: object = json.loads(data_str)
                            except json.JSONDecodeError:
                                msg = {"raw": data_str}
                            try:
                                await self.witness_logger.alog_event(
                                    action="sse_event",
                                    tool=None,
                                    full_payload={"event": msg},
                                )
                            except Exception:
                                pass
                return  # stream finished cleanly
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(delays[attempt])

        # All retries exhausted — write sse_timeout to audit.jsonl
        try:
            _audit = Path(self.witness_logger.session_path) / "audit.jsonl"
            _audit.parent.mkdir(parents=True, exist_ok=True)
            with _audit.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "type": "sse_timeout",
                    "target": self.target_url,
                    "retries": max_retries,
                    "error": str(last_exc),
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }) + "\n")
        except Exception:
            pass

        if last_exc is not None:
            raise last_exc
