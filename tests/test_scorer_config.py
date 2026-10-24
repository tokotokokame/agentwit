"""Tests for config-driven RiskScorer (rules on/off, only_tools, from_config)."""
from __future__ import annotations

from agentwit.analyzer.scorer import RiskScorer

EV = {"tool": "bash", "full_payload": {"params": {"command": "sudo su"}}}


def _pats(scorer) -> set[str]:
    return {i["pattern"] for i in scorer.score_event(EV)}


def test_default_detects_both():
    assert {"shell_exec", "privilege_escalation"} <= _pats(RiskScorer())


def test_rule_off_disables_only_that_pattern():
    pats = _pats(RiskScorer(rules={"privilege_escalation": False}))
    assert "privilege_escalation" not in pats
    assert "shell_exec" in pats


def test_unknown_rule_name_leaves_defaults_on():
    # a map that doesn't mention shell_exec must leave it enabled
    assert "shell_exec" in _pats(RiskScorer(rules={"persistence": False}))


def test_only_tools_skips_unlisted_tool():
    assert RiskScorer(only_tools=["read_file"]).score_event(EV) == []


def test_only_tools_allows_listed_tool():
    assert _pats(RiskScorer(only_tools=["bash"]))


def test_from_config_applies_rules_and_tools():
    scorer = RiskScorer.from_config(
        {"monitor": {"rules": {"shell_exec": False}, "only_tools": []}}
    )
    assert "shell_exec" not in _pats(scorer)
    assert "privilege_escalation" in _pats(scorer)


def test_from_config_none_is_default():
    assert {"shell_exec", "privilege_escalation"} <= _pats(RiskScorer.from_config(None))
