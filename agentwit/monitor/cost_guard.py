"""Cost and rate-limit guard for MCP sessions."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CostGuard:
    """Check session statistics against cost/rate thresholds.

    Args:
        per_call_usd: Alert threshold for a single call cost (USD).
        per_session_usd: Alert threshold for total session cost (USD).
        calls_per_minute: Alert threshold for call rate.

    Example::

        guard = CostGuard()
        alerts = guard.check({
            "call_cost_usd": 0.15,
            "total_cost_usd": 0.80,
            "calls_per_minute": 35,
        })
    """

    per_call_usd: float = 0.10
    per_session_usd: float = 1.00
    calls_per_minute: int = 30

    def check(self, session_stats: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate *session_stats* against all thresholds.

        Args:
            session_stats: Dict that may contain any of:
                - ``call_cost_usd`` (float): cost of the most recent call.
                - ``total_cost_usd`` (float): accumulated session cost.
                - ``calls_per_minute`` (float | int): current call rate.

        Returns:
            List of alert dicts.  Each dict has keys:

            - ``type``: alert identifier string.
            - ``threshold``: the configured limit that was exceeded.
            - ``actual``: the observed value.
            - ``message``: human-readable description.
        """
        alerts: list[dict[str, Any]] = []

        call_cost = session_stats.get("call_cost_usd")
        if call_cost is not None and call_cost > self.per_call_usd:
            alerts.append({
                "type": "per_call_cost_exceeded",
                "threshold": self.per_call_usd,
                "actual": call_cost,
                "message": (
                    f"Single call cost ${call_cost:.4f} exceeds limit ${self.per_call_usd:.4f}"
                ),
            })

        total_cost = session_stats.get("total_cost_usd")
        if total_cost is not None and total_cost > self.per_session_usd:
            alerts.append({
                "type": "per_session_cost_exceeded",
                "threshold": self.per_session_usd,
                "actual": total_cost,
                "message": (
                    f"Session cost ${total_cost:.4f} exceeds limit ${self.per_session_usd:.4f}"
                ),
            })

        cpm = session_stats.get("calls_per_minute")
        if cpm is not None and cpm > self.calls_per_minute:
            alerts.append({
                "type": "call_rate_exceeded",
                "threshold": self.calls_per_minute,
                "actual": cpm,
                "message": (
                    f"Call rate {cpm} calls/min exceeds limit {self.calls_per_minute} calls/min"
                ),
            })

        return alerts


class AnomalyDetector:
    def __init__(self):
        self._call_times: deque = deque(maxlen=100)
        self._tool_counts: dict = {}

    def record_call(self, tool_name: str):
        self._call_times.append(datetime.utcnow())
        self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1

    def check_anomalies(self) -> list:
        alerts = []
        now = datetime.utcnow()

        # 直近1分間の呼び出し数
        recent = [t for t in self._call_times
                  if now - t < timedelta(minutes=1)]
        if len(recent) > 30:
            alerts.append({
                "type":      "call_rate_anomaly",
                "severity":  "HIGH",
                "calls_per_minute": len(recent)
            })

        # 同一ツールへの連続呼び出し
        for tool, count in self._tool_counts.items():
            if count > 10:
                alerts.append({
                    "type":     "repeated_tool_call",
                    "severity": "MEDIUM",
                    "tool":     tool,
                    "count":    count
                })
        return alerts
