"""ChromaDB vector store wrapper.

One ChromaDB collection per namespace, using sentence-transformers
all-MiniLM-L6-v2 for embeddings.

Falls back gracefully if ChromaDB is unavailable — semantic search
returns empty list instead of crashing.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.config import get_settings

logger = logging.getLogger("claudeos.memory.vector")

_client = None
_ef = None   # embedding function
_collections: dict = {}
_init_lock = __import__("threading").Lock()
_init_failed = False  # M3: set True when ChromaDB init fails — used by health checks


def _init():
    global _client, _ef
    if _client is not None:
        return True
    with _init_lock:
        if _client is not None:  # double-checked locking — another thread may have init'd
            return True
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            settings = get_settings()
            _client = chromadb.PersistentClient(path=str(settings.chromadb_path))
            _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            return True
        except Exception as e:
            global _init_failed
            _init_failed = True
            logger.warning("ChromaDB unavailable — semantic search disabled: %s", e)
            return False


def _collection(namespace: str):
    if namespace in _collections:
        return _collections[namespace]
    if not _init():
        return None
    try:
        col = _client.get_or_create_collection(
            name=f"memory_{namespace.replace('-', '_')}",
            embedding_function=_ef,
            metadata={"hnsw:space": "cosine"},
        )
        _collections[namespace] = col
        return col
    except Exception as e:
        logger.warning("Could not get collection for namespace %s: %s", namespace, e)
        return None


def upsert(memory_id: str, namespace: str, text: str, metadata: dict) -> Optional[str]:
    """Embed and store a memory entry. Returns chroma_id or None on failure."""
    col = _collection(namespace)
    if col is None:
        return None
    chroma_id = f"mem_{memory_id}"
    try:
        col.upsert(
            ids=[chroma_id],
            documents=[text],
            metadatas=[{k: str(v) for k, v in metadata.items() if v is not None}],
        )
        return chroma_id
    except Exception as e:
        logger.error("ChromaDB upsert failed for %s: %s", memory_id, e)
        return None


def delete(memory_id: str, namespace: str) -> None:
    col = _collection(namespace)
    if col is None:
        return
    try:
        col.delete(ids=[f"mem_{memory_id}"])
    except Exception as e:
        logger.warning("ChromaDB delete failed for %s: %s", memory_id, e)


def delete_bulk(memory_ids: list[str], namespace: str) -> None:
    """Delete multiple entries in a single ChromaDB call."""
    if not memory_ids:
        return
    col = _collection(namespace)
    if col is None:
        return
    try:
        col.delete(ids=[f"mem_{mid}" for mid in memory_ids])
    except Exception as e:
        logger.warning("ChromaDB bulk delete failed for namespace %s: %s", namespace, e)


def search(
    query: str,
    namespace: str,
    top_k: int = 5,
    where: Optional[dict] = None,
) -> list[dict]:
    """Semantic search. Returns list of {chroma_id, memory_id, distance, metadata}."""
    col = _collection(namespace)
    if col is None:
        return []
    try:
        results = col.query(
            query_texts=[query],
            n_results=min(top_k, col.count() or 1),
            where=where,
            include=["distances", "metadatas"],
        )
        output = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for cid, dist, meta in zip(ids, distances, metadatas):
            memory_id = cid.removeprefix("mem_")
            output.append({
                "chroma_id": cid,
                "memory_id": memory_id,
                "distance": dist,
                "metadata": meta,
            })
        return output
    except Exception as e:
        logger.error("ChromaDB search failed: %s", e)
        return []


def count(namespace: str) -> int:
    col = _collection(namespace)
    if col is None:
        return 0
    try:
        return col.count()
    except Exception:
        return 0
