"""Tests for analyzer/timeline.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwit.analyzer.timeline import (
    Timeline,
    build_timeline,
    diff_sessions,
    load_session,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_session(tmp_path: Path, events: list[dict]) -> Path:
    session_dir = tmp_path / "session_test"
    session_dir.mkdir(parents=True, exist_ok=True)
    jsonl = session_dir / "witness.jsonl"
    with open(jsonl, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return session_dir


def _make_event(
    idx: int,
    tool: str = "read_file",
    action: str = "tools/call",
    actor: str = "agent",
    risk_indicators: list | None = None,
    timestamp: str | None = None,
) -> dict:
    ts = timestamp or f"2024-01-01T00:00:0{idx}.000000"
    return {
        "timestamp": ts,
        "actor": actor,
        "action": action,
        "tool": tool,
        "full_payload": {"request": {"method": action}},
        "risk_indicators": risk_indicators or [],
        "input_hash": f"hash_in_{idx}",
        "output_hash": f"hash_out_{idx}",
        "witness_id": f"wid_{idx}",
        "session_chain": f"chain_{idx}",
        "index": idx,
    }


# ---------------------------------------------------------------------------
# load_session
# ---------------------------------------------------------------------------

class TestLoadSession:
    def test_loads_events(self, tmp_path):
        events = [_make_event(i) for i in range(3)]
        session = _write_session(tmp_path, events)
        loaded = load_session(session)
        assert len(loaded) == 3
        assert loaded[0]["action"] == "tools/call"

    def test_missing_file_raises(self, tmp_path):
        empty = tmp_path / "empty_session"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            load_session(empty)

    def test_empty_file(self, tmp_path):
        session = tmp_path / "s"
        session.mkdir()
        (session / "witness.jsonl").write_text("")
        assert load_session(session) == []


# ---------------------------------------------------------------------------
# build_timeline
# ---------------------------------------------------------------------------

class TestBuildTimeline:
    def test_empty_returns_defaults(self):
        tl = build_timeline([])
        assert tl["total_events"] == 0
        assert tl["start_time"] is None
        assert tl["entries"] == []

    def test_single_event(self):
        e = _make_event(0, tool="bash", timestamp="2024-01-01T10:00:00")
        tl = build_timeline([e])
        assert tl["total_events"] == 1
        assert tl["start_time"] == "2024-01-01T10:00:00"
        assert tl["end_time"] == "2024-01-01T10:00:00"
        assert tl["duration_seconds"] == 0.0

    def test_duration_computed(self):
        e0 = _make_event(0, timestamp="2024-01-01T10:00:00")
        e1 = _make_event(1, timestamp="2024-01-01T10:00:30")
        tl = build_timeline([e0, e1])
        assert tl["duration_seconds"] == 30.0

    def test_actors_tools_actions_deduped(self):
        events = [
            _make_event(0, tool="bash", actor="a"),
            _make_event(1, tool="bash", actor="b"),
            _make_event(2, tool="read_file", actor="a"),
        ]
        tl = build_timeline(events)
        assert sorted(tl["actors"]) == ["a", "b"]
        assert sorted(tl["tools_used"]) == ["bash", "read_file"]

    def test_entries_have_required_fields(self):
        tl = build_timeline([_make_event(0)])
        entry = tl["entries"][0]
        for key in ("index", "timestamp", "actor", "action", "tool", "risk_count", "has_high_risk"):
            assert key in entry

    def test_high_risk_flag(self):
        e = _make_event(0, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "bash"}])
        tl = build_timeline([e])
        assert tl["entries"][0]["has_high_risk"] is True

    def test_worst_severity_critical(self):
        e = _make_event(0, risk_indicators=[
            {"pattern": "privilege_escalation", "severity": "critical", "matched": "sudo"},
        ])
        tl = build_timeline([e])
        assert tl["entries"][0]["worst_severity"] == "critical"


# ---------------------------------------------------------------------------
# diff_sessions
# ---------------------------------------------------------------------------

class TestDiffSessions:
    def test_identical_sessions(self, tmp_path):
        events = [_make_event(i) for i in range(2)]
        s1 = _write_session(tmp_path / "a", events)
        s2 = _write_session(tmp_path / "b", events)
        d = diff_sessions(s1, s2)
        assert d["diff"]["event_count_change"] == 0
        assert d["diff"]["tools_added"] == []
        assert d["diff"]["tools_removed"] == []

    def test_session_b_has_extra_tool(self, tmp_path):
        ea = [_make_event(0, tool="read_file")]
        eb = [_make_event(0, tool="read_file"), _make_event(1, tool="write_file")]
        s1 = _write_session(tmp_path / "a", ea)
        s2 = _write_session(tmp_path / "b", eb)
        d = diff_sessions(s1, s2)
        assert d["diff"]["event_count_change"] == 1
        assert "write_file" in d["diff"]["tools_added"]

    def test_session_a_has_extra_tool(self, tmp_path):
        ea = [_make_event(0, tool="bash"), _make_event(1, tool="nmap")]
        eb = [_make_event(0, tool="bash")]
        s1 = _write_session(tmp_path / "a", ea)
        s2 = _write_session(tmp_path / "b", eb)
        d = diff_sessions(s1, s2)
        assert "nmap" in d["diff"]["tools_removed"]

    def test_risk_changes_tracked(self, tmp_path):
        ea = [_make_event(0, risk_indicators=[{"severity": "high", "pattern": "shell_exec", "matched": "bash"}])]
        eb = [_make_event(0, risk_indicators=[])]
        s1 = _write_session(tmp_path / "a", ea)
        s2 = _write_session(tmp_path / "b", eb)
        d = diff_sessions(s1, s2)
        # risk_counts are computed from indicator lists
        assert d["session_a"]["risk_counts"]["high"] >= 1
        assert d["session_b"]["risk_counts"]["high"] == 0

    def test_input_hash_changes_detected(self, tmp_path):
        e1 = _make_event(0, tool="bash")
        e1["input_hash"] = "aaaa"
        e2 = _make_event(0, tool="bash")
        e2["input_hash"] = "bbbb"
        s1 = _write_session(tmp_path / "a", [e1])
        s2 = _write_session(tmp_path / "b", [e2])
        d = diff_sessions(s1, s2)
        assert d["diff"]["tool_comparison"]["bash"]["input_changes"][0]["input_hash_a"] == "aaaa"
        assert d["diff"]["tool_comparison"]["bash"]["input_changes"][0]["input_hash_b"] == "bbbb"


# ---------------------------------------------------------------------------
# Legacy Timeline class
# ---------------------------------------------------------------------------

class TestTimelineClass:
    def test_build_returns_entries(self):
        events = [_make_event(i) for i in range(2)]
        tl = Timeline(events)
        entries = tl.build()
        assert len(entries) == 2

    def test_render_text_string(self):
        tl = Timeline([_make_event(0)])
        text = tl.render_text()
        assert "Timeline" in text
        assert "tools/call" in text
