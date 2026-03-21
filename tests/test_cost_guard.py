"""Tests for agentwit.monitor.cost_guard."""
import pytest

from agentwit.monitor.cost_guard import CostGuard


class TestDefaults:
    def test_default_thresholds(self):
        g = CostGuard()
        assert g.per_call_usd == 0.10
        assert g.per_session_usd == 1.00
        assert g.calls_per_minute == 30

    def test_no_alerts_when_within_limits(self):
        g = CostGuard()
        alerts = g.check({"call_cost_usd": 0.05, "total_cost_usd": 0.50, "calls_per_minute": 15})
        assert alerts == []

    def test_empty_stats(self):
        g = CostGuard()
        assert g.check({}) == []


class TestPerCallCost:
    def test_alert_when_exceeded(self):
        g = CostGuard(per_call_usd=0.10)
        alerts = g.check({"call_cost_usd": 0.15})
        assert len(alerts) == 1
        assert alerts[0]["type"] == "per_call_cost_exceeded"
        assert alerts[0]["threshold"] == 0.10
        assert alerts[0]["actual"] == 0.15

    def test_no_alert_at_exact_threshold(self):
        g = CostGuard(per_call_usd=0.10)
        alerts = g.check({"call_cost_usd": 0.10})
        assert alerts == []

    def test_custom_threshold(self):
        g = CostGuard(per_call_usd=0.50)
        assert g.check({"call_cost_usd": 0.49}) == []
        assert len(g.check({"call_cost_usd": 0.51})) == 1


class TestPerSessionCost:
    def test_alert_when_exceeded(self):
        g = CostGuard(per_session_usd=1.00)
        alerts = g.check({"total_cost_usd": 1.50})
        assert len(alerts) == 1
        assert alerts[0]["type"] == "per_session_cost_exceeded"

    def test_no_alert_at_exact_threshold(self):
        g = CostGuard(per_session_usd=1.00)
        assert g.check({"total_cost_usd": 1.00}) == []


class TestCallRate:
    def test_alert_when_exceeded(self):
        g = CostGuard(calls_per_minute=30)
        alerts = g.check({"calls_per_minute": 35})
        assert len(alerts) == 1
        assert alerts[0]["type"] == "call_rate_exceeded"
        assert alerts[0]["threshold"] == 30
        assert alerts[0]["actual"] == 35

    def test_no_alert_at_exact_threshold(self):
        g = CostGuard(calls_per_minute=30)
        assert g.check({"calls_per_minute": 30}) == []


class TestMultipleAlerts:
    def test_all_thresholds_exceeded(self):
        g = CostGuard(per_call_usd=0.10, per_session_usd=1.00, calls_per_minute=30)
        alerts = g.check({
            "call_cost_usd": 0.20,
            "total_cost_usd": 2.00,
            "calls_per_minute": 60,
        })
        types = {a["type"] for a in alerts}
        assert types == {"per_call_cost_exceeded", "per_session_cost_exceeded", "call_rate_exceeded"}

    def test_message_is_non_empty(self):
        g = CostGuard()
        alerts = g.check({"call_cost_usd": 0.99})
        assert alerts[0]["message"]
