"""Risk scoring for witness log events.

Scans event tool names and payloads against a set of known risk patterns
and returns structured risk indicators.
"""
from __future__ import annotations

import json
import re
from typing import Any

# Each tuple: (pattern_name, regex, severity)
RISK_PATTERNS: list[tuple[str, str, str]] = [
    # --- existing patterns ---
    ("file_write", r"write_file|create_file|edit_file|overwrite", "medium"),
    ("shell_exec", r"run_command|execute|bash|shell|subprocess|popen|eval", "high"),
    ("data_exfil", r"http_request|fetch|curl|wget|requests\.get|requests\.post", "medium"),
    ("credential_access", r"password|token|secret|api_key|apikey|bearer|credentials|private_key", "high"),
    # --- new Phase 2 patterns ---
    ("credential_access_extended", r"\.env|keystore|\.pem|\.p12|\.pfx|id_rsa|id_ed25519|aws_access|gcp_key", "high"),
    ("data_exfiltration", r"https?://(?!localhost|127\.|0\.0\.0\.0)[a-zA-Z0-9].*?(upload|send|post|put|exfil|dump)", "high"),
    ("persistence", r"crontab|systemctl\s+enable|/etc/init\.d|launchctl|schtasks|at\s+\d|rc\.local|autostart", "high"),
    ("lateral_movement", r"nmap|masscan|ping\s+-[cC]|arp\s+-[an]|netstat|ss\s+-[tn]|/etc/hosts|host\s+discovery", "high"),
    ("privilege_escalation", r"\bsudo\b|setuid|suid|chmod\s+[0-9]*[4-7][0-9]{2}|chown\s+root|visudo|/etc/sudoers|pkexec", "critical"),
]

# Severity ordering for comparisons
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class RiskScorer:
    """Score a witness log event against known risk patterns.

    Each pattern is matched against the tool name and the serialised
    full_payload of the event.  Matching is case-insensitive.

    Example::

        scorer = RiskScorer()
        indicators = scorer.score_event(event)
        for ind in indicators:
            print(ind["pattern"], ind["severity"], ind["matched"])
    """

    def __init__(self, patterns: list[tuple[str, str, str]] | None = None) -> None:
        """Initialise the RiskScorer.

        Args:
            patterns: Optional override for the default :data:`RISK_PATTERNS`
                list.  Each element must be a tuple of
                ``(name, regex_pattern, severity)``.
        """
        self._patterns = patterns if patterns is not None else RISK_PATTERNS
        self._compiled = [
            (name, re.compile(regex, re.IGNORECASE), severity)
            for name, regex, severity in self._patterns
        ]

    def score_event(self, event: dict) -> list[dict]:
        """Score a single event and return a list of risk indicator dicts.

        The tool name and the full serialised payload are both scanned.

        Args:
            event: A signed witness log event dict.

        Returns:
            A (possibly empty) list of dicts, each with keys:

            - ``pattern``: The pattern name that matched.
            - ``severity``: ``"low"``, ``"medium"``, ``"high"``, or ``"critical"``.
            - ``matched``: The specific substring that triggered the match.
        """
        tool: str = event.get("tool") or ""
        payload_text: str = json.dumps(event.get("full_payload", {}), default=str)
        haystack = f"{tool} {payload_text}"

        indicators: list[dict] = []
        seen_patterns: set[str] = set()
        for name, regex, severity in self._compiled:
            if name in seen_patterns:
                continue
            m = regex.search(haystack)
            if m:
                indicators.append({
                    "pattern": name,
                    "severity": severity,
                    "matched": m.group(0),
                })
                seen_patterns.add(name)

        return indicators

    def score_session(self, events: list[dict]) -> dict[str, Any]:
        """Score an entire session and return a risk summary.

        Analyses all events and detects patterns including consecutive
        high-risk events that may indicate a coordinated attack chain.

        Args:
            events: Ordered list of witness log event dicts.

        Returns:
            A dict with keys:

            - ``total_events``: int
            - ``risk_level``: overall session level (CRITICAL/HIGH/MEDIUM/LOW)
            - ``counts``: dict mapping severity label → count of *events* at that level
            - ``indicators_total``: total number of matched indicators across all events
            - ``high_risk_events``: list of (index, event) tuples for events with
              HIGH or CRITICAL indicators
            - ``consecutive_high_risk``: list of runs of consecutive high-risk event
              indices (runs of length ≥ 2 are flagged)
            - ``pattern_frequency``: dict mapping pattern name → hit count
        """
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        indicators_total = 0
        high_risk_events: list[tuple[int, dict]] = []
        pattern_frequency: dict[str, int] = {}
        consecutive_runs: list[list[int]] = []
        current_run: list[int] = []

        for idx, event in enumerate(events):
            indicators = self.score_event(event)
            indicators_total += len(indicators)

            event_max_severity = "low"
            for ind in indicators:
                sev = ind["severity"]
                pattern_frequency[ind["pattern"]] = pattern_frequency.get(ind["pattern"], 0) + 1
                if _SEVERITY_ORDER.get(sev, 0) > _SEVERITY_ORDER.get(event_max_severity, 0):
                    event_max_severity = sev

            if indicators:
                counts[event_max_severity] = counts.get(event_max_severity, 0) + 1
                if _SEVERITY_ORDER.get(event_max_severity, 0) >= _SEVERITY_ORDER["high"]:
                    high_risk_events.append((idx, event))
                    current_run.append(idx)
                else:
                    if len(current_run) >= 2:
                        consecutive_runs.append(current_run)
                    current_run = []
            else:
                if len(current_run) >= 2:
                    consecutive_runs.append(current_run)
                current_run = []

        if len(current_run) >= 2:
            consecutive_runs.append(current_run)

        # Determine overall session risk level
        if counts["critical"] > 0:
            risk_level = "CRITICAL"
        elif counts["high"] > 0:
            risk_level = "HIGH"
        elif counts["medium"] > 0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "total_events": len(events),
            "risk_level": risk_level,
            "counts": counts,
            "indicators_total": indicators_total,
            "high_risk_events": high_risk_events,
            "consecutive_high_risk": consecutive_runs,
            "pattern_frequency": pattern_frequency,
        }
