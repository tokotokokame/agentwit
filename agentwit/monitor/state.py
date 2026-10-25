"""Hot-reloadable monitoring state.

Bundles the three config-derived pieces the proxy consults per event —
the risk scorer, the redaction settings and the notification hub — behind
one object so a running daemon can swap them atomically on SIGHUP without
restarting the socket.

``reload`` builds the new pieces first and only then assigns them, so a
half-built state is never observed; if building raises, the old state is
kept (the caller decides whether to log).
"""
from __future__ import annotations

from typing import Any

from ..analyzer.scorer import RiskScorer
from ..notifier.hub import NotificationHub


class MonitorState:
    """Mutable container for per-event monitoring behaviour."""

    def __init__(self, config: dict | None) -> None:
        self.scorer: RiskScorer = RiskScorer.from_config(config)
        self.hub: NotificationHub = NotificationHub.from_config(config)
        redact = (config or {}).get("monitor", {}).get("redact", {}) or {}
        self.redact_on: bool = bool(redact.get("enabled", False))
        self.redact_keys: list[str] = redact.get("keys", []) or []

    def reload(self, config: dict | None) -> None:
        """Rebuild from *config*. Raises if the config is unusable — the
        caller keeps the previous state on failure."""
        scorer = RiskScorer.from_config(config)
        hub = NotificationHub.from_config(config)
        redact = (config or {}).get("monitor", {}).get("redact", {}) or {}
        # all built — assign together
        self.scorer = scorer
        self.hub = hub
        self.redact_on = bool(redact.get("enabled", False))
        self.redact_keys = redact.get("keys", []) or []

    def summary(self) -> dict[str, Any]:
        """Small dict for logging what the active state looks like."""
        return {
            "rules_active": len(self.scorer._patterns),
            "redact_on": self.redact_on,
            "notify_routes": len(self.hub._routes),
        }
