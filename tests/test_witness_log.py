"""Tests for agentwit.witness.log.WitnessLogger."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentwit.witness.log import WitnessLogger, _sha256


class TestWitnessLoggerInit:
    """Tests for WitnessLogger initialisation."""

    def test_creates_session_directory(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path, actor="test-agent")
        assert logger.session_path.exists()
        assert logger.session_path.is_dir()
        logger.close()

    def test_session_id_format(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        assert logger.session_id.startswith("session_")
        logger.close()

    def test_creates_jsonl_file(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        log_path = logger.session_path / "witness.jsonl"
        assert log_path.exists()
        logger.close()

    def test_actor_stored(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path, actor="my-agent")
        assert logger.actor == "my-agent"
        logger.close()


class TestWitnessLoggerLogEvent:
    """Tests for WitnessLogger.log_event()."""

    def test_returns_signed_event(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path, actor="test")
        event = logger.log_event(
            action="tools/list",
            tool=None,
            full_payload={"params": {}, "result": {"tools": []}},
        )
        assert "witness_id" in event
        assert "session_chain" in event
        logger.close()

    def test_event_written_to_jsonl(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        logger.log_event("tools/list", None, {"params": {}})
        logger.close()

        log_path = logger.session_path / "witness.jsonl"
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["action"] == "tools/list"

    def test_multiple_events_appended(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        for i in range(5):
            logger.log_event(f"action_{i}", None, {})
        logger.close()

        log_path = logger.session_path / "witness.jsonl"
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_actor_present_in_event(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path, actor="my-agent")
        event = logger.log_event("tools/call", "bash", {"params": {"cmd": "ls"}})
        assert event["actor"] == "my-agent"
        logger.close()

    def test_tool_present_in_event(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        event = logger.log_event("tools/call", "read_file", {"params": {}})
        assert event["tool"] == "read_file"
        logger.close()

    def test_input_hash_computed_from_params(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        params = {"path": "/tmp/test.txt"}
        event = logger.log_event("tools/call", "read_file", {"params": params})
        assert event["input_hash"] == _sha256(params)
        logger.close()

    def test_output_hash_computed_from_result(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        result = {"content": "hello"}
        event = logger.log_event("tools/call", "read_file", {"params": {}, "result": result})
        assert event["output_hash"] == _sha256(result)
        logger.close()

    def test_risk_indicators_stored(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        indicators = [{"pattern": "shell_exec", "severity": "high", "matched": "bash"}]
        event = logger.log_event("tools/call", "bash", {}, risk_indicators=indicators)
        assert event["risk_indicators"] == indicators
        logger.close()

    def test_timestamp_present(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        event = logger.log_event("tools/list", None, {})
        assert "timestamp" in event
        assert event["timestamp"]  # non-empty
        logger.close()

    def test_full_payload_stored(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        payload = {"params": {"x": 1}, "result": {"y": 2}}
        event = logger.log_event("tools/call", "calc", payload)
        assert event["full_payload"] == payload
        logger.close()


class TestWitnessLoggerAsync:
    """Tests for the async alog_event interface."""

    @pytest.mark.asyncio
    async def test_alog_event_returns_signed_event(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        event = await logger.alog_event("tools/list", None, {})
        assert "witness_id" in event
        logger.close()

    @pytest.mark.asyncio
    async def test_alog_event_appends_to_file(self, tmp_path: Path) -> None:
        logger = WitnessLogger(session_dir=tmp_path)
        await logger.alog_event("a1", None, {})
        await logger.alog_event("a2", None, {})
        logger.close()

        log_path = logger.session_path / "witness.jsonl"
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2


class TestSha256Helper:
    """Tests for the _sha256 module-level helper."""

    def test_returns_64_char_hex(self) -> None:
        result = _sha256({"key": "value"})
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        data = {"a": 1, "b": [2, 3]}
        assert _sha256(data) == _sha256(data)

    def test_none_input(self) -> None:
        # Should not raise.
        result = _sha256(None)
        assert len(result) == 64
