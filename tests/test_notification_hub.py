"""Tests for the notification hub, SSRF guard, routing, rate limit, email."""
from __future__ import annotations

import asyncio

from agentwit.notifier.hub import (
    NotificationHub,
    _Route,
    _worst,
    _safe_webhook_url,
)
from agentwit.notifier.email import EmailSender
from agentwit.config import validate_config


def test_ssrf_guard():
    assert _safe_webhook_url("https://hooks.slack.com/x")
    assert _safe_webhook_url("http://hooks.slack.com/x") is None     # not https
    assert _safe_webhook_url("https://evil.com/x") is None           # host not allowed
    assert _safe_webhook_url("https://169.254.169.254/latest") is None  # metadata IP


def test_worst_severity():
    assert _worst([{"severity": "low"}, {"severity": "critical"}]) == "critical"
    assert _worst([]) == "low"


def test_routing_and_rate_limit():
    sent: list[tuple[str, str]] = []

    def mk(name):
        async def _d(_e, _i, sev):
            sent.append((name, sev))
        return _d

    async def run():
        hub = NotificationHub(
            [_Route("hi", {"high", "critical"}, mk("hi")),
             _Route("crit", {"critical"}, mk("crit"))],
            max_per_min=2,
        )
        await hub.notify({}, [{"severity": "high"}])       # -> hi
        await hub.notify({}, [{"severity": "critical"}])   # -> hi, crit
        await hub.notify({}, [{"severity": "critical"}])   # dropped by rate limit

    asyncio.run(run())
    assert sent == [("hi", "high"), ("hi", "critical"), ("crit", "critical")]


def test_from_config_drops_unsafe_webhook():
    cfg = {"notify": {"routes": [
        {"name": "s", "kind": "slack", "url": "https://hooks.slack.com/x", "on": ["CRITICAL"]},
        {"name": "bad", "kind": "webhook", "url": "https://evil.com/x", "on": ["HIGH"]},
        {"name": "m", "kind": "email", "smtp_host": "smtp.x", "mail_to": ["a@b.c"], "on": ["CRITICAL"]},
    ]}}
    assert [r.name for r in NotificationHub.from_config(cfg)._routes] == ["s", "m"]


def test_empty_hub_is_inactive():
    assert NotificationHub.from_config({}).active is False
    assert NotificationHub.from_config(None).active is False


def test_email_subject_contains_pattern_and_tool():
    msg = EmailSender(host="x", mail_to=["a@b.c"])._build(
        {"tool": "bash"}, [{"pattern": "shell_exec", "severity": "high"}], "high"
    )
    assert "shell_exec" in msg["Subject"] and "bash" in msg["Subject"]


def test_validate_route_required_fields():
    assert validate_config({"notify": {"routes": [{"kind": "email"}]}})[0]
    assert validate_config({"notify": {"routes": [{"kind": "webhook"}]}})[0]
    assert validate_config({"notify": {"routes": [{"kind": "bogus", "url": "x"}]}})[0]
    ok = {"notify": {"routes": [
        {"kind": "slack", "url": "https://hooks.slack.com/x", "on": ["HIGH"]}
    ]}}
    assert validate_config(ok)[0] == []
