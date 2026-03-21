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

# Prompt-injection specific patterns — used by score_for_injection()
PROMPT_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (
        "instruction_override",
        r"ignore\s+(?:all\s+)?(?:previous\s+|above\s+|prior\s+)?(?:instructions?|prompts?|context|rules?)|"
        r"disregard\s+(?:all\s+)?(?:previous\s+|above\s+|prior\s+)?(?:instructions?|prompts?|context|rules?)|"
        r"forget\s+(?:everything|all|what\s+you\s+were\s+told)|"
        r"new\s+(?:instructions?|directives?|rules?|system\s+prompt)",
        "critical",
    ),
    (
        "role_hijack",
        r"you\s+are\s+(?:now\s+)?(?:a\s+|an\s+)?(?:different\s+|new\s+)?(?:ai|assistant|bot|model|gpt|llm)\b|"
        r"act\s+as\s+(?:a\s+|an\s+|the\s+)?(?:different\s+|new\s+)?(?:ai|assistant|bot|jailbroken|unrestricted)|"
        r"pretend\s+(?:you\s+are|to\s+be)|"
        r"your\s+(?:true\s+|real\s+|actual\s+)?(?:identity|purpose|role|goal)\s+is",
        "critical",
    ),
    (
        "jailbreak",
        r"\bdan\b.*?mode|do\s+anything\s+now|jailbr(?:eak(?:ed)?|oken)\b|"
        r"developer\s+mode|unrestricted\s+mode|no\s+(?:restrictions?|limits?|filters?|guidelines?)|"
        r"bypass\s+(?:safety|filter|restriction|alignment|guardrail)|"
        r"without\s+(?:ethical|moral|safety)\s+(?:constraints?|restrictions?|guidelines?)",
        "critical",
    ),
    (
        "hidden_instruction",
        r"<!--.*?-->|"
        r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>|"
        r"<system>|<\/system>|"
        r"(?:\x00|\x01|\x02|\x03|\x04|\x05|\x06|\x07|\x08|\x0b|\x0c|\x0e|\x0f)"
        r"|\u200b|\u200c|\u200d|\ufeff",
        "high",
    ),
    (
        "data_extraction",
        r"(?:print|output|repeat|show|reveal|display|return|send)\s+(?:me\s+)?(?:all\s+|every\s+|your\s+|the\s+)?"
        r"(?:system\s+prompt|instructions?|context|config|secrets?|passwords?|tokens?|api.?keys?|"
        r"training\s+data|conversation\s+history|private|internal|confidential)|"
        r"(?:tell|give)\s+me\s+(?:all\s+|your\s+|the\s+)?"
        r"(?:system\s+prompt|instructions?|secrets?|passwords?|tokens?|api.?keys?)",
        "high",
    ),
    (
        "tool_abuse",
        r"call\s+(?:the\s+|a\s+|any\s+)?tool|invoke\s+(?:the\s+|a\s+|any\s+)?tool|"
        r"use\s+(?:the\s+|a\s+|any\s+)?tool\s+(?:to\s+)?(?:delete|remove|drop|destroy|exfil|steal|bypass)|"
        r"execute\s+(?:without|bypassing)\s+(?:permission|authorization|approval|confirmation)|"
        r"run\s+(?:this\s+|the\s+)?(?:command|script|code)\s+(?:silently|without|bypassing)",
        "medium",
    ),
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

    def score_for_injection(self, text: str) -> list[dict]:
        """Scan *text* for prompt-injection patterns.

        Unlike :meth:`score_event`, this method operates on a raw string and
        uses the dedicated :data:`PROMPT_INJECTION_PATTERNS` list rather than
        the general risk patterns.

        Args:
            text: Arbitrary text to scan (e.g. a user message or tool output).

        Returns:
            A (possibly empty) list of dicts, each with keys:

            - ``pattern``: The injection pattern name that matched.
            - ``severity``: ``"medium"``, ``"high"``, or ``"critical"``.
            - ``matched``: The specific substring that triggered the match.
        """
        compiled = [
            (name, re.compile(regex, re.IGNORECASE | re.DOTALL), severity)
            for name, regex, severity in PROMPT_INJECTION_PATTERNS
        ]

        indicators: list[dict] = []
        seen: set[str] = set()
        for name, regex, severity in compiled:
            if name in seen:
                continue
            m = regex.search(text)
            if m:
                indicators.append({
                    "pattern": name,
                    "severity": severity,
                    "matched": m.group(0),
                })
                seen.add(name)

        return indicators
