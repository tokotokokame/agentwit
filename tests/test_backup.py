"""Tests for SessionBackup: backup creation, hash file, and rotation."""
import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch
from agentwit.monitor.backup import SessionBackup, MAX_BACKUPS


@pytest.fixture()
def session_dir(tmp_path):
    """Minimal session directory with a witness.jsonl file."""
    sd = tmp_path / "session_20260101_000000"
    sd.mkdir()
    (sd / "witness.jsonl").write_text('{"event": 1}\n{"event": 2}\n')
    return sd


@pytest.fixture()
def backup_dir(tmp_path):
    return tmp_path / "backups"


def make_backup(session_dir, backup_dir):
    with patch("agentwit.monitor.backup.BACKUP_DIR", backup_dir):
        return SessionBackup().backup(session_dir)


def test_backup_creates_directory(session_dir, backup_dir):
    dest = make_backup(session_dir, backup_dir)
    assert dest.exists()
    assert dest.is_dir()


def test_backup_name_contains_session_name(session_dir, backup_dir):
    dest = make_backup(session_dir, backup_dir)
    assert dest.name.startswith(session_dir.name)


def test_backup_copies_witness_jsonl(session_dir, backup_dir):
    dest = make_backup(session_dir, backup_dir)
    assert (dest / "witness.jsonl").exists()
    content = (dest / "witness.jsonl").read_text()
    assert '{"event": 1}' in content


def test_backup_writes_hash_file(session_dir, backup_dir):
    dest = make_backup(session_dir, backup_dir)
    hash_file = dest / "backup_hash.json"
    assert hash_file.exists()
    hashes = json.loads(hash_file.read_text())
    assert "witness.jsonl" in hashes
    assert len(hashes["witness.jsonl"]) == 64  # sha256 hex digest


def test_backup_hash_is_correct(session_dir, backup_dir):
    import hashlib
    dest = make_backup(session_dir, backup_dir)
    hashes = json.loads((dest / "backup_hash.json").read_text())
    original = (session_dir / "witness.jsonl").read_bytes()
    expected = hashlib.sha256(original).hexdigest()
    assert hashes["witness.jsonl"] == expected


def test_backup_returns_path(session_dir, backup_dir):
    dest = make_backup(session_dir, backup_dir)
    assert isinstance(dest, Path)


def test_rotation_removes_oldest_when_over_limit(session_dir, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # MAX_BACKUPS 個のダミーバックアップを作成
    import time
    dummy_dirs = []
    for i in range(MAX_BACKUPS):
        d = backup_dir / f"old_session_{i:03d}"
        d.mkdir()
        (d / "witness.jsonl").write_text(f"dummy {i}")
        dummy_dirs.append(d)
        time.sleep(0.01)  # mtime に差をつける

    # 1つ追加すると最古が削除される
    with patch("agentwit.monitor.backup.BACKUP_DIR", backup_dir):
        SessionBackup().backup(session_dir)

    remaining = list(backup_dir.iterdir())
    assert len(remaining) == MAX_BACKUPS
    # 最古 (old_session_000) が削除されている
    assert not (backup_dir / "old_session_000").exists()


def test_no_rotation_when_under_limit(session_dir, backup_dir):
    make_backup(session_dir, backup_dir)
    assert len(list(backup_dir.iterdir())) == 1
