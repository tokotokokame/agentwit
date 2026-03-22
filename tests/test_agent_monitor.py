"""Tests for agentwit.integrations.langchain.AgentwitCallback.

Stubs langchain_core so no real install is required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub langchain_core before importing AgentwitCallback
# ---------------------------------------------------------------------------

def _install_langchain_stubs() -> None:
    """Register minimal langchain_core stubs in sys.modules."""
    if "langchain_core" in sys.modules:
        return  # already available (real or previously stubbed)

    class _BaseCallbackHandler:
        """Minimal stub — mirrors the real langchain_core base class."""

    class _LLMResult:
        def __init__(self, generations=None):
            self.generations = generations or []

    class _Generation:
        def __init__(self, text: str = ""):
            self.text = text

    lc = ModuleType("langchain_core")
    lc_cb = ModuleType("langchain_core.callbacks")
    lc_cb_base = ModuleType("langchain_core.callbacks.base")
    lc_outputs = ModuleType("langchain_core.outputs")

    lc_cb_base.BaseCallbackHandler = _BaseCallbackHandler
    lc_outputs.LLMResult = _LLMResult
    lc_outputs.Generation = _Generation

    sys.modules["langchain_core"] = lc
    sys.modules["langchain_core.callbacks"] = lc_cb
    sys.modules["langchain_core.callbacks.base"] = lc_cb_base
    sys.modules["langchain_core.outputs"] = lc_outputs


_install_langchain_stubs()

from agentwit.integrations.langchain import AgentwitCallback  # noqa: E402


# ---------------------------------------------------------------------------
# Stub data objects
# ---------------------------------------------------------------------------

class _AgentAction:
    def __init__(self, tool: str = "search", tool_input=None, log: str = ""):
        self.tool = tool
        self.tool_input = tool_input
        self.log = log


class _AgentFinish:
    def __init__(self, return_values: dict | None = None, log: str = ""):
        self.return_values = return_values or {}
        self.log = log


class _Generation:
    def __init__(self, text: str = ""):
        self.text = text


class _LLMResult:
    def __init__(self, generations=None):
        self.generations = generations or []


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_logger(tmp_path: Path) -> MagicMock:
    """Return a MagicMock WitnessLogger whose session_path is a real tmp dir."""
    logger = MagicMock()
    logger.session_path = tmp_path
    logger.session_id = "session_test_abc123"
    # Make log_event / alog_event no-ops (MagicMock default is fine, but
    # alog_event must not be awaited in a non-async context).
    logger.log_event.return_value = {}
    return logger


@pytest.fixture()
def cb(mock_logger: MagicMock) -> AgentwitCallback:
    return AgentwitCallback(witness_logger=mock_logger)


def _read_audit(tmp_path: Path) -> list[dict]:
    """Read all records from audit.jsonl."""
    audit_path = tmp_path / "audit.jsonl"
    if not audit_path.exists():
        return []
    return [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]


# ===========================================================================
# 1. _extract_thought
# ===========================================================================

class TestExtractThought:
    def test_extracts_react_thought(self) -> None:
        log = "Thought: I need to search for the answer\nAction: search"
        assert AgentwitCallback._extract_thought(log) == "I need to search for the answer"

    def test_returns_empty_when_no_thought(self) -> None:
        log = "Action: bash\nAction Input: ls -la"
        assert AgentwitCallback._extract_thought(log) == ""

    def test_returns_empty_for_none(self) -> None:
        assert AgentwitCallback._extract_thought(None) == ""  # type: ignore[arg-type]

    def test_returns_empty_for_empty_string(self) -> None:
        assert AgentwitCallback._extract_thought("") == ""

    def test_case_insensitive(self) -> None:
        log = "THOUGHT: case insensitive match"
        assert AgentwitCallback._extract_thought(log) == "case insensitive match"

    def test_picks_first_thought_line(self) -> None:
        log = "Thought: first\nThought: second"
        assert AgentwitCallback._extract_thought(log) == "first"


# ===========================================================================
# 2. on_agent_action
# ===========================================================================

class TestOnAgentAction:
    def test_writes_agent_thought_to_audit(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(tool="calculator", tool_input="2+2", log="Thought: do math")
        cb.on_agent_action(action)
        records = _read_audit(tmp_path)
        assert len(records) == 1
        assert records[0]["type"] == "agent_thought"

    def test_thought_extracted_from_react_log(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(log="Thought: need to calculate\nAction: calc")
        cb.on_agent_action(action)
        records = _read_audit(tmp_path)
        assert records[0]["thought"] == "need to calculate"

    def test_no_thought_in_log_does_not_crash(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(log="Action: bash\nAction Input: pwd")
        cb.on_agent_action(action)  # must not raise
        records = _read_audit(tmp_path)
        assert records[0]["thought"] == ""

    def test_tool_selected_field(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(tool="web_search", tool_input="query")
        cb.on_agent_action(action)
        records = _read_audit(tmp_path)
        assert records[0]["tool_selected"] == "web_search"

    def test_reasoning_from_tool_input(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(tool="bash", tool_input="ls /tmp")
        cb.on_agent_action(action)
        records = _read_audit(tmp_path)
        assert records[0]["reasoning"] == "ls /tmp"

    def test_reasoning_empty_when_tool_input_none(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        action = _AgentAction(tool="noop", tool_input=None)
        cb.on_agent_action(action)
        records = _read_audit(tmp_path)
        assert records[0]["reasoning"] == ""

    def test_session_id_in_record(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_agent_action(_AgentAction())
        records = _read_audit(tmp_path)
        assert records[0]["session_id"] == "session_test_abc123"

    def test_timestamp_format(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_agent_action(_AgentAction())
        records = _read_audit(tmp_path)
        ts = records[0]["timestamp"]
        # Must match YYYY-MM-DDTHH:MM:SSZ
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts)


# ===========================================================================
# 3. on_agent_finish
# ===========================================================================

class TestOnAgentFinish:
    def test_writes_agent_finish_to_audit(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        finish = _AgentFinish(return_values={"output": "42"})
        cb.on_agent_finish(finish)
        records = _read_audit(tmp_path)
        assert len(records) == 1
        assert records[0]["type"] == "agent_finish"

    def test_final_answer_from_return_values(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        finish = _AgentFinish(return_values={"output": "Paris"})
        cb.on_agent_finish(finish)
        records = _read_audit(tmp_path)
        assert records[0]["final_answer"] == "Paris"

    def test_final_answer_falls_back_to_log(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        finish = _AgentFinish(return_values={}, log="Final: done")
        cb.on_agent_finish(finish)
        records = _read_audit(tmp_path)
        assert records[0]["final_answer"] == "Final: done"

    def test_thought_extracted_from_log(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        finish = _AgentFinish(log="Thought: final reasoning\nFinal Answer: ok")
        cb.on_agent_finish(finish)
        records = _read_audit(tmp_path)
        assert records[0]["thought"] == "final reasoning"

    def test_no_thought_in_finish_log(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        finish = _AgentFinish(log="Final Answer: done")
        cb.on_agent_finish(finish)
        records = _read_audit(tmp_path)
        assert records[0]["thought"] == ""


# ===========================================================================
# 4. on_llm_start
# ===========================================================================

class TestOnLlmStart:
    def test_writes_llm_start_to_audit(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_llm_start({}, ["Hello, world!"])
        records = _read_audit(tmp_path)
        assert len(records) == 1
        assert records[0]["type"] == "llm_start"

    def test_prompt_truncated_to_100_chars(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        long_prompt = "A" * 200
        cb.on_llm_start({}, [long_prompt])
        records = _read_audit(tmp_path)
        assert records[0]["prompt_preview"] == "A" * 100

    def test_prompt_under_100_not_padded(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_llm_start({}, ["short prompt"])
        records = _read_audit(tmp_path)
        assert records[0]["prompt_preview"] == "short prompt"

    def test_empty_prompts_list_handled(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_llm_start({}, [])  # must not raise
        records = _read_audit(tmp_path)
        assert records[0]["prompt_preview"] == ""

    def test_session_id_in_llm_start(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_llm_start({}, ["hi"])
        records = _read_audit(tmp_path)
        assert records[0]["session_id"] == "session_test_abc123"


# ===========================================================================
# 5. on_llm_end
# ===========================================================================

class TestOnLlmEnd:
    def test_writes_llm_end_to_audit(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        result = _LLMResult(generations=[[_Generation("answer text")]])
        cb.on_llm_end(result)
        records = _read_audit(tmp_path)
        assert len(records) == 1
        assert records[0]["type"] == "llm_end"

    def test_response_truncated_to_100_chars(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        long_text = "B" * 200
        result = _LLMResult(generations=[[_Generation(long_text)]])
        cb.on_llm_end(result)
        records = _read_audit(tmp_path)
        assert records[0]["response_preview"] == "B" * 100

    def test_response_under_100_not_padded(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        result = _LLMResult(generations=[[_Generation("short")]])
        cb.on_llm_end(result)
        records = _read_audit(tmp_path)
        assert records[0]["response_preview"] == "short"

    def test_empty_generations_handled(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        result = _LLMResult(generations=[])
        cb.on_llm_end(result)  # must not raise
        records = _read_audit(tmp_path)
        assert records[0]["type"] == "llm_end"

    def test_session_id_in_llm_end(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        result = _LLMResult(generations=[[_Generation("ok")]])
        cb.on_llm_end(result)
        records = _read_audit(tmp_path)
        assert records[0]["session_id"] == "session_test_abc123"


# ===========================================================================
# 6. Multiple callbacks / chaining
# ===========================================================================

class TestMultipleCallbacks:
    def test_multiple_calls_append_to_audit(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_agent_action(_AgentAction(tool="tool_a"))
        cb.on_agent_action(_AgentAction(tool="tool_b"))
        cb.on_agent_finish(_AgentFinish(return_values={"output": "done"}))
        records = _read_audit(tmp_path)
        assert len(records) == 3
        assert records[0]["type"] == "agent_thought"
        assert records[1]["type"] == "agent_thought"
        assert records[2]["type"] == "agent_finish"

    def test_all_records_share_session_id(self, cb: AgentwitCallback, tmp_path: Path) -> None:
        cb.on_llm_start({}, ["p1"])
        cb.on_agent_action(_AgentAction())
        cb.on_agent_finish(_AgentFinish())
        records = _read_audit(tmp_path)
        assert all(r["session_id"] == "session_test_abc123" for r in records)

    def test_two_independent_callbacks_write_to_their_own_dirs(
        self, tmp_path: Path
    ) -> None:
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        dir_b = tmp_path / "b"
        dir_b.mkdir()

        logger_a = MagicMock()
        logger_a.session_path = dir_a
        logger_a.session_id = "session_a"
        logger_a.log_event.return_value = {}

        logger_b = MagicMock()
        logger_b.session_path = dir_b
        logger_b.session_id = "session_b"
        logger_b.log_event.return_value = {}

        cb_a = AgentwitCallback(witness_logger=logger_a)
        cb_b = AgentwitCallback(witness_logger=logger_b)

        cb_a.on_agent_action(_AgentAction(tool="ta"))
        cb_b.on_agent_action(_AgentAction(tool="tb"))

        recs_a = _read_audit(dir_a)
        recs_b = _read_audit(dir_b)

        assert recs_a[0]["tool_selected"] == "ta"
        assert recs_b[0]["tool_selected"] == "tb"
        assert recs_a[0]["session_id"] == "session_a"
        assert recs_b[0]["session_id"] == "session_b"
