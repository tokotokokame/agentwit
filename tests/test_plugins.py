"""Tests for the agentwit plugin system (PluginBase + load_plugins)."""
from __future__ import annotations

import importlib.metadata
from unittest.mock import MagicMock, patch

import pytest

from agentwit.plugins.base import PluginBase
from agentwit.plugins import load_plugins


# ---------------------------------------------------------------------------
# Concrete plugin fixtures
# ---------------------------------------------------------------------------


class _AlwaysAlertPlugin(PluginBase):
    """Always returns one alert — useful for testing scan() integration."""

    @property
    def name(self) -> str:
        return "always-alert"

    @property
    def version(self) -> str:
        return "2.0.0"

    def scan(self, event: dict) -> list[dict]:
        return [
            {
                "pattern": "test_pattern",
                "severity": "high",
                "description": "Test alert",
            }
        ]


class _NeverAlertPlugin(PluginBase):
    """Always returns an empty list."""

    def scan(self, event: dict) -> list[dict]:
        return []


class _MultiAlertPlugin(PluginBase):
    """Returns multiple alerts per event."""

    def scan(self, event: dict) -> list[dict]:
        return [
            {"pattern": "p1", "severity": "low", "description": "low alert"},
            {"pattern": "p2", "severity": "critical", "description": "critical alert"},
        ]


# ---------------------------------------------------------------------------
# PluginBase tests
# ---------------------------------------------------------------------------


class TestPluginBase:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            PluginBase()  # type: ignore[abstract]

    def test_name_defaults_to_classname_lower(self):
        plugin = _NeverAlertPlugin()
        assert plugin.name == "_neveralertplugin"

    def test_version_defaults_to_0_1_0(self):
        plugin = _NeverAlertPlugin()
        assert plugin.version == "0.1.0"

    def test_custom_name(self):
        plugin = _AlwaysAlertPlugin()
        assert plugin.name == "always-alert"

    def test_custom_version(self):
        plugin = _AlwaysAlertPlugin()
        assert plugin.version == "2.0.0"

    def test_scan_returns_list(self):
        plugin = _AlwaysAlertPlugin()
        result = plugin.scan({"action": "tools/call"})
        assert isinstance(result, list)

    def test_scan_empty_event(self):
        plugin = _NeverAlertPlugin()
        assert plugin.scan({}) == []

    def test_scan_alert_has_required_keys(self):
        plugin = _AlwaysAlertPlugin()
        alerts = plugin.scan({"action": "tools/call", "tool": "bash"})
        assert len(alerts) == 1
        alert = alerts[0]
        assert "pattern" in alert
        assert "severity" in alert
        assert "description" in alert

    def test_scan_multiple_alerts(self):
        plugin = _MultiAlertPlugin()
        alerts = plugin.scan({})
        assert len(alerts) == 2
        assert alerts[0]["severity"] == "low"
        assert alerts[1]["severity"] == "critical"

    def test_scan_no_alert_on_clean_event(self):
        plugin = _NeverAlertPlugin()
        event = {
            "action": "tools/call",
            "tool": "read_file",
            "full_payload": {"params": {"path": "/tmp/safe.txt"}, "result": {}},
        }
        assert plugin.scan(event) == []


# ---------------------------------------------------------------------------
# load_plugins tests
# ---------------------------------------------------------------------------


class TestLoadPlugins:
    def test_returns_list(self):
        result = load_plugins()
        assert isinstance(result, list)

    def test_no_plugins_returns_empty_list(self):
        with patch("importlib.metadata.entry_points", return_value=[]):
            result = load_plugins()
        assert result == []

    def test_loads_valid_plugin(self):
        ep = MagicMock()
        ep.name = "test_ep"
        ep.load.return_value = _AlwaysAlertPlugin

        with patch("importlib.metadata.entry_points", return_value=[ep]):
            plugins = load_plugins()

        assert len(plugins) == 1
        assert isinstance(plugins[0], _AlwaysAlertPlugin)

    def test_skips_broken_plugin(self):
        bad_ep = MagicMock()
        bad_ep.name = "bad_ep"
        bad_ep.load.side_effect = ImportError("missing dep")

        good_ep = MagicMock()
        good_ep.name = "good_ep"
        good_ep.load.return_value = _NeverAlertPlugin

        with patch("importlib.metadata.entry_points", return_value=[bad_ep, good_ep]):
            plugins = load_plugins()

        assert len(plugins) == 1
        assert isinstance(plugins[0], _NeverAlertPlugin)

    def test_all_broken_plugins_returns_empty_list(self):
        bad_ep = MagicMock()
        bad_ep.name = "bad"
        bad_ep.load.side_effect = RuntimeError("boom")

        with patch("importlib.metadata.entry_points", return_value=[bad_ep]):
            plugins = load_plugins()

        assert plugins == []

    def test_loads_multiple_plugins(self):
        ep1 = MagicMock()
        ep1.name = "ep1"
        ep1.load.return_value = _AlwaysAlertPlugin

        ep2 = MagicMock()
        ep2.name = "ep2"
        ep2.load.return_value = _NeverAlertPlugin

        with patch("importlib.metadata.entry_points", return_value=[ep1, ep2]):
            plugins = load_plugins()

        assert len(plugins) == 2

    def test_entry_points_exception_returns_empty(self):
        with patch(
            "importlib.metadata.entry_points", side_effect=Exception("registry error")
        ):
            plugins = load_plugins()
        assert plugins == []

    def test_loaded_plugin_name_accessible(self):
        ep = MagicMock()
        ep.name = "ep"
        ep.load.return_value = _AlwaysAlertPlugin

        with patch("importlib.metadata.entry_points", return_value=[ep]):
            plugins = load_plugins()

        assert plugins[0].name == "always-alert"

    def test_loaded_plugin_scan_works(self):
        ep = MagicMock()
        ep.name = "ep"
        ep.load.return_value = _AlwaysAlertPlugin

        with patch("importlib.metadata.entry_points", return_value=[ep]):
            plugins = load_plugins()

        alerts = plugins[0].scan({"action": "tools/call"})
        assert len(alerts) == 1
        assert alerts[0]["pattern"] == "test_pattern"
