"""Webhook notification backend for agentwit risk alerts.

Sends fire-and-forget HTTP POST notifications to Slack or Discord webhooks
when HIGH or CRITICAL risk events are detected.

Usage::

    from agentwit.notifier.webhook import WebhookNotifier

    notifier = WebhookNotifier(
        url="https://hooks.slack.com/services/xxx/yyy/zzz",
        min_severity="HIGH",
    )
    await notifier.notify_if_threshold(event, risk_indicators)

Requires ``httpx>=0.27.0`` (already a core dependency).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Severity ordering
_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Severities that each CLI label maps to (case-insensitive input)
_SEVERITY_ALIASES: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


class WebhookNotifier:
    """Fire-and-forget webhook notifier for Slack and Discord.

    Automatically detects the target platform from the URL and sends the
    appropriate payload format.

    Args:
        url: The webhook URL (Slack ``hooks.slack.com`` or Discord
            ``discord.com/api/webhooks``).
        min_severity: Minimum severity level that triggers a notification.
            One of ``"LOW"``, ``"MEDIUM"``, ``"HIGH"``, ``"CRITICAL"``.
            Defaults to ``"HIGH"``.
    """

    def __init__(self, url: str, min_severity: str = "HIGH") -> None:
        self.url = url
        self.min_severity = min_severity.lower()
        self._min_order = _SEVERITY_ORDER.get(self.min_severity, 2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def notify_if_threshold(
        self,
        event: dict[str, Any],
        risk_indicators: list[dict[str, Any]],
    ) -> None:
        """Send a notification if any indicator meets the minimum severity.

        This is fire-and-forget: it schedules the HTTP call as a background
        task and returns immediately without raising exceptions.

        Args:
            event: The witness log event dict.
            risk_indicators: Risk indicators associated with this event.
        """
        worst_sev, worst_pat = self._worst(risk_indicators)
        if _SEVERITY_ORDER.get(worst_sev, -1) < self._min_order:
            return

        asyncio.ensure_future(
            self._send_safe(event, worst_sev, worst_pat, risk_indicators)
        )

    def notify_if_threshold_sync(
        self,
        event: dict[str, Any],
        risk_indicators: list[dict[str, Any]],
    ) -> None:
        """Synchronous variant — schedules via ``asyncio.ensure_future`` or
        creates a new event loop if none is running."""
        worst_sev, worst_pat = self._worst(risk_indicators)
        if _SEVERITY_ORDER.get(worst_sev, -1) < self._min_order:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self._send_safe(event, worst_sev, worst_pat, risk_indicators)
                )
            else:
                loop.run_until_complete(
                    self._send_safe(event, worst_sev, worst_pat, risk_indicators)
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Platform detection
    # ------------------------------------------------------------------

    def _is_discord(self) -> bool:
        return "discord.com/api/webhooks" in self.url or "discordapp.com/api/webhooks" in self.url

    def _build_payload(
        self,
        event: dict[str, Any],
        severity: str,
        pattern: str,
        all_indicators: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session_id = event.get("session_id", "unknown")
        tool = event.get("tool", "") or "unknown"
        timestamp = event.get("timestamp", "")
        actor = event.get("actor", "unknown")

        sev_upper = severity.upper()
        emoji = {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev_upper, "⚠️")
        text = (
            f"{emoji} *agentwit Alert* [{sev_upper}]\n"
            f"• Session: `{session_id}`\n"
            f"• Tool: `{tool}`\n"
            f"• Pattern: `{pattern}`\n"
            f"• Actor: `{actor}`\n"
            f"• Timestamp: {timestamp}"
        )

        if self._is_discord():
            return {"content": text.replace("*", "**")}

        # Slack format
        return {
            "text": f"{emoji} agentwit Alert [{sev_upper}]",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_safe(
        self,
        event: dict[str, Any],
        severity: str,
        pattern: str,
        all_indicators: list[dict[str, Any]],
    ) -> None:
        """Send the HTTP request; never raises — logs warnings on failure."""
        try:
            await self._send(event, severity, pattern, all_indicators)
        except Exception as exc:
            logger.warning("agentwit webhook notification failed: %s", exc)

    async def _send(
        self,
        event: dict[str, Any],
        severity: str,
        pattern: str,
        all_indicators: list[dict[str, Any]],
    ) -> None:
        try:
            import httpx
        except ImportError as err:
            logger.warning(
                "httpx is required for webhook notifications. "
                "Install with: pip install httpx"
            )
            return

        payload = self._build_payload(event, severity, pattern, all_indicators)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.url,
                content=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

    @staticmethod
    def _worst(indicators: list[dict[str, Any]]) -> tuple[str, str]:
        """Return (worst_severity, pattern) from a list of indicators."""
        best_sev = ""
        best_pat = ""
        for ri in indicators:
            sev = ri.get("severity", "low")
            if _SEVERITY_ORDER.get(sev, 0) > _SEVERITY_ORDER.get(best_sev, -1):
                best_sev = sev
                best_pat = ri.get("pattern", "")
        return best_sev or "low", best_pat


def parse_severity_list(raw: str) -> list[str]:
    """Parse a comma-separated severity list from the CLI.

    Example::

        parse_severity_list("HIGH,CRITICAL")  # ["high", "critical"]
    """
    return [s.strip().lower() for s in raw.split(",") if s.strip()]
