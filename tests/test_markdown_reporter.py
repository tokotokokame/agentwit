"""Tests for reporter/markdown_reporter.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwit.reporter.markdown_reporter import MarkdownReporter


def _write_session(tmp_path: Path, events: list[dict], name: str = "session_md_test") -> Path:
    session = tmp_path / name
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
        _chain = ChainManager(session_id="session_md_test")
    event = {
        "timestamp": f"2024-01-01T00:00:0{idx}.000000",
        "actor": "agent",
        "action": "tools/call",
        "tool": tool,
        "full_payload": {},
        "risk_indicators": risk_indicators or [],
        "input_hash": f"in_{idx}",
        "output_hash": f"out_{idx}",
    }
    return _chain.sign(event)


class TestMarkdownReporter:
    def test_load_events(self, tmp_path):
        events = [_make_event(i) for i in range(3)]
        session = _write_session(tmp_path, events)
        reporter = MarkdownReporter(session)
        loaded = reporter.load_events()
        assert len(loaded) == 3

    def test_generate_returns_markdown(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert md.startswith("# Witness Report:")

    def test_render_alias(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        r = MarkdownReporter(session)
        assert r.render() == r.generate()

    def test_summary_section(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "## Summary" in md
        assert "Chain Integrity" in md
        assert "Total Events" in md

    def test_risk_indicators_section(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "## Risk Indicators" in md
        assert "CRITICAL" in md
        assert "HIGH" in md

    def test_event_timeline_section(self, tmp_path):
        events = [_make_event(0, tool="bash")]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "## Event Timeline" in md
        assert "bash" in md

    def test_chain_verification_section(self, tmp_path):
        events = [_make_event(i) for i in range(2)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "## Chain Verification" in md

    def test_valid_chain_shows_checkmark(self, tmp_path):
        events = [_make_event(i) for i in range(2)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "✅" in md

    def test_tampered_chain_shows_x(self, tmp_path):
        events = [_make_event(i) for i in range(2)]
        events[1]["witness_id"] = "tampered"
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "❌" in md

    def test_high_risk_event_flagged(self, tmp_path):
        events = [_make_event(0, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "bash"}])]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "🟠" in md or "HIGH" in md

    def test_pattern_frequency_table(self, tmp_path):
        events = [
            _make_event(0, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "bash"}]),
            _make_event(1, risk_indicators=[{"pattern": "shell_exec", "severity": "high", "matched": "sh"}]),
        ]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "shell_exec" in md
        assert "Pattern Frequency" in md

    def test_session_id_in_header(self, tmp_path):
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "session_md_test" in md

    def test_version_in_footer(self, tmp_path):
        import agentwit
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert agentwit.__version__ in md

    def test_empty_session(self, tmp_path):
        session = _write_session(tmp_path, [])
        md = MarkdownReporter(session).generate()
        assert "# Witness Report:" in md

    def test_table_format_github_compatible(self, tmp_path):
        """Verify tables use pipe syntax."""
        events = [_make_event(0)]
        session = _write_session(tmp_path, events)
        md = MarkdownReporter(session).generate()
        assert "|---" in md or "| ---" in md
