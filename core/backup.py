"""SQLite backup utility — Phase C (B-05).

Strategy: SQLite online backup via VACUUM INTO (no lock contention).
- Destination: data/backups/claudeos_YYYYMMDD_HHMMSS.db
- Retention: keep last 7 backups; older ones auto-pruned.
- Called by: APScheduler daily job + POST /admin/backup endpoint.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("claudeos.backup")

_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"
_KEEP = 7


def create_backup() -> dict:
    """Run a SQLite online backup. Returns result dict."""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    from core.config import get_settings
    settings = get_settings()
    db_path = settings.sqlite_path

    if not db_path.exists():
        return {"ok": False, "error": f"Database not found: {db_path}"}

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = _BACKUP_DIR / f"claudeos_{ts}.db"

    try:
        # VACUUM INTO is an online backup — no locks held on the source DB.
        src = sqlite3.connect(str(db_path))
        try:
            src.execute(f"VACUUM INTO '{dest}'")
        finally:
            src.close()

        size_bytes = dest.stat().st_size
        logger.info("Backup created: %s (%d bytes)", dest.name, size_bytes)

        pruned = _prune_old_backups()
        return {
            "ok": True,
            "file": dest.name,
            "size_bytes": size_bytes,
            "path": str(dest),
            "pruned": pruned,
        }
    except Exception as e:
        logger.error("Backup failed: %s", e)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return {"ok": False, "error": str(e)}


def list_backups() -> list[dict]:
    """Return metadata for all existing backups, newest first."""
    if not _BACKUP_DIR.exists():
        return []
    files = sorted(_BACKUP_DIR.glob("claudeos_*.db"), reverse=True)
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "file": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "path": str(f),
        })
    return result


def _prune_old_backups() -> int:
    """Delete backups beyond the retention limit. Returns count deleted."""
    files = sorted(_BACKUP_DIR.glob("claudeos_*.db"), reverse=True)
    to_delete = files[_KEEP:]
    for f in to_delete:
        try:
            f.unlink()
            logger.info("Pruned old backup: %s", f.name)
        except Exception as e:
            logger.warning("Could not prune backup %s: %s", f.name, e)
    return len(to_delete)
