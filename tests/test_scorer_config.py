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


# --- introspection skipping (tools/list false-positive fix) ----------------

# A catalogue whose tool metadata legitimately contains security keywords.
_CATALOG_EV = {
    "action": "tools/list",
    "tool": None,
    "full_payload": {"result": {"tools": [
        {"name": "cloud-scan",
         "inputSchema": {"properties": {"credentials": {"type": "object"}}}},
        {"name": "htb-advisor", "description": "needs an nmap result"},
    ]}},
}


def test_introspection_not_scored_by_default():
    # tools/list catalogue must not raise credential_access / lateral_movement
    assert RiskScorer().score_event(_CATALOG_EV) == []


def test_introspection_scored_when_opted_in():
    pats = _pats_ev(RiskScorer(score_introspection=True), _CATALOG_EV)
    assert "credential_access" in pats and "lateral_movement" in pats


def test_tools_call_still_scored():
    # the real action path is unaffected: a tools/call with a flagged arg scores
    ev = {"action": "tools/call", "tool": "run_command",
          "full_payload": {"params": {"arguments": {"cmd": "bash -lc id"}}}}
    assert "shell_exec" in _pats_ev(RiskScorer(), ev)


def test_from_config_passes_score_introspection():
    cfg = {"monitor": {"score_introspection": True}}
    assert RiskScorer.from_config(cfg).score_event(_CATALOG_EV) != []


def _pats_ev(scorer, ev) -> set:
    return {i["pattern"] for i in scorer.score_event(ev)}
