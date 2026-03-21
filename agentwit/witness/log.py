"""Witness Log generation.

Records all events to a JSONL file with cryptographic chaining so that
any post-hoc modification of the log is detectable.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chain import ChainManager
from ..security.signing import EventSigner


def _sha256(data: Any) -> str:
    """Return the hex-encoded sha256 digest of the canonical JSON of *data*."""
    if data is None:
        data = {}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class WitnessLogger:
    """Records agent ↔ MCP communication events to a tamper-evident JSONL log.

    Each call to :meth:`log_event` (or :meth:`alog_event`) appends one JSON
    line to ``<session_dir>/witness.jsonl`` and returns the signed event dict.

    Example::

        logger = WitnessLogger("/tmp/logs", actor="my-agent")
        event = logger.log_event("tools/call", "bash", {"params": {...}})
        logger.close()
    """

    def __init__(self, session_dir: str | Path, actor: str = "unknown") -> None:
        """Create a new WitnessLogger.

        Args:
            session_dir: Parent directory in which the session sub-directory
                will be created.
            actor: Human-readable identifier for the entity whose traffic is
                being recorded (e.g. ``"claude-agent"``).
        """
        session_dir = Path(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_id: str = f"session_{timestamp}"
        self.session_path: Path = session_dir / self.session_id
        self.session_path.mkdir(parents=True, exist_ok=True)

        self.actor = actor
        self.chain = ChainManager(session_id=self.session_id)
        self._signer = EventSigner()

        log_path = self.session_path / "witness.jsonl"
        self._log_file = log_path.open("a", encoding="utf-8")

    # ------------------------------------------------------------------
    # Synchronous API
    # ------------------------------------------------------------------

    def log_event(
        self,
        action: str,
        tool: str | None,
        full_payload: dict,
        risk_indicators: list | None = None,
    ) -> dict:
        """Record an event synchronously.

        Args:
            action: The MCP method or action name (e.g. ``"tools/call"``).
            tool: The tool name involved, if applicable.
            full_payload: The full request/response payload dict.
            risk_indicators: Optional list of risk indicator dicts from the
                analyzer.

        Returns:
            The signed event dict (includes ``witness_id`` and
            ``session_chain``).
        """
        event = self._build_event(action, tool, full_payload, risk_indicators or [])
        signed = self.chain.sign(event)
        signed["signature"] = self._signer.sign(signed)
        signed["signed_by"] = self._signer.fingerprint()
        self._append(signed)
        return signed

    def close(self) -> None:
        """Flush and close the underlying log file."""
        self._log_file.flush()
        self._log_file.close()

    # ------------------------------------------------------------------
    # Asynchronous API
    # ------------------------------------------------------------------

    async def alog_event(
        self,
        action: str,
        tool: str | None,
        full_payload: dict,
        risk_indicators: list | None = None,
    ) -> dict:
        """Async wrapper around :meth:`log_event`.

        Logging itself is synchronous (file I/O), but this coroutine makes
        it easy to ``await`` from async code without blocking the event loop
        for a long time.
        """
        return self.log_event(action, tool, full_payload, risk_indicators)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_event(
        self,
        action: str,
        tool: str | None,
        full_payload: dict,
        risk_indicators: list,
    ) -> dict:
        """Construct the raw (unsigned) event dict."""
        input_data = full_payload.get("params", full_payload.get("input", {}))
        output_data = full_payload.get("result", full_payload.get("output", {}))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": self.actor,
            "action": action,
            "tool": tool,
            "input_hash": _sha256(input_data),
            "output_hash": _sha256(output_data),
            "full_payload": full_payload,
            "risk_indicators": risk_indicators,
        }

    def _append(self, event: dict) -> None:
        """Write *event* as a single JSON line to the log file."""
        self._log_file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self._log_file.flush()
