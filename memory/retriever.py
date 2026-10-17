"""Hybrid BM25 + Vector RAG retriever with RRF reranking — Phase 11.2.

Combines:
1. BM25 keyword scoring (rank-bm25) — great for exact terms, dates, proper nouns
2. ChromaDB semantic search — great for meaning and paraphrase
3. Reciprocal Rank Fusion (RRF) — merges both ranked lists optimally

Formula: score(d) = 1/(k+bm25_rank) + 1/(k+vector_rank)  where k=60

Falls back gracefully if rank-bm25 is unavailable (returns pure vector results).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Optional

from memory.schemas import MemoryEntry

logger = logging.getLogger("claudeos.memory.retriever")

_RRF_K = 60  # standard RRF constant — balances precision vs. recall

# BM25 corpus cache — keyed by namespace, stores (BM25Okapi, entries, expiry)
# Rebuilt on first query per namespace, then reused until TTL expires.
_bm25_cache: dict[str, tuple] = {}
_bm25_cache_lock = threading.Lock()
_BM25_CACHE_TTL = 300  # seconds — 5 min, matches namespace summary cache TTL

_RETRIEVER_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="retriever")


def invalidate_bm25_cache(namespace: str) -> None:
    """Call after writing/deleting memory entries so next search rebuilds corpus."""
    with _bm25_cache_lock:
        _bm25_cache.pop(namespace, None)


def hybrid_search(
    query: str,
    namespace: str,
    top_k: int = 5,
    min_confidence: float = 0.0,
    category: Optional[str] = None,
) -> list[MemoryEntry]:
    """Hybrid BM25+vector search with RRF reranking.

    Returns top_k entries merged from both retrieval paths, deduped.
    Each future has a 2.5s timeout — slow ChromaDB or BM25 degrades gracefully.
    """
    bm25_fut = _RETRIEVER_POOL.submit(_bm25_search, query, namespace, top_k * 2, min_confidence, category)
    vec_fut  = _RETRIEVER_POOL.submit(_vector_search, query, namespace, top_k * 2, min_confidence)

    try:
        bm25_results = bm25_fut.result(timeout=4.0)
    except (FutureTimeout, Exception) as e:
        logger.warning("BM25 timed out or failed: %s", e)
        bm25_results = []

    try:
        vec_results = vec_fut.result(timeout=4.0)
    except (FutureTimeout, Exception) as e:
        logger.warning("Vector search timed out or failed: %s", e)
        vec_results = []

    if not bm25_results and not vec_results:
        return []

    # If only one source available, return it directly
    if not bm25_results:
        return vec_results[:top_k]
    if not vec_results:
        return bm25_results[:top_k]

    # RRF merge
    return _rrf_merge(bm25_results, vec_results, top_k)


def _bm25_search(
    query: str,
    namespace: str,
    top_k: int,
    min_confidence: float,
    category: Optional[str],
) -> list[MemoryEntry]:
    """BM25 search over SQLite memory entries for this namespace.

    Corpus is cached per namespace for _BM25_CACHE_TTL seconds.
    Call invalidate_bm25_cache(namespace) after writes to force rebuild.
    """
    try:
        from rank_bm25 import BM25Okapi
        from memory import store

        now = time.monotonic()
        bm25 = None
        entries = None

        with _bm25_cache_lock:
            cached = _bm25_cache.get(namespace)
            if cached and now < cached[2]:
                bm25, entries, _ = cached

        if bm25 is None:
            entries = store.list_entries(
                namespace=namespace,
                category=category,
                min_confidence=min_confidence,
                limit=500,
            )
            if not entries:
                return []
            corpus = [f"{e.key} {e.value}".lower().split() for e in entries]
            bm25 = BM25Okapi(corpus)
            with _bm25_cache_lock:
                _bm25_cache[namespace] = (bm25, entries, now + _BM25_CACHE_TTL)
                if len(_bm25_cache) > 50:
                    oldest = sorted(_bm25_cache.keys(),
                                    key=lambda k: _bm25_cache[k][2])[:10]
                    for k in oldest:
                        _bm25_cache.pop(k, None)

        if not entries:
            return []

        scores = bm25.get_scores(query.lower().split())
        scored = sorted(zip(scores, entries), key=lambda x: -x[0])
        return [e for score, e in scored[:top_k] if score > 0]
    except ImportError:
        try:
            from memory import store
            return store.search_text(query, namespace, category, top_k)
        except Exception:
            return []
    except Exception as e:
        logger.warning("BM25 search failed: %s", e)
        return []


def _vector_search(
    query: str,
    namespace: str,
    top_k: int,
    min_confidence: float,
) -> list[MemoryEntry]:
    """ChromaDB semantic search."""
    try:
        from memory import engine as mem
        return mem.search_semantic(query, namespace, top_k=top_k, min_confidence=min_confidence)
    except Exception as e:
        logger.warning("Vector search failed: %s", e)
        return []


def _rrf_merge(
    list_a: list[MemoryEntry],
    list_b: list[MemoryEntry],
    top_k: int,
) -> list[MemoryEntry]:
    """Merge two ranked lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    entry_map: dict[str, MemoryEntry] = {}

    for rank, entry in enumerate(list_a):
        scores[entry.id] = scores.get(entry.id, 0) + 1.0 / (_RRF_K + rank + 1)
        entry_map[entry.id] = entry

    for rank, entry in enumerate(list_b):
        scores[entry.id] = scores.get(entry.id, 0) + 1.0 / (_RRF_K + rank + 1)
        entry_map[entry.id] = entry

    ranked_ids = sorted(scores.keys(), key=lambda eid: -scores[eid])
    return [entry_map[eid] for eid in ranked_ids[:top_k]]
