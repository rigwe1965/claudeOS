"""Memory Engine — unified facade for all memory operations.

All agents and workflows call this module. Never call store.py or
vector_store.py directly from outside the memory package.

Write path:
    engine.write() → store.write() + vector_store.upsert()

Read paths:
    1. engine.get()             — exact namespace+key lookup (SQLite)
    2. engine.search_text()     — FTS5 keyword search (SQLite)
    3. engine.search_semantic() — cosine similarity (ChromaDB → join SQLite)

Agent context injection:
    engine.get_agent_context()  — high-confidence facts for system prompt
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from memory import store, vector_store
from memory.schemas import (
    MemoryEntry,
    MemoryEntryCreate,
    MemoryEntryUpdate,
    MemorySearchRequest,
)
from core.database import get_db
from core.utils import new_id, utcnow_str

logger = logging.getLogger("claudeos.memory.engine")

# Background thread pool for ChromaDB upserts and event log inserts.
# These are fire-and-forget — callers get the SQLite entry back immediately.
# max_workers=2: one for upserts, one for log events; keeps GIL pressure low.
_bg_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem-bg")

# Dedicated pool for parallel search ("both" mode) — separate from _bg_pool so
# fire-and-forget upserts don't block blocking search futures.
_search_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem-search")

# In-process TTL cache for get_agent_context: key → (result_str, expiry_epoch)
_context_cache: dict[tuple, tuple[str, float]] = {}
_CONTEXT_CACHE_TTL = 60.0  # seconds
_CONTEXT_CACHE_MAX = 100   # max entries — evict oldest 20% when exceeded


def write(
    namespace: str,
    category: str,
    key: str,
    value: str,
    source: str = "user",
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    confidence: float = 1.0,
    expires_at: Optional[datetime] = None,
) -> MemoryEntry:
    """Write a memory entry. Upserts on same namespace+key.

    SQLite write is synchronous (returns entry immediately).
    ChromaDB embed + vector metadata + event log run in a background thread
    so the caller is not blocked by sentence-transformer inference (~50-200ms).
    """
    entry_create = MemoryEntryCreate(
        namespace=namespace,
        category=category,
        key=key,
        value=value,
        source=source,
        agent_id=agent_id,
        session_id=session_id,
        tags=tags or [],
        confidence=confidence,
        expires_at=expires_at,
    )
    entry = store.write(entry_create)

    # Invalidate BM25 corpus cache for this namespace — next search rebuilds.
    try:
        from memory.retriever import invalidate_bm25_cache
        invalidate_bm25_cache(namespace)
    except Exception:
        pass

    # M4: Backpressure warning — log if embed queue is building up
    _qsize = _bg_pool._work_queue.qsize()
    if _qsize > 100:
        logger.warning("Memory write queue backlog: %d items — embeddings lagging behind writes", _qsize)

    # Fire-and-forget: ChromaDB upsert + vector metadata + event log.
    # Semantic search has eventual consistency (~100-300ms lag after write).
    # FTS5 / exact-key lookups are immediately consistent (SQLite already committed above).
    _bg_pool.submit(_upsert_vector, entry.id, entry.key, entry.value, namespace, category, key, confidence)

    return entry


def _upsert_vector(
    entry_id: str,
    entry_key: str,
    entry_value: str,
    namespace: str,
    category: str,
    key: str,
    confidence: float,
) -> None:
    """Background: embed into ChromaDB, record vector metadata and event log."""
    embed_text = f"{entry_key}: {entry_value}"
    chroma_id = vector_store.upsert(
        memory_id=entry_id,
        namespace=namespace,
        text=embed_text,
        metadata={
            "namespace": namespace,
            "category": category,
            "key": key,
            "confidence": str(confidence),
        },
    )
    if chroma_id:
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_vectors(id, memory_id, chroma_id) VALUES (?, ?, ?)",
                    (new_id(), entry_id, chroma_id),
                )
                conn.execute(
                    "INSERT INTO system_events(id, event_type, namespace, payload) VALUES (?, ?, ?, ?)",
                    (new_id(), "memory_write", namespace, json.dumps({"key": key, "category": category})),
                )
        except Exception as e:
            logger.warning("Failed to record vector metadata or event: %s", e)
    else:
        _do_log_event("memory_write", namespace, {"key": key, "category": category})


def get(namespace: str, key: str) -> Optional[MemoryEntry]:
    """Exact key lookup within a namespace."""
    return store.get_by_key(namespace, key)


def get_by_id(entry_id: str) -> Optional[MemoryEntry]:
    return store.get_by_id(entry_id)


def list_entries(
    namespace: Optional[str] = None,
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryEntry]:
    return store.list_entries(namespace, category, min_confidence, limit=limit, offset=offset)


def update(entry_id: str, update_data: MemoryEntryUpdate) -> Optional[MemoryEntry]:
    entry = store.update(entry_id, update_data)
    if entry and update_data.value is not None:
        # Re-embed async — sentence-transformer inference (~50-200ms) must not block caller
        _bg_pool.submit(
            vector_store.upsert,
            entry.id, entry.namespace,
            f"{entry.key}: {entry.value}",
            {"namespace": entry.namespace, "category": entry.category, "key": entry.key},
        )
    return entry


def delete(entry_id: str) -> bool:
    entry = store.get_by_id(entry_id)
    if entry:
        vector_store.delete(entry.id, entry.namespace)
    return store.delete(entry_id)


def search_text(
    query: str,
    namespace: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
) -> list[MemoryEntry]:
    """FTS5 keyword search."""
    return store.search_text(query, namespace, category, limit)


def search_semantic(
    query: str,
    namespace: str,
    top_k: int = 5,
    min_confidence: float = 0.0,
) -> list[MemoryEntry]:
    """Semantic search via ChromaDB → hydrate from SQLite in a single IN query."""
    hits = vector_store.search(query, namespace, top_k=top_k)
    if not hits:
        return []
    # Preserve ChromaDB ordering by mapping memory_id → hit position
    memory_ids = [h["memory_id"] for h in hits]
    order_map = {mid: idx for idx, mid in enumerate(memory_ids)}
    placeholders = ",".join("?" * len(memory_ids))
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT * FROM memory_entries
                WHERE id IN ({placeholders})
                  AND confidence >= ?
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)""",
            (*memory_ids, min_confidence),
        ).fetchall()
    from memory.store import _row_to_entry
    entries = [_row_to_entry(r) for r in rows]
    entries.sort(key=lambda e: order_map.get(e.id, len(memory_ids)))
    return entries


def search(req: MemorySearchRequest) -> list[MemoryEntry]:
    """Unified search dispatcher."""
    if req.mode == "text":
        return search_text(req.query, req.namespace, req.category, req.top_k)
    if req.mode == "semantic":
        ns = req.namespace or "global"
        return search_semantic(req.query, ns, req.top_k, req.min_confidence)
    # "both" — run FTS5 + ChromaDB concurrently via module-level pool (no per-call allocation)
    sem_ns = req.namespace or "global"
    t_fut = _search_pool.submit(search_text, req.query, req.namespace, req.category, req.top_k)
    s_fut = _search_pool.submit(search_semantic, req.query, sem_ns, req.top_k, req.min_confidence)
    text_results = t_fut.result()
    sem_results = s_fut.result()
    seen: set[str] = set()
    merged: list[MemoryEntry] = []
    for e in text_results + sem_results:
        if e.id not in seen:
            seen.add(e.id)
            merged.append(e)
    return merged[: req.top_k]


def expire_stale() -> int:
    """Delete expired entries from SQLite and ChromaDB (bulk ChromaDB delete)."""
    with get_db() as conn:
        expired_rows = conn.execute(
            "SELECT id, namespace FROM memory_entries WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
        ).fetchall()

    if expired_rows:
        # Group by namespace — one ChromaDB collection.delete() call per namespace
        from collections import defaultdict
        by_ns: dict[str, list[str]] = defaultdict(list)
        for row in expired_rows:
            by_ns[row["namespace"]].append(row["id"])
        for ns, ids in by_ns.items():
            try:
                vector_store.delete_bulk(ids, ns)
            except Exception as e:
                logger.warning("Bulk ChromaDB delete failed for %s: %s", ns, e)

    count = store.expire_stale()
    logger.info("Expired %d stale memory entries", count)
    return count


def namespace_counts() -> dict[str, int]:
    return store.namespace_counts()


def get_agent_context(namespace: str, min_confidence: float = 0.8) -> str:
    """Build context string for injection into agent system prompts.

    Results are cached in-process for 60 seconds keyed on (namespace, min_confidence).
    """
    cache_key = (namespace, min_confidence)
    cached = _context_cache.get(cache_key)
    if cached is not None:
        result, expiry = cached
        if time.monotonic() < expiry:
            return result

    entries = store.get_context_for_agent(namespace, min_confidence)
    if not entries:
        result = ""
    else:
        lines = [f"## ClaudeOS Memory Context [{namespace}]"]
        for e in entries:
            lines.append(f"- [{e.category}] {e.key}: {e.value}  (confidence: {e.confidence:.2f})")
        result = "\n".join(lines)

    _context_cache[cache_key] = (result, time.monotonic() + _CONTEXT_CACHE_TTL)
    # Evict oldest 20% when over limit — dicts preserve insertion order (Python 3.7+)
    if len(_context_cache) > _CONTEXT_CACHE_MAX:
        for k in list(_context_cache.keys())[:_CONTEXT_CACHE_MAX // 5]:
            _context_cache.pop(k, None)
    return result


def _log_event(event_type: str, namespace: str, payload: dict) -> None:
    """Fire-and-forget event log insert."""
    _bg_pool.submit(_do_log_event, event_type, namespace, payload)


def _do_log_event(event_type: str, namespace: str, payload: dict) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO system_events(id, event_type, namespace, payload) VALUES (?, ?, ?, ?)",
                (new_id(), event_type, namespace, json.dumps(payload)),
            )
    except Exception:
        pass
