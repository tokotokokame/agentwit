"""Risk scoring for witness log events.

Scans event tool names and payloads against a set of known risk patterns
and returns structured risk indicators.
"""
from __future__ import annotations

import json
import re

# Each tuple: (pattern_name, regex, severity)
RISK_PATTERNS: list[tuple[str, str, str]] = [
    ("file_write", r"write_file|create_file|edit_file", "medium"),
    ("shell_exec", r"run_command|execute|bash|shell", "high"),
    ("data_exfil", r"http_request|fetch|curl|wget", "medium"),
    ("credential_access", r"password|token|secret|api_key", "high"),
]


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
            - ``severity``: ``"low"``, ``"medium"``, or ``"high"``.
            - ``matched``: The specific substring that triggered the match.
        """
        tool: str = event.get("tool") or ""
        payload_text: str = json.dumps(event.get("full_payload", {}), default=str)
        haystack = f"{tool} {payload_text}"

        indicators: list[dict] = []
        for name, regex, severity in self._compiled:
            m = regex.search(haystack)
            if m:
                indicators.append({
                    "pattern": name,
                    "severity": severity,
                    "matched": m.group(0),
                })

        return indicators
