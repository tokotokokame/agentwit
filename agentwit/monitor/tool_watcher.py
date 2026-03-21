"""Tool schema change detection and audit logging."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


_SNAPSHOT_PATH = Path.home() / ".agentwit" / "tool_snapshot.json"
_AUDIT_PATH = Path.home() / ".agentwit" / "audit.jsonl"


class ToolWatcher:
    """Watch MCP tool schemas for additions, removals, and modifications.

    Example::

        watcher = ToolWatcher()
        prev = watcher.snapshot(old_tools)
        curr = watcher.snapshot(new_tools)
        changes = watcher.diff(prev, curr)
    """

    def __init__(
        self,
        snapshot_path: Path | None = None,
        audit_path: Path | None = None,
    ) -> None:
        self._snapshot_path = snapshot_path or _SNAPSHOT_PATH
        self._audit_path = audit_path or _AUDIT_PATH

    def snapshot(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Persist a snapshot of *tools* and return it as a dict keyed by tool name.

        Args:
            tools: List of tool schema dicts.  Each dict must have a ``name`` key.

        Returns:
            Mapping of tool name → tool schema dict.
        """
        snap: dict[str, Any] = {t["name"]: t for t in tools}
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._snapshot_path.write_text(json.dumps(snap, indent=2))
        return snap

    def diff(
        self,
        prev: dict[str, Any],
        curr: dict[str, Any],
    ) -> dict[str, list]:
        """Compute the difference between two snapshots.

        Args:
            prev: Previous snapshot (as returned by :meth:`snapshot`).
            curr: Current snapshot.

        Returns:
            Dict with keys ``added``, ``removed``, ``modified`` — each a list of
            tool names.  If any changes are found they are written to the audit log.
        """
        prev_keys = set(prev)
        curr_keys = set(curr)

        added = sorted(curr_keys - prev_keys)
        removed = sorted(prev_keys - curr_keys)
        modified = sorted(
            name
            for name in prev_keys & curr_keys
            if json.dumps(prev[name], sort_keys=True) != json.dumps(curr[name], sort_keys=True)
        )

        if added or removed or modified:
            self._write_audit(added=added, removed=removed, modified=modified)

        return {"added": added, "removed": removed, "modified": modified}

    def _write_audit(self, *, added: list, removed: list, modified: list) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "type": "tool_schema_change",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "added": added,
            "removed": removed,
            "modified": modified,
        }
        with self._audit_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
