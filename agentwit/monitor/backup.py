import shutil, hashlib, json
from pathlib import Path
from datetime import datetime

BACKUP_DIR  = Path.home() / ".agentwit" / "backups"
MAX_BACKUPS = 30

class SessionBackup:
    def backup(self, session_dir: Path) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"{session_dir.name}_{timestamp}"
        shutil.copytree(session_dir, dest)
        # 整合性ハッシュを記録
        self._write_hash(dest)
        # 古いバックアップを削除
        self._rotate()
        return dest

    def _write_hash(self, backup_dir: Path):
        hashes = {}
        for f in backup_dir.rglob("*.jsonl"):
            hashes[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        (backup_dir / "backup_hash.json").write_text(
            json.dumps(hashes, indent=2)
        )

    def _rotate(self):
        backups = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
        while len(backups) > MAX_BACKUPS:
            shutil.rmtree(backups.pop(0))
