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
