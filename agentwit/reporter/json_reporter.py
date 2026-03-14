"""JSON report generator for witness log sessions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..witness.chain import ChainManager


class JsonReporter:
    """Generate a JSON-formatted audit report from a witness log session.

    The report aggregates all events from ``witness.jsonl``, verifies the
    chain integrity, computes a risk summary, and returns structured data
    suitable for machine consumption or further processing.

    Example::

        reporter = JsonReporter(Path("./witness_logs/session_20240101_120000"))
        print(reporter.render())
    """

    def __init__(self, session_dir: Path) -> None:
        """Initialise the reporter.

        Args:
            session_dir: Path to the session directory containing
                ``witness.jsonl``.
        """
        self.session_dir = Path(session_dir)
        self._events: list[dict] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_events(self) -> list[dict]:
        """Read and parse all events from ``witness.jsonl``.

        Returns:
            Ordered list of event dicts as recorded by the WitnessLogger.

        Raises:
            FileNotFoundError: If ``witness.jsonl`` does not exist in the
                session directory.
        """
        log_path = self.session_dir / "witness.jsonl"
        events: list[dict] = []
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        self._events = events
        return events

    def generate(self) -> dict:
        """Build and return the full report as a Python dict.

        Returns:
            A dict with the following keys:

            - ``session_id``: The session directory name.
            - ``generated_at``: ISO8601 timestamp of report generation.
            - ``total_events``: Number of events in the log.
            - ``actor``: The actor recorded on the first event (or ``"unknown"``).
            - ``chain_valid``: ``True`` if every event passes chain verification.
            - ``events``: The full list of event dicts.
            - ``risk_summary``: Dict with ``total_risk_indicators`` (int) and
              ``high_risk_events`` (list of event dicts that have at least one
              risk indicator).
        """
        events = self._events if self._events is not None else self.load_events()

        # Derive session_id from the directory name.
        session_id = self.session_dir.name

        # Verify chain using a fresh ChainManager initialised with the same session_id.
        chain = ChainManager(session_id=session_id)
        verification = chain.verify_chain(events)
        chain_valid = all(r["valid"] for r in verification)

        # Actor from first event.
        actor = events[0].get("actor", "unknown") if events else "unknown"

        # Risk summary.
        total_risk_indicators = 0
        high_risk_events: list[dict] = []
        for event in events:
            indicators = event.get("risk_indicators") or []
            total_risk_indicators += len(indicators)
            if indicators:
                high_risk_events.append(event)

        return {
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(events),
            "actor": actor,
            "chain_valid": chain_valid,
            "events": events,
            "risk_summary": {
                "total_risk_indicators": total_risk_indicators,
                "high_risk_events": high_risk_events,
            },
        }

    def render(self) -> str:
        """Return the report as a pretty-printed JSON string.

        Returns:
            A formatted JSON string representation of the report.
        """
        return json.dumps(self.generate(), indent=2, ensure_ascii=False, default=str)
