"""Tests for session summary build/format and hub summary push."""
from __future__ import annotations

import asyncio
import json

from agentwit.monitor.summary import build_summary, format_summary
from agentwit.notifier.hub import NotificationHub, _Route


def _mk(home, rows):
    sess = home / "witness_logs" / "session_14:00"
    sess.mkdir(parents=True)
    (sess / "witness.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_build_summary_counts(tmp_path):
    _mk(tmp_path, [
        {"timestamp": "2026-10-26T14:00:01Z", "tool": "bash",
         "risk_indicators": [{"pattern": "shell_exec", "severity": "high"}]},
        {"timestamp": "2026-10-26T14:00:02Z", "tool": "bash",
         "risk_indicators": [{"pattern": "privilege_escalation", "severity": "critical"}]},
        {"timestamp": "2026-10-26T14:00:03Z", "tool": "read_file", "risk_indicators": []},
    ])
    s = build_summary(tmp_path)
    assert s["events"] == 3 and s["flagged"] == 2
    assert s["by_severity"]["critical"] == 1 and s["by_severity"]["high"] == 1
    assert s["top_tools"][0] == ("bash", 2)


def test_format_summary_is_plain_text(tmp_path):
    _mk(tmp_path, [{"timestamp": "2026-10-26T14:00:01Z", "tool": "bash",
                    "risk_indicators": [{"pattern": "shell_exec", "severity": "high"}]}])
    text = format_summary(build_summary(tmp_path))
    assert "agentwit summary" in text and "flagged: 1" in text


def test_empty_session_summary(tmp_path):
    assert "no witness session" in format_summary(build_summary(tmp_path))


def test_hub_notify_summary_hits_all_routes():
    got = []

    async def ts(subject, text):
        got.append((subject, text))

    async def run():
        hub = NotificationHub([
            _Route("a", {"high"}, lambda *a: None, ts),
            _Route("b", {"critical"}, lambda *a: None, ts),
        ])
        await hub.notify_summary("agentwit summary", "body")

    asyncio.run(run())
    assert len(got) == 2  # summaries are not severity-gated


def test_summary_sanitizes_tool_names(tmp_path):
    _mk(tmp_path, [{"timestamp": "t", "tool": "bash @channel <!here>",
                    "risk_indicators": [{"pattern": "shell_exec", "severity": "high"}]}])
    text = format_summary(build_summary(tmp_path))
    assert "<!here>" not in text and "@channel" not in text
