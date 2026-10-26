"""SMTP email notification backend.

Uses only the standard library (``smtplib`` + ``email.message``), so no new
dependency. Sending is pushed to a thread via ``run_in_executor`` so the
proxy event loop is never blocked, and every failure is swallowed (a
monitoring tool must not crash because a mail server is down).

SMTP credentials come from config as ``${env:...}`` references resolved
before the sender is built — they are never stored in config.yaml.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)


class EmailSender:
    """Send a one-shot alert email over SMTP (connection made per send)."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        use_tls: bool = True,
        username: str | None = None,
        password: str | None = None,
        mail_from: str | None = None,
        mail_to: list[str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.use_tls = bool(use_tls)
        self.username = username
        self.password = password
        self.mail_from = mail_from or (username or "agentwit@localhost")
        self.mail_to = mail_to or []
        self.timeout = timeout

    async def send(
        self, event: dict[str, Any], indicators: list[dict], severity: str
    ) -> None:
        """Send asynchronously; never raises."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, self._send_sync, event, indicators, severity
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("agentwit email notification failed: %s", exc)

    def _build(self, event: dict, indicators: list[dict], severity: str) -> EmailMessage:
        from .sanitize import clean_field
        tool = clean_field(event.get("tool") or "unknown")
        session = clean_field(event.get("session_id") or "unknown")
        patterns = clean_field(", ".join(sorted({i.get("pattern", "") for i in indicators})))
        msg = EmailMessage()
        msg["Subject"] = f"[agentwit {severity.upper()}] {patterns or 'alert'} on {tool}"
        msg["From"] = self.mail_from
        msg["To"] = ", ".join(self.mail_to)
        msg.set_content(
            f"agentwit risk alert [{severity.upper()}]\n"
            f"Session : {session}\n"
            f"Tool    : {tool}\n"
            f"Patterns: {patterns}\n"
            f"Time    : {event.get('timestamp', '')}\n"
            f"Witness : {event.get('witness_id', '')}\n"
        )
        return msg

    def _send_sync(self, event: dict, indicators: list[dict], severity: str) -> None:
        if not self.mail_to:
            logger.warning("agentwit email: no recipients configured; skipping")
            return
        self._deliver(self._build(event, indicators, severity))

    async def send_text(self, subject: str, body: str) -> None:
        """Send a plain text email (e.g. a summary). Never raises."""
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.mail_from
        msg["To"] = ", ".join(self.mail_to)
        msg.set_content(body)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._deliver, msg)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("agentwit email summary failed: %s", type(exc).__name__)

    def _deliver(self, msg: EmailMessage) -> None:
        if not self.mail_to:
            return
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            if self.use_tls:
                server.starttls(context=ssl.create_default_context())
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(msg)
