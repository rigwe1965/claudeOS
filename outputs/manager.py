"""Output Manager — save, tag, search, export agent/workflow outputs.

Responsibilities:
1. Persist output to SQLite (FTS5-indexed for search)
2. Write file to outputs/store/{type}/{namespace}/
3. Auto-tag from content (keywords + agent/workflow metadata)
4. FTS search across title, content, tags, summary
5. Export to markdown/text/json
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.database import get_db
from core.utils import new_id, utcnow_str
from outputs.schemas import Output, OutputSave, OutputSearchResult

logger = logging.getLogger("claudeos.outputs.manager")

STORE_ROOT = Path(__file__).parent / "store"

# Auto-tag keyword maps
_TAG_KEYWORDS: dict[str, list[str]] = {
    "research": ["research", "analysis", "findings", "study", "investigate"],
    "report": ["report", "summary", "brief", "status", "update"],
    "draft": ["draft", "proposal", "template", "outline"],
    "code": ["```python", "```javascript", "```sql", "def ", "function ", "class "],
    "client": ["client", "reci", "ivycandy", "faiyke"],
    "urgent": ["urgent", "critical", "asap", "immediately", "deadline"],
    "decision": ["decision", "decided", "approved", "rejected", "chosen"],
}


def save(
    namespace: str,
    title: str,
    content: str,
    output_type: str = "report",
    format: str = "markdown",
    tags: Optional[list[str]] = None,
    agent_run_id: Optional[str] = None,
    workflow_run_id: Optional[str] = None,
    project_id: Optional[str] = None,
    summary: str = "",
) -> Output:
    """Save output to DB + filesystem. Returns saved Output."""
    output_id = new_id()
    now = utcnow_str()

    # Auto-tag
    auto_tags = _auto_tag(content, output_type)
    all_tags = list(set((tags or []) + auto_tags + [namespace]))

    # Auto-summarise if not provided
    if not summary:
        summary = _auto_summary(content)

    size_bytes = len(content.encode("utf-8"))

    # Write file
    file_path = _write_file(output_id, namespace, output_type, format, content)

    tags_json = json.dumps(all_tags)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO outputs
               (id, namespace, project_id, agent_run_id, workflow_run_id,
                type, title, content, format, tags, file_path, size_bytes,
                summary, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                output_id, namespace, project_id, agent_run_id, workflow_run_id,
                output_type, title, content, format, tags_json,
                str(file_path), size_bytes, summary, now, now,
            ),
        )

    logger.info("Saved output %s (%s, %d bytes, ns=%s)", output_id[:8], output_type, size_bytes, namespace)
    return Output(
        id=output_id,
        namespace=namespace,
        project_id=project_id,
        agent_run_id=agent_run_id,
        workflow_run_id=workflow_run_id,
        output_type=output_type,
        title=title,
        content=content,
        format=format,
        tags=all_tags,
        file_path=str(file_path),
        size_bytes=size_bytes,
        summary=summary,
        created_at=now,
        updated_at=now,
    )


def get_by_id(output_id: str) -> Optional[Output]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM outputs WHERE id = ?", (output_id,)).fetchone()
    return _row_to_output(row) if row else None


def list_outputs(
    namespace: Optional[str] = None,
    output_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Output]:
    conditions, params = ["deleted_at IS NULL"], []
    if namespace:
        conditions.append("namespace = ?")
        params.append(namespace)
    if output_type:
        conditions.append("type = ?")
        params.append(output_type)
    if tags:
        for tag in tags:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
    where = "WHERE " + " AND ".join(conditions)
    params += [limit, offset]
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM outputs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_output(r) for r in rows]


def search(query: str, namespace: Optional[str] = None, limit: int = 20) -> list[OutputSearchResult]:
    """FTS5 full-text search across title, content, tags, summary."""
    if not query.strip():
        return []

    # Sanitise query for FTS5
    safe_query = re.sub(r'[^\w\s]', ' ', query).strip()
    if not safe_query:
        return []

    ns_filter = "AND o.namespace = ?" if namespace else ""
    params: list = [safe_query]
    if namespace:
        params.append(namespace)
    params.append(limit)

    try:
        with get_db() as conn:
            rows = conn.execute(
                f"""SELECT o.id, o.namespace, o.title, o.summary, o.type,
                           o.format, o.tags, o.size_bytes, o.created_at,
                           rank AS score
                    FROM outputs_fts
                    JOIN outputs o ON outputs_fts.rowid = o.rowid
                    WHERE outputs_fts MATCH ? {ns_filter}
                      AND o.deleted_at IS NULL
                    ORDER BY rank
                    LIMIT ?""",
                params,
            ).fetchall()
    except Exception as e:
        logger.error("FTS search failed: %s", e)
        return []

    return [_row_to_search_result(r) for r in rows]


def delete(output_id: str) -> bool:
    now = utcnow_str()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM outputs WHERE id = ? AND deleted_at IS NULL", (output_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE outputs SET deleted_at = ? WHERE id = ?", (now, output_id)
        )
    return True


def delete_bulk(ids: list[str]) -> tuple[list[str], list[str]]:
    """Soft-delete multiple outputs. Returns (deleted, failed)."""
    if not ids:
        return [], []
    ph = ",".join("?" * len(ids))
    now = utcnow_str()
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id FROM outputs WHERE id IN ({ph}) AND deleted_at IS NULL", ids
        ).fetchall()
        found_ids = [r["id"] for r in rows]
        if found_ids:
            ph2 = ",".join("?" * len(found_ids))
            conn.execute(
                f"UPDATE outputs SET deleted_at = ? WHERE id IN ({ph2})",
                [now] + found_ids,
            )
    failed = [i for i in ids if i not in set(found_ids)]
    return found_ids, failed


def export_text(output_id: str) -> Optional[str]:
    """Return raw content string."""
    out = get_by_id(output_id)
    return out.content if out else None


def export_json(output_id: str) -> Optional[dict]:
    out = get_by_id(output_id)
    if not out:
        return None
    return out.model_dump()


def get_stats(namespace: Optional[str] = None) -> dict:
    """Return counts and sizes by type."""
    conditions, params = ["deleted_at IS NULL"], []
    if namespace:
        conditions.append("namespace = ?")
        params.append(namespace)
    where = "WHERE " + " AND ".join(conditions)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT type, COUNT(*) as count, SUM(size_bytes) as total_bytes FROM outputs {where} GROUP BY type",
            params,
        ).fetchall()
    by_type = {r["type"]: {"count": r["count"], "total_bytes": r["total_bytes"] or 0} for r in rows}
    total_count = sum(v["count"] for v in by_type.values())
    total_bytes = sum(v["total_bytes"] for v in by_type.values())
    return {
        "total_count": total_count,
        "total_bytes": total_bytes,
        "by_type": by_type,
    }


def get_stats_all() -> dict:
    """Return global stats + per-namespace breakdown in a single query."""
    with get_db() as conn:
        ns_rows = conn.execute(
            "SELECT namespace, COUNT(*) as total_count, SUM(size_bytes) as total_bytes FROM outputs WHERE deleted_at IS NULL GROUP BY namespace"
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*), SUM(size_bytes) FROM outputs WHERE deleted_at IS NULL"
        ).fetchone()
        type_rows = conn.execute(
            "SELECT type, COUNT(*) as count, SUM(size_bytes) as total_bytes FROM outputs WHERE deleted_at IS NULL GROUP BY type"
        ).fetchall()

    by_namespace = {
        r["namespace"]: {"total_count": r["total_count"], "total_bytes": r["total_bytes"] or 0}
        for r in ns_rows
    }
    by_type = {r["type"]: {"count": r["count"], "total_bytes": r["total_bytes"] or 0} for r in type_rows}
    return {
        "total_count": total[0] or 0,
        "total_bytes": total[1] or 0,
        "by_namespace": by_namespace,
        "by_type": by_type,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_path_segment(s: str) -> str:
    """Strip path separators and dotdot sequences, bound length."""
    s = re.sub(r'[/\\]', '_', s)   # no separators
    s = re.sub(r'\.\.', '', s)      # no dotdot
    return s[:64] or "unknown"


def _write_file(output_id: str, namespace: str, output_type: str, format: str, content: str) -> Path:
    ext = {"markdown": "md", "json": "json", "html": "html"}.get(format, "txt")
    type_dir = output_type if output_type in ("reports", "drafts", "analyses", "code", "archive") else output_type + "s"
    store_dir = STORE_ROOT / _safe_path_segment(type_dir) / _safe_path_segment(namespace)
    # Guard: raise ValueError if path escaped STORE_ROOT
    store_dir.resolve().relative_to(STORE_ROOT.resolve())
    store_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    file_path = store_dir / f"{date_prefix}-{output_id[:8]}.{ext}"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _auto_tag(content: str, output_type: str) -> list[str]:
    tags = [output_type]
    content_lower = content.lower()
    for tag, keywords in _TAG_KEYWORDS.items():
        if any(kw.lower() in content_lower for kw in keywords):
            if tag != output_type:
                tags.append(tag)
    return tags


def _auto_summary(content: str, max_chars: int = 200) -> str:
    """Extract first meaningful sentence(s) as summary."""
    text = content.strip()
    # Strip markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*|__|\*|_|`', '', text)
    # Get first non-empty paragraph
    for para in text.split("\n"):
        para = para.strip()
        if len(para) > 20:
            return para[:max_chars] + ("…" if len(para) > max_chars else "")
    return text[:max_chars]


def _row_to_output(row) -> Output:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["output_type"] = d.pop("type", "report")
    d["file_path"] = d.get("file_path") or ""
    d["summary"] = d.get("summary") or ""
    return Output(**d)


def _row_to_search_result(row) -> OutputSearchResult:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["output_type"] = d.pop("type", "report")
    d["summary"] = d.get("summary") or ""
    d["score"] = float(d.get("score") or 0.0)
    return OutputSearchResult(**d)
