"""Tests for EventSigner: sign, verify, tamper detection."""
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture()
def signer(tmp_path):
    """EventSigner using a temporary key directory."""
    with patch("agentwit.security.signing.KEY_DIR", tmp_path), \
         patch("agentwit.security.signing.PRIVATE_KEY_PATH", tmp_path / "signing_key.pem"), \
         patch("agentwit.security.signing.PUBLIC_KEY_PATH", tmp_path / "signing_pub.pem"):
        from agentwit.security.signing import EventSigner
        yield EventSigner()


def test_sign_returns_string(signer):
    event = {"action": "tools/call", "tool": "bash"}
    sig = signer.sign(event)
    assert isinstance(sig, str)
    assert len(sig) > 0


def test_verify_valid_signature(signer):
    event = {"action": "tools/call", "tool": "bash", "timestamp": "2026-01-01T00:00:00Z"}
    sig = signer.sign(event)
    assert signer.verify(event, sig) is True


def test_verify_detects_tampering(signer):
    event = {"action": "tools/call", "tool": "bash"}
    sig = signer.sign(event)
    # 改ざん: tool を変更
    tampered = {**event, "tool": "evil_tool"}
    assert signer.verify(tampered, sig) is False


def test_verify_invalid_signature(signer):
    event = {"action": "tools/call"}
    assert signer.verify(event, "invalidsignature==") is False


def test_verify_empty_signature(signer):
    event = {"action": "tools/call"}
    assert signer.verify(event, "") is False


def test_fingerprint_is_16_chars(signer):
    fp = signer.fingerprint()
    assert isinstance(fp, str)
    assert len(fp) == 16


def test_keypair_persists(tmp_path):
    """同じディレクトリで初期化するとキーが再利用される"""
    with patch("agentwit.security.signing.KEY_DIR", tmp_path), \
         patch("agentwit.security.signing.PRIVATE_KEY_PATH", tmp_path / "signing_key.pem"), \
         patch("agentwit.security.signing.PUBLIC_KEY_PATH", tmp_path / "signing_pub.pem"):
        from agentwit.security.signing import EventSigner
        s1 = EventSigner()
        fp1 = s1.fingerprint()
        s2 = EventSigner()
        fp2 = s2.fingerprint()
    assert fp1 == fp2


def test_sign_verify_roundtrip_complex_event(signer):
    event = {
        "witness_id": "abc123",
        "session_chain": "def456",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "actor": "test-agent",
        "action": "tools/call",
        "tool": "read_file",
        "input_hash": "aaa",
        "output_hash": "bbb",
        "full_payload": {"params": {"path": "/etc/passwd"}},
        "risk_indicators": [{"severity": "high", "pattern": "path_traversal"}],
    }
    sig = signer.sign(event)
    assert signer.verify(event, sig) is True
