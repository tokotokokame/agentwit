"""Regression tests for the工程7 security review fixes."""
from __future__ import annotations

import logging

from agentwit.notifier.hub import _safe_webhook_url


SECRET = "https://hooks.slack.com/services/T000/B000/XXXXSECRETXXXX"


def test_non_https_webhook_url_not_logged(caplog):
    """A rejected non-https webhook URL must not appear in logs (it is a secret)."""
    bad = "http://hooks.slack.com/services/T000/B000/XXXXSECRETXXXX"
    with caplog.at_level(logging.WARNING):
        assert _safe_webhook_url(bad) is None
    assert "XXXXSECRETXXXX" not in caplog.text
    assert "services/T000" not in caplog.text


def test_disallowed_host_log_has_no_full_url(caplog):
    with caplog.at_level(logging.WARNING):
        assert _safe_webhook_url("https://evil.example.com/abc/SECRETPATH") is None
    assert "SECRETPATH" not in caplog.text


def test_safe_url_accepts_allowlisted_https():
    assert _safe_webhook_url(SECRET) == SECRET


def test_userinfo_trick_rejected():
    # hostname resolves to evil.com, not the allow-listed host
    assert _safe_webhook_url("https://hooks.slack.com@evil.com/x") is None


def test_smtp_host_guard_blocks_loopback_and_metadata(monkeypatch):
    """L2: loopback / link-local(metadata) / unspecified SMTP hosts are refused."""
    import socket
    import agentwit.notifier.hub as hub

    def fake_gai(host, *a, **k):
        ip = {"lo": "127.0.0.1", "meta": "169.254.169.254", "zero": "0.0.0.0",
              "pub": "93.184.216.34", "lan": "10.0.0.5"}[host]
        return [(socket.AF_INET, None, None, "", (ip, 0))]

    monkeypatch.setattr(hub.socket if hasattr(hub, "socket") else socket,
                        "getaddrinfo", fake_gai, raising=False)
    monkeypatch.setattr("socket.getaddrinfo", fake_gai)
    assert hub._safe_smtp_host("lo") is False
    assert hub._safe_smtp_host("meta") is False      # cloud metadata pivot
    assert hub._safe_smtp_host("zero") is False
    assert hub._safe_smtp_host("pub") is True         # public relay ok
    assert hub._safe_smtp_host("lan") is True         # internal RFC1918 relay ok


def test_smtp_host_guard_rejects_unresolvable(monkeypatch):
    import socket
    import agentwit.notifier.hub as hub

    def boom(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr("socket.getaddrinfo", boom)
    assert hub._safe_smtp_host("no.such.host.invalid") is False
    assert hub._safe_smtp_host("") is False


def test_notification_field_sanitized():
    """L4: @channel, Slack control spans and backticks are neutralised."""
    from agentwit.notifier.sanitize import clean_field
    out = clean_field("tool`x` <!channel> @here @everyone\n<@U123>")
    assert "`" not in out
    assert "<!channel>" not in out and "<@U123>" not in out
    assert "@here" not in out  # zero-width inserted, so literal '@here' is gone
    assert "\n" not in out


def test_webhook_failure_logs_type_only(caplog):
    """WebhookNotifier swallows failures and logs only the exception type."""
    import asyncio
    from agentwit.notifier.webhook import WebhookNotifier

    n = WebhookNotifier(url=SECRET, min_severity="low")

    async def run():
        # force a failure path by making _send raise with the URL in the message
        async def boom(*a, **k):
            raise RuntimeError(SECRET)
        n._send = boom
        await n._send_safe({}, "high", "x", [])

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert "XXXXSECRETXXXX" not in caplog.text
    assert "RuntimeError" in caplog.text
