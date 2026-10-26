"""Build a human-readable summary of a witness session.

Used by `agentwit summary` and by the daemon's end-of-session push, so a
phone (Slack/Discord/email) shows what happened without opening the console.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..notifier.sanitize import clean_field

_SEV = ("critical", "high", "medium", "low")


def _latest_session(home: Path) -> Path | None:
    logs = home / "witness_logs"
    if not logs.is_dir():
        return None
    sessions = sorted((p for p in logs.glob("session_*") if p.is_dir()),
                      key=lambda p: p.name, reverse=True)
    return sessions[0] if sessions else None


def build_summary(home: Path, session: str | None = None) -> dict:
    """Return summary stats for a session (newest if *session* is None)."""
    sess = Path(session) if session else _latest_session(home)
    if not sess or not (sess / "witness.jsonl").exists():
        return {"session": None, "events": 0, "flagged": 0,
                "by_severity": {}, "top_tools": [], "top_patterns": [],
                "first": "", "last": ""}
    sev = Counter()
    tools = Counter()
    patterns = Counter()
    total = flagged = 0
    first = last = ""
    for line in (sess / "witness.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        ts = e.get("timestamp", "")
        if ts:
            first = first or ts
            last = ts
        inds = e.get("risk_indicators") or []
        if inds:
            flagged += 1
            worst = max((str(i.get("severity", "low")).lower() for i in inds),
                        key=lambda s: _SEV[::-1].index(s) if s in _SEV else 0)
            sev[worst] += 1
            if e.get("tool"):
                tools[e["tool"]] += 1
            for i in inds:
                if i.get("pattern"):
                    patterns[i["pattern"]] += 1
    return {
        "session": sess.name,
        "events": total,
        "flagged": flagged,
        "by_severity": {s: sev.get(s, 0) for s in _SEV if sev.get(s)},
        "top_tools": tools.most_common(5),
        "top_patterns": patterns.most_common(5),
        "first": first,
        "last": last,
    }


def format_summary(s: dict) -> str:
    """Render a summary dict as a short plain-text block."""
    if not s.get("session"):
        return "agentwit: no witness session found yet."
    lines = [
        f"agentwit summary — {clean_field(s['session'])}",
        f"events: {s['events']}   flagged: {s['flagged']}",
    ]
    if s["by_severity"]:
        lines.append("by severity: " +
                     ", ".join(f"{k.upper()} {v}" for k, v in s["by_severity"].items()))
    if s["top_tools"]:
        lines.append("top tools: " +
                     ", ".join(f"{clean_field(t, 40)}×{n}" for t, n in s["top_tools"]))
    if s["top_patterns"]:
        lines.append("top patterns: " +
                     ", ".join(f"{clean_field(p, 40)}×{n}" for p, n in s["top_patterns"]))
    if s["first"]:
        lines.append(f"window: {clean_field(s['first'])} → {clean_field(s['last'])}")
    return "\n".join(lines)
