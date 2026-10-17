"""SQLite CRUD operations for the Memory Engine."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.database import get_db
from core.utils import new_id, utcnow_str
from memory.schemas import MemoryEntry, MemoryEntryCreate, MemoryEntryUpdate, CATEGORY_TTL


def _dt_to_sqlite(dt: datetime) -> str:
    """Convert datetime to SQLite-compatible UTC string (no tz suffix)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _row_to_entry(row) -> MemoryEntry:
    d = dict(row)
    return MemoryEntry(**d)


def write(entry_create: MemoryEntryCreate) -> MemoryEntry:
    """Insert or update a memory entry in a single round-trip via UPSERT."""
    expires_at = entry_create.expires_at
    if expires_at is None:
        ttl_days = CATEGORY_TTL.get(entry_create.category)
        if ttl_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    now = utcnow_str()
    expires_str = _dt_to_sqlite(expires_at) if expires_at else None
    entry_id = new_id()
    tags_json = json.dumps(entry_create.tags)

    with get_db() as conn:
        row = conn.execute(
            """INSERT INTO memory_entries
               (id, namespace, category, key, value, source, agent_id, session_id,
                tags, confidence, expires_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(namespace, key) DO UPDATE SET
                   value      = excluded.value,
                   category   = excluded.category,
                   source     = excluded.source,
                   agent_id   = excluded.agent_id,
                   session_id = excluded.session_id,
                   tags       = excluded.tags,
                   confidence = excluded.confidence,
                   expires_at = excluded.expires_at,
                   updated_at = excluded.updated_at
               RETURNING *""",
            (
                entry_id,
                entry_create.namespace,
                entry_create.category,
                entry_create.key,
                entry_create.value,
                entry_create.source,
                entry_create.agent_id,
                entry_create.session_id,
                tags_json,
                entry_create.confidence,
                expires_str,
                now,
                now,
            ),
        ).fetchone()

    return _row_to_entry(row)


def get_by_id(entry_id: str) -> Optional[MemoryEntry]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM memory_entries WHERE id = ?", (entry_id,)
        ).fetchone()
    return _row_to_entry(row) if row else None


def get_by_key(namespace: str, key: str) -> Optional[MemoryEntry]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM memory_entries WHERE namespace = ? AND key = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            (namespace, key),
        ).fetchone()
    return _row_to_entry(row) if row else None


def list_entries(
    namespace: Optional[str] = None,
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    include_expired: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryEntry]:
    conditions = []
    params: list = []

    if namespace:
        conditions.append("namespace = ?")
        params.append(namespace)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if not include_expired:
        conditions.append("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)")
    if min_confidence > 0:
        conditions.append("confidence >= ?")
        params.append(min_confidence)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM memory_entries {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def update(entry_id: str, update_data: MemoryEntryUpdate) -> Optional[MemoryEntry]:
    fields: list[str] = []
    params: list = []

    if update_data.value is not None:
        fields.append("value = ?")
        params.append(update_data.value)
    if update_data.tags is not None:
        fields.append("tags = ?")
        params.append(json.dumps(update_data.tags))
    if update_data.confidence is not None:
        fields.append("confidence = ?")
        params.append(max(0.0, min(1.0, update_data.confidence)))
    if update_data.expires_at is not None:
        fields.append("expires_at = ?")
        params.append(_dt_to_sqlite(update_data.expires_at))

    if not fields:
        return get_by_id(entry_id)

    fields.append("updated_at = ?")
    params.append(utcnow_str())
    params.append(entry_id)

    with get_db() as conn:
        cursor = conn.execute(
            f"UPDATE memory_entries SET {', '.join(fields)} WHERE id = ?",
            params,
        )
    if cursor.rowcount == 0:
        return None
    return get_by_id(entry_id)


def delete(entry_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
    return cursor.rowcount > 0


def search_text(
    query: str,
    namespace: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
) -> list[MemoryEntry]:
    """FTS5 full-text search over key + value + tags."""
    ns_filter = "AND m.namespace = ?" if namespace else ""
    cat_filter = "AND m.category = ?" if category else ""
    params: list = [query, *(([namespace] if namespace else []) + ([category] if category else [])), limit]

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT m.* FROM memory_fts f
                JOIN memory_entries m ON m.rowid = f.rowid
                WHERE memory_fts MATCH ?
                  {ns_filter} {cat_filter}
                  AND (m.expires_at IS NULL OR m.expires_at > CURRENT_TIMESTAMP)
                ORDER BY rank
                LIMIT ?""",
            params,
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def expire_stale() -> int:
    """Hard-delete entries past expires_at. Returns count deleted."""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM memory_entries WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
        )
    return cursor.rowcount


def namespace_counts() -> dict[str, int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT namespace, COUNT(*) as cnt FROM memory_entries WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) GROUP BY namespace"
        ).fetchall()
    return {r["namespace"]: r["cnt"] for r in rows}


def get_context_for_agent(namespace: str, min_confidence: float = 0.8, limit: int = 20) -> list[MemoryEntry]:
    """Fetch high-confidence, non-expired entries for injection into agent system prompt."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM memory_entries
               WHERE namespace IN (?, 'global')
                 AND confidence >= ?
                 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
               ORDER BY confidence DESC, updated_at DESC
               LIMIT ?""",
            (namespace, min_confidence, limit),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]
