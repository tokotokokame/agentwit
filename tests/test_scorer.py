"""Tests for agentwit.analyzer.scorer.RiskScorer."""
import pytest

from agentwit.analyzer.scorer import RiskScorer, RISK_PATTERNS


class TestRiskPatterns:
    """Smoke tests for the module-level RISK_PATTERNS constant."""

    def test_patterns_is_list(self) -> None:
        assert isinstance(RISK_PATTERNS, list)

    def test_each_pattern_is_three_tuple(self) -> None:
        for item in RISK_PATTERNS:
            assert len(item) == 3, f"Expected 3-tuple, got {item!r}"

    def test_expected_patterns_present(self) -> None:
        names = [p[0] for p in RISK_PATTERNS]
        for expected in ("file_write", "shell_exec", "data_exfil", "credential_access"):
            assert expected in names


class TestRiskScorerShellExec:
    """RiskScorer detects shell_exec patterns."""

    def _make_event(self, tool: str, payload: dict | None = None) -> dict:
        return {
            "tool": tool,
            "action": "tools/call",
            "full_payload": payload or {},
            "risk_indicators": [],
        }

    def test_detects_bash_tool(self) -> None:
        scorer = RiskScorer()
        event = self._make_event("bash", {"params": {"cmd": "ls /"}})
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "shell_exec" in patterns

    def test_detects_run_command_tool(self) -> None:
        scorer = RiskScorer()
        event = self._make_event("run_command", {"params": {"cmd": "whoami"}})
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "shell_exec" in patterns

    def test_detects_execute_in_payload(self) -> None:
        scorer = RiskScorer()
        event = self._make_event("some_tool", {"params": {"method": "execute", "cmd": "id"}})
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "shell_exec" in patterns

    def test_shell_exec_severity_is_high(self) -> None:
        scorer = RiskScorer()
        event = self._make_event("bash")
        indicators = scorer.score_event(event)
        for ind in indicators:
            if ind["pattern"] == "shell_exec":
                assert ind["severity"] == "high"

    def test_matched_field_present(self) -> None:
        scorer = RiskScorer()
        event = self._make_event("bash")
        indicators = scorer.score_event(event)
        for ind in indicators:
            assert "matched" in ind
            assert ind["matched"]  # non-empty


class TestRiskScorerBenignEvents:
    """RiskScorer returns empty list for benign events."""

    def test_benign_tools_list(self) -> None:
        scorer = RiskScorer()
        event = {
            "tool": None,
            "action": "tools/list",
            "full_payload": {"params": {}, "result": {"tools": ["read_file"]}},
            "risk_indicators": [],
        }
        indicators = scorer.score_event(event)
        assert indicators == []

    def test_benign_get_resource(self) -> None:
        scorer = RiskScorer()
        event = {
            "tool": "get_resource",
            "action": "resources/read",
            "full_payload": {"params": {"uri": "docs://readme"}, "result": {"content": "hello"}},
            "risk_indicators": [],
        }
        indicators = scorer.score_event(event)
        assert indicators == []


class TestRiskScorerOtherPatterns:
    """RiskScorer detects file_write, data_exfil, credential_access patterns."""

    def test_detects_write_file(self) -> None:
        scorer = RiskScorer()
        event = {"tool": "write_file", "action": "tools/call", "full_payload": {}, "risk_indicators": []}
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "file_write" in patterns

    def test_detects_http_request(self) -> None:
        scorer = RiskScorer()
        event = {"tool": "http_request", "action": "tools/call", "full_payload": {}, "risk_indicators": []}
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "data_exfil" in patterns

    def test_detects_credential_in_payload(self) -> None:
        scorer = RiskScorer()
        event = {
            "tool": "some_tool",
            "action": "tools/call",
            "full_payload": {"params": {"api_key": "sk-abc123"}},
            "risk_indicators": [],
        }
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "credential_access" in patterns

    def test_case_insensitive_matching(self) -> None:
        scorer = RiskScorer()
        event = {"tool": "BASH", "action": "tools/call", "full_payload": {}, "risk_indicators": []}
        indicators = scorer.score_event(event)
        patterns = [i["pattern"] for i in indicators]
        assert "shell_exec" in patterns


class TestRiskScorerCustomPatterns:
    """RiskScorer supports custom pattern injection."""

    def test_custom_patterns_used(self) -> None:
        custom = [("custom_pattern", r"my_special_tool", "low")]
        scorer = RiskScorer(patterns=custom)
        event = {"tool": "my_special_tool", "action": "tools/call", "full_payload": {}, "risk_indicators": []}
        indicators = scorer.score_event(event)
        assert len(indicators) == 1
        assert indicators[0]["pattern"] == "custom_pattern"

    def test_empty_custom_patterns(self) -> None:
        scorer = RiskScorer(patterns=[])
        event = {"tool": "bash", "action": "tools/call", "full_payload": {}, "risk_indicators": []}
        assert scorer.score_event(event) == []
