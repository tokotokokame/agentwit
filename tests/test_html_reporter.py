"""Tests for reporter/html_reporter.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwit.reporter.html_reporter import HtmlReporter


def _write_session(tmp_path: Path, events: list[dict]) -> Path:
    session = tmp_path / "session_html_test"
    session.mkdir()
    jsonl = session / "witness.jsonl"
    with open(jsonl, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return session


_chain = None

def _make_event(idx: int, tool: str = "read_file", risk_indicators: list | None = None) -> dict:
    from agentwit.witness.chain import ChainManager

    global _chain
    if idx == 0 or _chain is None:
        _chain = ChainManager(session_id="session_html_test")
    event = {
        "timestamp": f"2024-01-01T00:00:0{idx}.000000",
        "actor": "agent",
        "action": "tools/call",
        "tool": tool,
        "full_payload": {"request": {}},
        "risk_indicators": risk_indicators or [],
        "input_hash": f"in_{idx}",
        "output_hash": f"out_{idx}",
    }
    return _chain.sign(event)


class TestHtmlReporter:
    def test_load_events(self, tmp_path):
        events = [_make_event(i) for i in range(3)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        loaded = reporter.load_events()
        assert len(loaded) == 3

    def test_generate_returns_html(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "Witness Report" in html

    def test_render_alias(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        assert reporter.render() == reporter.generate()

    def test_session_id_in_report(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "session_html_test" in html

    def test_chain_valid_badge(self, tmp_path):
        events = [_make_event(i) for i in range(2)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "VALID" in html

    def test_risk_summary_section(self, tmp_path):
        events = [_make_event(0, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "bash"}])]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "Risk Summary" in html
        assert "shell_exec" in html

    def test_event_timeline_section(self, tmp_path):
        events = [_make_event(0, tool="bash")]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "Event Timeline" in html
        assert "bash" in html

    def test_high_risk_row_highlighted(self, tmp_path):
        events = [_make_event(0, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "bash"}])]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "row-high" in html

    def test_critical_risk_row_highlighted(self, tmp_path):
        events = [_make_event(0, risk_indicators=[{"pattern": "privilege_escalation", "severity": "critical", "matched": "sudo"}])]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "row-critical" in html

    def test_empty_session(self, tmp_path):
        session = _write_session(tmp_path, [])
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "<!DOCTYPE html>" in html
        assert "No events" in html

    def test_dark_theme_css(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        # Dark theme uses --bg variable
        assert "--bg:" in html or "background: #0d1117" in html or "#0d1117" in html

    def test_version_in_footer(self, tmp_path):
        import agentwit
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert agentwit.__version__ in html

    def test_tampered_badge_when_chain_broken(self, tmp_path):
        # Tamper one event
        events = [_make_event(i) for i in range(2)]
        events[1]["witness_id"] = "tampered_id"
        session = _write_session(tmp_path, events)
        reporter = HtmlReporter(session)
        html = reporter.generate()
        assert "TAMPERED" in html
