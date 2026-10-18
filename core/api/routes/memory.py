"""Memory API routes — /api/v1/memory/*"""
from flask import Blueprint, jsonify, request, g

from memory import engine
from memory.schemas import (
    MemoryEntryCreate,
    MemoryEntryUpdate,
    MemorySearchRequest,
)
from core.auth import require_auth, require_role, effective_namespace, can_access_namespace, is_scoped
from core.utils import utcnow_str

_MEMORY_ROLES = ("admin", "operator", "client", "viewer")  # staff is tickets-only; unknown roles fail closed


def require_memory_access(f):
    """Authenticate, then reject roles with no memory access (checked on every route)."""
    return require_auth(require_role(*_MEMORY_ROLES)(f))


memory_bp = Blueprint("memory", __name__, url_prefix="/api/v1/memory")


def _entry_dict(e) -> dict:
    return {
        "id": e.id,
        "namespace": e.namespace,
        "category": e.category,
        "key": e.key,
        "value": e.value,
        "source": e.source,
        "agent_id": e.agent_id,
        "session_id": e.session_id,
        "tags": e.tags,
        "confidence": e.confidence,
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@memory_bp.get("")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def list_memory():
    namespace = effective_namespace(request.args.get("namespace"))
    category = request.args.get("category")
    min_confidence = float(request.args.get("min_confidence", 0.0))
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    entries = engine.list_entries(namespace, category, min_confidence, limit=limit, offset=offset)

    # M1: Audit read access — trace for exfiltration detection
    try:
        from core.auth import audit_log
        audit_log(
            "memory_read",
            user_id=g.get("user_id"),
            username=g.get("username"),
            namespace=namespace,
            detail={"count": len(entries), "category": category},
        )
    except Exception:
        pass

    return jsonify({
        "entries": [_entry_dict(e) for e in entries],
        "count": len(entries),
    })


@memory_bp.post("")
@require_auth
@require_role("admin", "operator", "client")
def write_memory():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Enforce namespace for client/viewer roles
    forced_ns = effective_namespace(data.get("namespace"))
    if forced_ns:
        data["namespace"] = forced_ns

    try:
        entry_create = MemoryEntryCreate(**data)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    # Cap value size — prevents DoS via huge ChromaDB embed + FTS5 index bloat
    _MAX_VALUE_BYTES = 65536  # 64 KB
    if len((entry_create.value or "").encode("utf-8")) > _MAX_VALUE_BYTES:
        return jsonify({"error": f"value exceeds maximum size of {_MAX_VALUE_BYTES // 1024}KB"}), 422

    entry = engine.write(
        namespace=entry_create.namespace,
        category=entry_create.category,
        key=entry_create.key,
        value=entry_create.value,
        source=entry_create.source,
        agent_id=entry_create.agent_id,
        session_id=entry_create.session_id,
        tags=entry_create.tags,
        confidence=entry_create.confidence,
        expires_at=entry_create.expires_at,
    )
    return jsonify(_entry_dict(entry)), 201


@memory_bp.delete("/bulk")
@require_auth
@require_role("admin", "operator", "client")
def bulk_delete_memory():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422

    from core.database import get_db
    from memory import vector_store as vs

    deleted, failed = [], []

    # Single batch fetch for permission checks
    with get_db() as conn:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, namespace FROM memory_entries WHERE id IN ({placeholders}) AND archived=0",
            ids,
        ).fetchall()

    fetched = {r["id"]: r["namespace"] for r in rows}
    valid_ids: list[str] = []
    ids_by_ns: dict[str, list[str]] = {}

    for eid in ids:
        if eid not in fetched:
            failed.append(eid)
            continue
        ns = fetched[eid]
        allowed_ns = effective_namespace(ns)
        if allowed_ns is None or ns != allowed_ns:
            failed.append(eid)
            continue
        valid_ids.append(eid)
        ids_by_ns.setdefault(ns, []).append(eid)

    if valid_ids:
        # Batch SQLite delete — one round-trip for all valid IDs
        with get_db() as conn:
            placeholders = ",".join("?" * len(valid_ids))
            conn.execute(
                f"DELETE FROM memory_entries WHERE id IN ({placeholders})", valid_ids
            )
        # Batch ChromaDB delete per namespace
        for ns, ns_ids in ids_by_ns.items():
            try:
                vs.delete_bulk(ns_ids, ns)
            except Exception:
                pass
        deleted = valid_ids

    return jsonify({"deleted": deleted, "failed": failed, "count": len(deleted)})


@memory_bp.get("/<entry_id>")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def get_memory(entry_id: str):
    entry = engine.get_by_id(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    if not can_access_namespace(entry.namespace):
        return jsonify({"error": "Not found"}), 404  # 404, not 403 — don't confirm existence
    return jsonify(_entry_dict(entry))


@memory_bp.put("/<entry_id>")
@require_auth
@require_role("admin", "operator", "client")
def update_memory(entry_id: str):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    entry = engine.get_by_id(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    if not can_access_namespace(entry.namespace):
        return jsonify({"error": "Not found"}), 404

    try:
        update_data = MemoryEntryUpdate(**data)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    entry = engine.update(entry_id, update_data)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_entry_dict(entry))


@memory_bp.delete("/<entry_id>")
@require_auth
@require_role("admin", "operator", "client")
def delete_memory(entry_id: str):
    entry = engine.get_by_id(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    if not can_access_namespace(entry.namespace):
        return jsonify({"error": "Not found"}), 404
    deleted = engine.delete(entry_id)
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": entry_id})


@memory_bp.post("/search")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def search_memory():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Enforce namespace for client/viewer
    forced_ns = effective_namespace(data.get("namespace"))
    if forced_ns:
        data["namespace"] = forced_ns

    try:
        req = MemorySearchRequest(**data)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    entries = engine.search(req)
    return jsonify({
        "query": req.query,
        "mode": req.mode,
        "namespace": req.namespace,
        "results": [_entry_dict(e) for e in entries],
        "count": len(entries),
    })


@memory_bp.post("/import")
@require_memory_access
@require_role("admin", "operator")
def import_memory():
    from pathlib import Path
    from core.config import get_settings
    from memory.importer import import_directory

    settings = get_settings()
    memory_dir = Path(settings.CLAUDE_MEMORY_PATH)
    namespace = effective_namespace(request.args.get("namespace", "global")) or "global"

    if not memory_dir.exists():
        return jsonify({"error": f"Memory directory not found: {memory_dir}"}), 400

    results = import_directory(memory_dir, namespace=namespace)
    total = sum(results.values())
    return jsonify({
        "imported": total,
        "total_files": len(results),
        "results": results,
        "timestamp": utcnow_str(),
    })


@memory_bp.get("/namespaces")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def list_namespaces():
    counts = engine.namespace_counts()
    if is_scoped():
        own = effective_namespace(None)
        counts = {k: v for k, v in counts.items() if k == own} if isinstance(counts, dict) else [c for c in counts if (c.get("namespace") if isinstance(c, dict) else c) == own]
    return jsonify({"namespaces": counts})


@memory_bp.delete("/expire")
@require_memory_access
@require_role("admin", "operator")
def expire_memory():
    count = engine.expire_stale()
    return jsonify({"expired": count, "timestamp": utcnow_str()})


@memory_bp.get("/context/<namespace>")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def agent_context(namespace: str):
    min_confidence = float(request.args.get("min_confidence", 0.8))
    if not can_access_namespace(namespace):
        return jsonify({"error": "Not found"}), 404
    safe_ns = namespace
    context_str = engine.get_agent_context(safe_ns, min_confidence)
    return jsonify({"namespace": safe_ns, "context": context_str})


@memory_bp.post("/consolidate")
@require_memory_access
@require_role("admin", "operator")
def consolidate_memory():
    """Trigger memory consolidation — Phase 11.1."""
    from memory.consolidator import run_consolidation
    body = request.get_json(silent=True) or {}
    namespace = body.get("namespace")  # None = all namespaces
    dry_run = bool(body.get("dry_run", False))
    stats = run_consolidation(namespace=namespace, dry_run=dry_run)
    return jsonify(stats)


@memory_bp.get("/hybrid-search")
@require_auth
@require_role("admin", "operator", "client", "viewer")
def hybrid_search():
    """Hybrid BM25+vector search with RRF — Phase 11.2."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q param required"}), 400
    namespace = effective_namespace(request.args.get("namespace", "global"))
    top_k = min(int(request.args.get("top_k", 10)), 50)
    from memory.retriever import hybrid_search as _hybrid
    results = _hybrid(query=query, namespace=namespace or "global", top_k=top_k)
    return jsonify({
        "results": [_entry_dict(e) for e in results],
        "count": len(results),
        "query": query,
        "namespace": namespace,
    })


