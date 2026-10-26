"""Tests for value-scanning redaction (L1 fix): secrets embedded in values."""
from __future__ import annotations

from agentwit.config.redact import redact_payload, PLACEHOLDER


def _scan(v: str) -> str:
    return redact_payload({"command": v}, [], scan_values=True)["command"]


def test_bearer_token_in_command_masked():
    p = {"arguments": {"command": "curl -H 'Authorization: Bearer ghs_ABCDEFGHIJ0123456789KLMNOP' x"}}
    out = redact_payload(p, [], scan_values=True)
    cmd = out["arguments"]["command"]
    assert "ghs_ABCDEFGHIJ" not in cmd
    assert PLACEHOLDER in cmd
    assert cmd.startswith("curl -H 'Authorization: Bearer")  # context kept


def test_aws_key():
    assert _scan("aws AKIAIOSFODNN7EXAMPLE end") == "aws ***REDACTED*** end"


def test_openai_and_github_and_slack_token():
    assert "sk-" not in _scan("k=sk-abcdefghij0123456789ABCD")
    assert "ghp_" not in _scan("ghp_" + "a" * 36)
    assert "xoxb-" not in _scan("xoxb-123456789-abcdefghij")


def test_jwt_and_webhook_urls():
    assert PLACEHOLDER in _scan("t=eyJhbGci.eyJzdWIiOjEyMw.sIgNature")
    assert "hooks.slack" not in _scan("https://hooks.slack.com/services/T0/B0/zzzz")
    assert "discord.com/api/webhooks" not in _scan("https://discord.com/api/webhooks/1/abc")


def test_pem_private_key_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    assert "MIIabc" not in _scan("key=" + pem)


def test_no_over_redaction_of_ordinary_values():
    for v in ("nmap -sV 10.10.10.5", "/etc/passwd", "read the token file", "select * from users"):
        assert _scan(v) == v


def test_scan_off_by_default_keeps_backcompat():
    # existing callers pass no scan_values → embedded secrets are NOT scanned
    v = "Bearer ghs_ABCDEFGHIJ0123456789KLMNOP"
    assert redact_payload({"c": v}, [])["c"] == v


def test_key_based_still_works_with_scan():
    out = redact_payload({"password": "hunter2", "cmd": "ok"}, ["password"], scan_values=True)
    assert out["password"] == PLACEHOLDER
    assert out["cmd"] == "ok"
