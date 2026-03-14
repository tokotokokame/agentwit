"""Session timeline construction and session comparison.

Provides functions to load, summarise, and diff witness log sessions.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_session(session_path: str | Path) -> list[dict]:
    """Load all events from a session directory.

    Args:
        session_path: Path to the session directory that contains
            ``witness.jsonl``.

    Returns:
        Ordered list of event dicts.

    Raises:
        FileNotFoundError: If ``witness.jsonl`` is not found.
    """
    session_path = Path(session_path)
    jsonl_file = session_path / "witness.jsonl"
    events: list[dict] = []
    with open(jsonl_file, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def build_timeline(events: list[dict]) -> dict[str, Any]:
    """Build a time-series summary from a list of events.

    Args:
        events: Ordered list of witness log event dicts.

    Returns:
        A dict with keys:

        - ``total_events``: int
        - ``start_time``: ISO8601 string of first event (or None)
        - ``end_time``: ISO8601 string of last event (or None)
        - ``duration_seconds``: float or None
        - ``actors``: sorted list of distinct actor names
        - ``tools_used``: sorted list of distinct tool names
        - ``actions``: sorted list of distinct action names
        - ``entries``: list of per-event summary dicts
    """
    if not events:
        return {
            "total_events": 0,
            "start_time": None,
            "end_time": None,
            "duration_seconds": None,
            "actors": [],
            "tools_used": [],
            "actions": [],
            "entries": [],
        }

    entries: list[dict] = []
    actors: set[str] = set()
    tools_used: set[str] = set()
    actions: set[str] = set()

    for i, event in enumerate(events):
        actor = event.get("actor", "unknown")
        action = event.get("action", "")
        tool = event.get("tool", "")
        timestamp = event.get("timestamp", "")
        risk_indicators = event.get("risk_indicators") or []

        actors.add(actor)
        if action:
            actions.add(action)
        if tool:
            tools_used.add(tool)

        has_high_risk = any(
            ri.get("severity") in ("high", "critical") for ri in risk_indicators
        )
        worst_severity = _worst_severity(risk_indicators)

        entries.append({
            "index": i,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "tool": tool,
            "risk_indicators": risk_indicators,
            "risk_count": len(risk_indicators),
            "has_high_risk": has_high_risk,
            "worst_severity": worst_severity,
            "witness_id": event.get("witness_id", ""),
        })

    start_time = events[0].get("timestamp", "")
    end_time = events[-1].get("timestamp", "")
    duration_seconds: float | None = None

    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            duration_seconds = (end_dt - start_dt).total_seconds()
        except ValueError:
            pass

    return {
        "total_events": len(events),
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "actors": sorted(actors),
        "tools_used": sorted(tools_used),
        "actions": sorted(actions),
        "entries": entries,
    }


def diff_sessions(
    session_a: str | Path,
    session_b: str | Path,
) -> dict[str, Any]:
    """Compare two sessions and return a structured diff.

    Compares event counts, tools called, and risk profiles between two
    sessions.  For tools that appear in both sessions the per-tool call
    counts are compared.

    Args:
        session_a: Path to the first session directory.
        session_b: Path to the second session directory.

    Returns:
        A dict with keys:

        - ``session_a``: summary of session A
        - ``session_b``: summary of session B
        - ``diff``: dict describing additions, removals, and changes
    """
    events_a = load_session(session_a)
    events_b = load_session(session_b)

    timeline_a = build_timeline(events_a)
    timeline_b = build_timeline(events_b)

    risk_a = _count_by_severity(events_a)
    risk_b = _count_by_severity(events_b)

    tools_a: set[str] = {e.get("tool", "") for e in events_a if e.get("tool")}
    tools_b: set[str] = {e.get("tool", "") for e in events_b if e.get("tool")}

    tool_calls_a: dict[str, list[dict]] = {}
    for e in events_a:
        t = e.get("tool", "")
        if t:
            tool_calls_a.setdefault(t, []).append(e)

    tool_calls_b: dict[str, list[dict]] = {}
    for e in events_b:
        t = e.get("tool", "")
        if t:
            tool_calls_b.setdefault(t, []).append(e)

    common_tools = tools_a & tools_b
    tool_comparison: dict[str, dict] = {}
    for tool in common_tools:
        calls_a = tool_calls_a.get(tool, [])
        calls_b = tool_calls_b.get(tool, [])
        # Compare input hashes of matching pairs
        input_changes: list[dict] = []
        for idx, (ca, cb) in enumerate(zip(calls_a, calls_b)):
            if ca.get("input_hash") != cb.get("input_hash"):
                input_changes.append({
                    "call_index": idx,
                    "input_hash_a": ca.get("input_hash"),
                    "input_hash_b": cb.get("input_hash"),
                })
        tool_comparison[tool] = {
            "count_a": len(calls_a),
            "count_b": len(calls_b),
            "count_diff": len(calls_b) - len(calls_a),
            "input_changes": input_changes,
        }

    return {
        "session_a": {
            "path": str(session_a),
            "total_events": timeline_a["total_events"],
            "tools_used": timeline_a["tools_used"],
            "risk_counts": risk_a,
            "start_time": timeline_a["start_time"],
            "end_time": timeline_a["end_time"],
        },
        "session_b": {
            "path": str(session_b),
            "total_events": timeline_b["total_events"],
            "tools_used": timeline_b["tools_used"],
            "risk_counts": risk_b,
            "start_time": timeline_b["start_time"],
            "end_time": timeline_b["end_time"],
        },
        "diff": {
            "event_count_change": timeline_b["total_events"] - timeline_a["total_events"],
            "tools_added": sorted(tools_b - tools_a),
            "tools_removed": sorted(tools_a - tools_b),
            "tools_common": sorted(common_tools),
            "tool_comparison": tool_comparison,
            "risk_changes": {
                sev: risk_b.get(sev, 0) - risk_a.get(sev, 0)
                for sev in ("critical", "high", "medium", "low")
            },
        },
    }


# ---------------------------------------------------------------------------
# Legacy class-based API (kept for backwards compatibility)
# ---------------------------------------------------------------------------

class Timeline:
    """Build and display a chronological timeline of witness log events."""

    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def build(self) -> list[dict]:
        """Build and return timeline entries."""
        return build_timeline(self.events)["entries"]

    def render_text(self) -> str:
        """Render the timeline as a human-readable text string."""
        timeline = build_timeline(self.events)
        lines = [
            f"Timeline: {timeline['total_events']} events",
            f"  Period : {timeline['start_time']} → {timeline['end_time']}",
            f"  Actors : {', '.join(timeline['actors']) or '-'}",
            f"  Tools  : {', '.join(timeline['tools_used']) or '-'}",
            "",
        ]
        for entry in timeline["entries"]:
            risk_tag = ""
            if entry["risk_count"]:
                risk_tag = f"  [{entry['worst_severity'].upper()} RISK x{entry['risk_count']}]"
            lines.append(
                f"  [{entry['index']:03d}] {entry['timestamp']}  "
                f"{entry['action']}  tool={entry['tool'] or '-'}{risk_tag}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _worst_severity(risk_indicators: list[dict]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    worst = "none"
    for ri in risk_indicators:
        sev = ri.get("severity", "low")
        if order.get(sev, 0) > order.get(worst, -1):
            worst = sev
    return worst


def _count_by_severity(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for event in events:
        for ri in event.get("risk_indicators") or []:
            sev = ri.get("severity", "low")
            counts[sev] = counts.get(sev, 0) + 1
    return counts
