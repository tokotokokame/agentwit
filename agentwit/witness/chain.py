"""Chain hash management for tamper-evident witness logs.

Each event in a session is linked to the previous event via a cryptographic
hash chain. Modifying any event breaks the chain from that point forward,
making tampering detectable.
"""
import hashlib
import json
import uuid
from typing import Any


class ChainManager:
    """Manages a cryptographic hash chain for a witness log session.

    The chain works as follows:
    - The genesis hash is derived from the session_id: sha256("genesis:" + session_id)
    - Each event's ``session_chain`` is: sha256(prev_chain_hash + event_hash)
    - ``event_hash`` is the sha256 of the canonical JSON of the event data
      (excluding ``witness_id`` and ``session_chain`` fields)
    - ``witness_id`` is the sha256 of the full signed event (after adding
      ``session_chain``)
    """

    def __init__(self, session_id: str | None = None) -> None:
        """Initialize a ChainManager.

        Args:
            session_id: Identifier for this session. A UUID is generated if not provided.
        """
        self.session_id: str = session_id if session_id is not None else str(uuid.uuid4())
        self._prev_chain_hash: str = self._genesis_hash()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sign(self, event_data: dict) -> dict:
        """Add ``witness_id`` and ``session_chain`` to an event dict.

        The caller should NOT include ``witness_id`` or ``session_chain`` in
        *event_data* — they will be computed and added here.  The original
        dict is not mutated; a new dict is returned.

        Args:
            event_data: The event fields (timestamp, actor, action, …).

        Returns:
            A new dict with ``witness_id`` and ``session_chain`` added.
        """
        # Strip any previously-set chain fields to get a clean base.
        base = {k: v for k, v in event_data.items() if k not in ("witness_id", "session_chain")}

        # Compute chain hash from canonical JSON of the base event.
        event_hash = self._compute_event_hash(base)
        chain_hash = self._compute_chain_hash(self._prev_chain_hash, event_hash)

        # Build the signed event.
        signed: dict[str, Any] = {"witness_id": "", "session_chain": chain_hash, **base}

        # witness_id is the hash of the fully assembled event (with session_chain).
        witness_id = self._compute_event_hash(signed)
        signed["witness_id"] = witness_id

        # Advance the chain.
        self._prev_chain_hash = chain_hash

        return signed

    def verify_chain(self, events: list[dict]) -> list[dict]:
        """Verify the integrity of a list of signed events.

        Args:
            events: Ordered list of events as returned by ``sign()``.

        Returns:
            List of result dicts, one per event::

                {
                    "index": int,
                    "witness_id": str,
                    "valid": bool,
                    "reason": str,  # empty string when valid
                }
        """
        results: list[dict] = []
        expected_prev = self._genesis_hash()

        for idx, event in enumerate(events):
            witness_id = event.get("witness_id", "")
            session_chain = event.get("session_chain", "")

            # Re-derive the base event (strip chain fields) to recompute hashes.
            base = {k: v for k, v in event.items() if k not in ("witness_id", "session_chain")}
            event_hash = self._compute_event_hash(base)
            expected_chain = self._compute_chain_hash(expected_prev, event_hash)

            if session_chain != expected_chain:
                results.append({
                    "index": idx,
                    "witness_id": witness_id,
                    "valid": False,
                    "reason": (
                        f"session_chain mismatch: expected {expected_chain!r}, "
                        f"got {session_chain!r}"
                    ),
                })
                # Still advance with the *stored* chain hash so we can report
                # subsequent failures accurately relative to the stored values.
                expected_prev = session_chain
                continue

            # Verify witness_id.
            reassembled = {"witness_id": "", "session_chain": session_chain, **base}
            expected_witness_id = self._compute_event_hash(reassembled)
            if witness_id != expected_witness_id:
                results.append({
                    "index": idx,
                    "witness_id": witness_id,
                    "valid": False,
                    "reason": (
                        f"witness_id mismatch: expected {expected_witness_id!r}, "
                        f"got {witness_id!r}"
                    ),
                })
            else:
                results.append({
                    "index": idx,
                    "witness_id": witness_id,
                    "valid": True,
                    "reason": "",
                })

            expected_prev = session_chain

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _genesis_hash(self) -> str:
        """Return the genesis chain hash for this session."""
        return hashlib.sha256(f"genesis:{self.session_id}".encode()).hexdigest()

    def _compute_event_hash(self, event_data: dict) -> str:
        """Return the sha256 hex digest of the canonical JSON of *event_data*.

        Keys are sorted to ensure a deterministic encoding.
        """
        canonical = json.dumps(event_data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compute_chain_hash(self, prev_hash: str, event_hash: str) -> str:
        """Return sha256(prev_hash + event_hash)."""
        return hashlib.sha256((prev_hash + event_hash).encode()).hexdigest()
