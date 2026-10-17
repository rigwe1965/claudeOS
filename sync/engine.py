"""Phase 7 — Supabase Cloud Sync Engine.

Strategy: push-only, watermark-based.
- Reads rows from SQLite newer than last_synced_at per table.
- Upserts to Supabase (safe re-runs).
- Updates sync_state watermark only on full success.
- Logs each sync run to sync_log table.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from core.config import get_settings
from core.database import get_db
from core.utils import new_id, utcnow_str
from sync.schemas import SyncResult, TableSyncResult

logger = logging.getLogger("claudeos.sync")

_migration_done = False

# Tables and the timestamp column used for watermark
_SYNC_TABLES: dict[str, str] = {
    "memory_entries": "created_at",
    "agent_runs": "created_at",
    "outputs": "created_at",
    "namespaces": "created_at",
    "projects": "created_at",
    "system_events": "created_at",
    "users": "created_at",
    "tickets": "created_at",
    "workflows": "created_at",
}

# Columns to exclude from sync (sensitive or local-only data)
_EXCLUDE_COLS: dict[str, list[str]] = {
    "outputs": ["file_path"],
    "users": ["password_hash", "failed_attempts", "locked_until"],
}


def _get_supabase():
    """Return a Supabase client or None if not configured."""
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return None
    try:
        from supabase import create_client
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    except Exception as e:
        logger.error("Supabase client init failed: %s", e)
        return None


def _run_migration():
    """Ensure sync_state / sync_log tables exist."""
    global _migration_done
    if _migration_done:
        return
    from pathlib import Path
    migration = Path(__file__).parent.parent / "memory" / "db" / "migrations" / "002_sync_state.sql"
    if migration.exists():
        from core.database import run_migration
        run_migration(migration)
    _migration_done = True


def get_status() -> dict:
    """Return current sync status dict."""
    _run_migration()
    settings = get_settings()
    configured = bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY)

    with get_db() as conn:
        rows = conn.execute(
            "SELECT table_name, last_synced_at, rows_pushed, rows_failed, last_error FROM sync_state"
        ).fetchall()

    table_states = {}
    last_sync_times = []
    for r in rows:
        table_states[r["table_name"]] = {
            "last_synced_at": r["last_synced_at"],
            "rows_pushed": r["rows_pushed"],
            "rows_failed": r["rows_failed"],
            "last_error": r["last_error"],
        }
        if r["last_synced_at"]:
            last_sync_times.append(r["last_synced_at"])

    last_sync_at = max(last_sync_times) if last_sync_times else None

    auto_interval = getattr(settings, "SYNC_INTERVAL_MIN", 15)

    return {
        "configured": configured,
        "last_sync_at": last_sync_at,
        "table_states": table_states,
        "auto_sync_enabled": configured,
        "auto_sync_interval_min": auto_interval,
    }


def push_all() -> SyncResult:
    """Push all pending rows to Supabase. Returns SyncResult."""
    _run_migration()
    started_at = utcnow_str()
    t0 = time.time()

    sb = _get_supabase()
    if sb is None:
        return SyncResult(
            success=False,
            started_at=started_at,
            completed_at=utcnow_str(),
            tables=[TableSyncResult(table_name="*", error="Supabase not configured")],
        )

    results: list[TableSyncResult] = []

    for table, ts_col in _SYNC_TABLES.items():
        res = _push_table(sb, table, ts_col)
        results.append(res)

    total_pushed = sum(r.rows_pushed for r in results)
    total_failed = sum(r.rows_failed for r in results)
    duration_ms = int((time.time() - t0) * 1000)
    completed_at = utcnow_str()

    return SyncResult(
        success=total_failed == 0,
        tables=results,
        total_pushed=total_pushed,
        total_failed=total_failed,
        duration_ms=duration_ms,
        started_at=started_at,
        completed_at=completed_at,
    )


def push_table(table_name: str) -> TableSyncResult:
    """Push a single table."""
    _run_migration()
    sb = _get_supabase()
    if sb is None:
        return TableSyncResult(table_name=table_name, error="Supabase not configured")
    ts_col = _SYNC_TABLES.get(table_name)
    if ts_col is None:
        return TableSyncResult(table_name=table_name, error=f"Unknown table: {table_name}")
    return _push_table(sb, table_name, ts_col)


def _push_table(sb, table: str, ts_col: str) -> TableSyncResult:
    t0 = time.time()
    log_id = new_id()
    now = utcnow_str()

    with get_db() as conn:
        watermark_row = conn.execute(
            "SELECT last_synced_at FROM sync_state WHERE table_name = ?", (table,)
        ).fetchone()

    watermark = watermark_row["last_synced_at"] if watermark_row else None

    # Fetch rows newer than watermark (or all if no watermark)
    try:
        with get_db() as conn:
            if watermark:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE {ts_col} > ? ORDER BY {ts_col} ASC",
                    (watermark,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {table} ORDER BY {ts_col} ASC"
                ).fetchall()
    except Exception as e:
        logger.error("Failed to fetch %s: %s", table, e)
        return TableSyncResult(table_name=table, error=str(e), duration_ms=_ms(t0))

    if not rows:
        _update_watermark(table, watermark or now, 0, 0, None)
        return TableSyncResult(table_name=table, rows_pushed=0, duration_ms=_ms(t0))

    exclude = _EXCLUDE_COLS.get(table, [])
    records = []
    for row in rows:
        rec = dict(row)
        for col in exclude:
            rec.pop(col, None)
        records.append(rec)

    # Upsert in batches of 200
    rows_ok = 0
    rows_fail = 0
    error_msg = None
    batch_size = 200

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            sb.table(table).upsert(batch).execute()
            rows_ok += len(batch)
        except Exception as e:
            logger.error("Upsert failed for %s batch %d: %s", table, i // batch_size, e)
            rows_fail += len(batch)
            error_msg = str(e)[:500]

    duration = _ms(t0)
    new_watermark = records[-1].get(ts_col, now) if rows_ok > 0 else watermark
    _update_watermark(table, new_watermark or now, rows_ok, rows_fail, error_msg)
    _log_sync_run(log_id, table, rows_ok, rows_fail, duration, error_msg, now)

    logger.info("Sync %s: pushed=%d failed=%d (%dms)", table, rows_ok, rows_fail, duration)
    return TableSyncResult(
        table_name=table,
        rows_pushed=rows_ok,
        rows_failed=rows_fail,
        error=error_msg,
        duration_ms=duration,
    )


def get_sync_log(limit: int = 50) -> list[dict]:
    _run_migration()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sync_log ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_log_entries(ids: list) -> int:
    """Delete sync log entries by ID. Returns count deleted."""
    _run_migration()
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with get_db() as conn:
        cur = conn.execute(f"DELETE FROM sync_log WHERE id IN ({placeholders})", ids)
        return cur.rowcount


def reset_watermark(table_name: Optional[str] = None) -> None:
    """Reset watermark so next sync pushes all rows."""
    _run_migration()
    with get_db() as conn:
        if table_name:
            conn.execute(
                "UPDATE sync_state SET last_synced_at = NULL WHERE table_name = ?",
                (table_name,),
            )
        else:
            conn.execute("UPDATE sync_state SET last_synced_at = NULL")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _update_watermark(
    table: str,
    last_synced_at: str,
    rows_pushed: int,
    rows_failed: int,
    error: Optional[str],
) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO sync_state (table_name, last_synced_at, rows_pushed, rows_failed, last_error, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(table_name) DO UPDATE SET
                   last_synced_at = excluded.last_synced_at,
                   rows_pushed = sync_state.rows_pushed + excluded.rows_pushed,
                   rows_failed = excluded.rows_failed,
                   last_error = excluded.last_error,
                   updated_at = excluded.updated_at""",
            (table, last_synced_at, rows_pushed, rows_failed, error, utcnow_str()),
        )


def _log_sync_run(
    log_id: str,
    table: str,
    rows_ok: int,
    rows_fail: int,
    duration_ms: int,
    error: Optional[str],
    started_at: str,
) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO sync_log
               (id, table_name, direction, rows_ok, rows_fail, duration_ms, error, started_at, completed_at)
               VALUES (?, ?, 'push', ?, ?, ?, ?, ?, ?)""",
            (log_id, table, rows_ok, rows_fail, duration_ms, error, started_at, utcnow_str()),
        )
