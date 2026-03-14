"""Tests for agentwit.witness.chain.ChainManager."""
import hashlib
import json

import pytest

from agentwit.witness.chain import ChainManager


class TestChainManagerSign:
    """Tests for ChainManager.sign()."""

    def test_sign_adds_witness_id(self) -> None:
        cm = ChainManager(session_id="test-session")
        event = {"timestamp": "2024-01-01T00:00:00Z", "actor": "agent", "action": "tools/list"}
        signed = cm.sign(event)
        assert "witness_id" in signed
        assert isinstance(signed["witness_id"], str)
        assert len(signed["witness_id"]) == 64  # sha256 hex digest

    def test_sign_adds_session_chain(self) -> None:
        cm = ChainManager(session_id="test-session")
        event = {"timestamp": "2024-01-01T00:00:00Z", "actor": "agent", "action": "tools/list"}
        signed = cm.sign(event)
        assert "session_chain" in signed
        assert isinstance(signed["session_chain"], str)
        assert len(signed["session_chain"]) == 64

    def test_sign_preserves_original_fields(self) -> None:
        cm = ChainManager(session_id="test-session")
        event = {"actor": "agent", "action": "tools/call", "tool": "bash"}
        signed = cm.sign(event)
        assert signed["actor"] == "agent"
        assert signed["action"] == "tools/call"
        assert signed["tool"] == "bash"

    def test_sign_does_not_mutate_input(self) -> None:
        cm = ChainManager(session_id="test-session")
        event = {"actor": "agent", "action": "tools/call"}
        original_keys = set(event.keys())
        cm.sign(event)
        assert set(event.keys()) == original_keys

    def test_sign_genesis_chain_hash(self) -> None:
        """First event's session_chain must derive from genesis hash."""
        session_id = "test-session-genesis"
        cm = ChainManager(session_id=session_id)
        event = {"actor": "agent", "action": "tools/list"}
        signed = cm.sign(event)

        # Manually recompute genesis hash.
        genesis = hashlib.sha256(f"genesis:{session_id}".encode()).hexdigest()

        # Re-derive event_hash (base without chain fields).
        base = {k: v for k, v in signed.items() if k not in ("witness_id", "session_chain")}
        event_hash = hashlib.sha256(
            json.dumps(base, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()
        expected_chain = hashlib.sha256((genesis + event_hash).encode()).hexdigest()

        assert signed["session_chain"] == expected_chain

    def test_sign_chain_advances(self) -> None:
        """Consecutive events must have different session_chain values."""
        cm = ChainManager(session_id="test-session")
        e1 = cm.sign({"action": "tools/list"})
        e2 = cm.sign({"action": "tools/call"})
        assert e1["session_chain"] != e2["session_chain"]

    def test_sign_uuid_generated_when_session_id_none(self) -> None:
        cm = ChainManager()
        assert cm.session_id is not None
        assert len(cm.session_id) > 0


class TestChainManagerVerify:
    """Tests for ChainManager.verify_chain()."""

    def _make_chain(self, n: int = 3, session_id: str = "verify-session") -> tuple[ChainManager, list[dict]]:
        cm = ChainManager(session_id=session_id)
        events = [cm.sign({"action": f"action_{i}", "seq": i}) for i in range(n)]
        return cm, events

    def test_verify_valid_chain(self) -> None:
        _, events = self._make_chain()
        cm2 = ChainManager(session_id="verify-session")
        results = cm2.verify_chain(events)
        assert len(results) == 3
        assert all(r["valid"] for r in results)
        assert all(r["reason"] == "" for r in results)

    def test_verify_returns_index(self) -> None:
        _, events = self._make_chain(n=2)
        cm2 = ChainManager(session_id="verify-session")
        results = cm2.verify_chain(events)
        assert results[0]["index"] == 0
        assert results[1]["index"] == 1

    def test_verify_returns_witness_id(self) -> None:
        _, events = self._make_chain(n=2)
        cm2 = ChainManager(session_id="verify-session")
        results = cm2.verify_chain(events)
        assert results[0]["witness_id"] == events[0]["witness_id"]

    def test_verify_empty_chain(self) -> None:
        cm = ChainManager(session_id="verify-session")
        results = cm.verify_chain([])
        assert results == []

    def test_verify_single_event(self) -> None:
        _, events = self._make_chain(n=1)
        cm2 = ChainManager(session_id="verify-session")
        results = cm2.verify_chain(events)
        assert results[0]["valid"] is True

    def test_verify_detects_tampered_field(self) -> None:
        """Modifying an event field must fail chain verification."""
        session_id = "tamper-session"
        _, events = self._make_chain(n=3, session_id=session_id)

        # Tamper with the middle event.
        tampered = events.copy()
        tampered[1] = dict(tampered[1])
        tampered[1]["action"] = "TAMPERED"

        cm2 = ChainManager(session_id=session_id)
        results = cm2.verify_chain(tampered)

        # The tampered event at index 1 must be invalid.
        assert results[1]["valid"] is False
        assert "mismatch" in results[1]["reason"].lower()

    def test_verify_detects_tampered_witness_id(self) -> None:
        """Modifying only the witness_id must fail verification."""
        session_id = "wid-tamper-session"
        _, events = self._make_chain(n=2, session_id=session_id)

        tampered = events.copy()
        tampered[0] = dict(tampered[0])
        tampered[0]["witness_id"] = "a" * 64

        cm2 = ChainManager(session_id=session_id)
        results = cm2.verify_chain(tampered)
        assert results[0]["valid"] is False

    def test_verify_does_not_affect_signer_state(self) -> None:
        """Calling verify_chain on a fresh manager should not change _prev_chain_hash."""
        _, events = self._make_chain(n=2, session_id="state-session")
        cm2 = ChainManager(session_id="state-session")
        genesis = cm2._prev_chain_hash
        cm2.verify_chain(events)
        # _prev_chain_hash is reset to genesis since verify uses a local variable.
        # The verify method should leave _prev_chain_hash unchanged.
        assert cm2._prev_chain_hash == genesis
