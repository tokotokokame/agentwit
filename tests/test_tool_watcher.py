"""Tests for agentwit.monitor.tool_watcher."""
import json
import tempfile
from pathlib import Path

import pytest

from agentwit.monitor.tool_watcher import ToolWatcher


@pytest.fixture()
def tmp_watcher(tmp_path):
    return ToolWatcher(
        snapshot_path=tmp_path / "tool_snapshot.json",
        audit_path=tmp_path / "audit.jsonl",
    )


TOOL_A = {"name": "tool_a", "description": "does a", "inputSchema": {"type": "object"}}
TOOL_B = {"name": "tool_b", "description": "does b", "inputSchema": {"type": "object"}}
TOOL_A_MODIFIED = {"name": "tool_a", "description": "does a (updated)", "inputSchema": {"type": "object"}}


class TestSnapshot:
    def test_returns_dict_keyed_by_name(self, tmp_watcher):
        snap = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        assert set(snap.keys()) == {"tool_a", "tool_b"}

    def test_writes_to_disk(self, tmp_watcher, tmp_path):
        tmp_watcher.snapshot([TOOL_A])
        data = json.loads((tmp_path / "tool_snapshot.json").read_text())
        assert "tool_a" in data

    def test_empty_tools(self, tmp_watcher):
        snap = tmp_watcher.snapshot([])
        assert snap == {}


class TestDiff:
    def test_no_changes(self, tmp_watcher):
        snap = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        result = tmp_watcher.diff(snap, snap)
        assert result == {"added": [], "removed": [], "modified": []}

    def test_added_tool(self, tmp_watcher):
        prev = tmp_watcher.snapshot([TOOL_A])
        curr = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        result = tmp_watcher.diff(prev, curr)
        assert result["added"] == ["tool_b"]
        assert result["removed"] == []
        assert result["modified"] == []

    def test_removed_tool(self, tmp_watcher):
        prev = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        curr = tmp_watcher.snapshot([TOOL_A])
        result = tmp_watcher.diff(prev, curr)
        assert result["removed"] == ["tool_b"]
        assert result["added"] == []

    def test_modified_tool(self, tmp_watcher):
        prev = tmp_watcher.snapshot([TOOL_A])
        curr = tmp_watcher.snapshot([TOOL_A_MODIFIED])
        result = tmp_watcher.diff(prev, curr)
        assert result["modified"] == ["tool_a"]
        assert result["added"] == []
        assert result["removed"] == []

    def test_writes_audit_on_change(self, tmp_watcher, tmp_path):
        prev = tmp_watcher.snapshot([TOOL_A])
        curr = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        tmp_watcher.diff(prev, curr)
        audit_file = tmp_path / "audit.jsonl"
        assert audit_file.exists()
        record = json.loads(audit_file.read_text().strip())
        assert record["type"] == "tool_schema_change"
        assert "tool_b" in record["added"]

    def test_no_audit_when_no_change(self, tmp_watcher, tmp_path):
        snap = tmp_watcher.snapshot([TOOL_A])
        tmp_watcher.diff(snap, snap)
        audit_file = tmp_path / "audit.jsonl"
        assert not audit_file.exists()

    def test_audit_appends_multiple_records(self, tmp_watcher, tmp_path):
        prev = tmp_watcher.snapshot([TOOL_A])
        curr1 = tmp_watcher.snapshot([TOOL_A, TOOL_B])
        tmp_watcher.diff(prev, curr1)
        curr2 = tmp_watcher.snapshot([TOOL_A])
        tmp_watcher.diff(curr1, curr2)
        lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
