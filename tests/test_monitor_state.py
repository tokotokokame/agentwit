"""Tests for MonitorState hot-reload and the daemon CLI wiring."""
from __future__ import annotations

from agentwit.monitor.state import MonitorState


def test_initial_state_from_config():
    st = MonitorState({"monitor": {"rules": {"shell_exec": False}}})
    assert st.redact_on is False  # not set in this config
    assert all(p[0] != "shell_exec" for p in st.scorer._patterns)


def test_reload_swaps_rules_and_redact():
    st = MonitorState(None)
    before = len(st.scorer._patterns)
    st.reload({"monitor": {
        "rules": {"shell_exec": False, "persistence": False},
        "redact": {"enabled": True, "keys": ["x"]},
    }})
    assert len(st.scorer._patterns) == before - 2
    assert st.redact_on is True
    assert st.redact_keys == ["x"]


def test_reload_rebuilds_hub_routes():
    st = MonitorState(None)
    assert st.hub.active is False
    st.reload({"notify": {"routes": [
        {"kind": "slack", "url": "https://hooks.slack.com/x", "on": ["HIGH"]}
    ]}})
    assert st.hub.active is True


def test_summary_shape():
    s = MonitorState(None).summary()
    assert {"rules_active", "redact_on", "notify_routes"} <= set(s)


def test_daemon_command_registered():
    from agentwit.cli import main
    assert "daemon" in main.commands
