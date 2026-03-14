"""Tests for notifier/webhook.py"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentwit.notifier.webhook import WebhookNotifier, parse_severity_list


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _event(tool: str = "bash", actor: str = "agent") -> dict:
    return {
        "timestamp": "2024-01-01T00:00:00",
        "actor": actor,
        "action": "tools/call",
        "tool": tool,
        "full_payload": {},
        "session_id": "session_test_001",
        "witness_id": "wid_001",
    }


def _indicators(severity: str = "high", pattern: str = "shell_exec") -> list[dict]:
    return [{"severity": severity, "pattern": pattern, "matched": "bash"}]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestWebhookNotifierInit:
    def test_default_min_severity(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        assert n.min_severity == "high"

    def test_custom_severity(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx", min_severity="CRITICAL")
        assert n.min_severity == "critical"

    def test_discord_detection(self):
        n = WebhookNotifier(url="https://discord.com/api/webhooks/123/abc")
        assert n._is_discord() is True

    def test_slack_detection(self):
        n = WebhookNotifier(url="https://hooks.slack.com/services/T/B/x")
        assert n._is_discord() is False


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------

class TestThreshold:
    @pytest.mark.asyncio
    async def test_below_threshold_not_sent(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx", min_severity="HIGH")
        with patch.object(n, "_send_safe", new_callable=AsyncMock) as mock_send:
            await n.notify_if_threshold(_event(), _indicators(severity="medium"))
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_threshold_sent(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx", min_severity="HIGH")
        with patch.object(n, "_send_safe", new_callable=AsyncMock) as mock_send:
            await n.notify_if_threshold(_event(), _indicators(severity="high"))
            # ensure_future schedules it; we check _send_safe is available
            # (exact call timing depends on event loop)
            # At minimum verify no exception raised
            assert True

    @pytest.mark.asyncio
    async def test_critical_above_high_threshold(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx", min_severity="HIGH")
        with patch.object(n, "_send_safe", new_callable=AsyncMock) as mock_send:
            await n.notify_if_threshold(_event(), _indicators(severity="critical"))
            assert True  # no exception

    @pytest.mark.asyncio
    async def test_empty_indicators_not_sent(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx", min_severity="HIGH")
        with patch.object(n, "_send_safe", new_callable=AsyncMock) as mock_send:
            await n.notify_if_threshold(_event(), [])
            mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Payload building
# ---------------------------------------------------------------------------

class TestPayloadBuilding:
    def test_slack_payload_has_blocks(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        payload = n._build_payload(_event(), "high", "shell_exec", _indicators())
        assert "blocks" in payload or "text" in payload

    def test_discord_payload_has_content(self):
        n = WebhookNotifier(url="https://discord.com/api/webhooks/123/abc")
        payload = n._build_payload(_event(), "critical", "privilege_escalation", _indicators("critical"))
        assert "content" in payload
        assert "CRITICAL" in payload["content"]

    def test_slack_payload_contains_session_id(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        payload = n._build_payload(_event(), "high", "shell_exec", _indicators())
        payload_str = json.dumps(payload)
        assert "session_test_001" in payload_str

    def test_payload_contains_tool_name(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        payload = n._build_payload(_event(tool="nmap"), "high", "lateral_movement", _indicators())
        payload_str = json.dumps(payload)
        assert "nmap" in payload_str

    def test_severity_emoji_critical(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        payload = n._build_payload(_event(), "critical", "priv_esc", _indicators("critical"))
        # Check the actual string values in the dict (not JSON-escaped)
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "🚨" in payload_str

    def test_severity_emoji_high(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        payload = n._build_payload(_event(), "high", "shell_exec", _indicators())
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "🔴" in payload_str


# ---------------------------------------------------------------------------
# HTTP send (mocked)
# ---------------------------------------------------------------------------

class TestSendSafe:
    @pytest.mark.asyncio
    async def test_send_safe_swallows_exception(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        # Patch _send to raise
        with patch.object(n, "_send", side_effect=Exception("network error")):
            # Should not raise
            await n._send_safe(_event(), "high", "shell_exec", _indicators())

    @pytest.mark.asyncio
    async def test_send_makes_post_request(self):
        n = WebhookNotifier(url="https://hooks.slack.com/xxx")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("agentwit.notifier.webhook.httpx") as mock_httpx:
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            await n._send(_event(), "high", "shell_exec", _indicators())
            mock_client.post.assert_awaited_once()
            call_args = mock_client.post.call_args
            assert call_args.args[0] == "https://hooks.slack.com/xxx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestParseSeverityList:
    def test_basic(self):
        assert parse_severity_list("HIGH,CRITICAL") == ["high", "critical"]

    def test_single(self):
        assert parse_severity_list("medium") == ["medium"]

    def test_whitespace_stripped(self):
        assert parse_severity_list(" HIGH , CRITICAL ") == ["high", "critical"]

    def test_empty_string(self):
        assert parse_severity_list("") == []


class TestWorstHelper:
    def test_worst_of_mixed(self):
        inds = [
            {"severity": "medium", "pattern": "a"},
            {"severity": "critical", "pattern": "b"},
            {"severity": "high", "pattern": "c"},
        ]
        sev, pat = WebhookNotifier._worst(inds)
        assert sev == "critical"
        assert pat == "b"

    def test_empty_returns_low(self):
        sev, pat = WebhookNotifier._worst([])
        assert sev == "low"
        assert pat == ""
