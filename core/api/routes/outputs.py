"""Output Manager REST API routes."""
from __future__ import annotations

from flask import Blueprint, jsonify, request, Response

from core.auth import require_auth, require_role, require_write, effective_namespace, can_access_namespace, is_scoped

_OUTPUT_ROLES = ("admin", "operator", "client", "viewer")  # staff is tickets-only; unknown roles fail closed


def require_api_key(f):
    """Authenticate, then reject roles with no output access (checked on every route)."""
    return require_auth(require_role(*_OUTPUT_ROLES)(f))

outputs_bp = Blueprint("outputs", __name__, url_prefix="/api/v1/outputs")


@outputs_bp.get("")
@require_api_key
def list_outputs():
    from outputs.manager import list_outputs as _list
    namespace = effective_namespace(request.args.get("namespace"))
    output_type = request.args.get("type")
    tags = request.args.getlist("tag")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    outputs = _list(namespace=namespace, output_type=output_type, tags=tags or None, limit=limit, offset=offset)
    return jsonify([_out_dict(o) for o in outputs])


@outputs_bp.post("")
@require_api_key
@require_write
def save_output():
    from outputs.manager import save
    from outputs.schemas import OutputSave, OUTPUT_TYPES
    body = request.get_json(silent=True) or {}
    if is_scoped():
        body["namespace"] = effective_namespace(body.get("namespace"))
    try:
        data = OutputSave(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422
    if data.output_type not in OUTPUT_TYPES:
        return jsonify({"error": f"output_type must be one of: {', '.join(OUTPUT_TYPES)}"}), 422
    out = save(
        namespace=data.namespace,
        title=data.title,
        content=data.content,
        output_type=data.output_type,
        format=data.format,
        tags=data.tags,
        agent_run_id=data.agent_run_id,
        workflow_run_id=data.workflow_run_id,
        project_id=data.project_id,
        summary=data.summary,
    )
    return jsonify(_out_dict(out)), 201


@outputs_bp.get("/search")
@require_api_key
def search_outputs():
    from outputs.manager import search
    query = request.args.get("q", "")
    namespace = effective_namespace(request.args.get("namespace"))
    limit = min(int(request.args.get("limit", 20)), 100)
    if not query:
        return jsonify({"error": "q parameter required"}), 400
    results = search(query, namespace=namespace, limit=limit)
    return jsonify([r.model_dump() for r in results])


@outputs_bp.get("/stats/all")
@require_api_key
def output_stats_all():
    """Aggregated stats (global + by_namespace + by_type) in one call."""
    from outputs.manager import get_stats_all
    if is_scoped():
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(get_stats_all())


@outputs_bp.get("/stats")
@require_api_key
def output_stats():
    from outputs.manager import get_stats
    namespace = effective_namespace(request.args.get("namespace"))
    return jsonify(get_stats(namespace=namespace))


@outputs_bp.delete("/bulk")
@require_api_key
@require_write
def bulk_delete_outputs():
    from outputs.manager import delete_bulk as _del_bulk
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422
    if len(ids) > 200 or not all(isinstance(i, str) for i in ids):
        return jsonify({"error": "max 200 string ids per request"}), 422
    if is_scoped():
        from outputs.manager import get_by_id
        own = [i for i in ids if (o := get_by_id(i)) and can_access_namespace(o.namespace)]
        ids_denied = [i for i in ids if i not in set(own)]
        deleted, failed = _del_bulk(own) if own else ([], [])
        return jsonify({"deleted": deleted, "failed": failed + ids_denied, "count": len(deleted)})
    deleted, failed = _del_bulk(ids)
    return jsonify({"deleted": deleted, "failed": failed, "count": len(deleted)})


@outputs_bp.get("/<output_id>")
@require_api_key
def get_output(output_id: str):
    from outputs.manager import get_by_id
    out = get_by_id(output_id)
    if not out:
        return jsonify({"error": "Output not found"}), 404
    if not can_access_namespace(out.namespace):
        return jsonify({"error": "Output not found"}), 404
    return jsonify(_out_dict(out, include_content=True))


@outputs_bp.get("/<output_id>/content")
@require_api_key
def get_content(output_id: str):
    """Return raw content as plain text."""
    from outputs.manager import get_by_id
    out = get_by_id(output_id)
    if not out:
        return jsonify({"error": "Output not found"}), 404
    if not can_access_namespace(out.namespace):
        return jsonify({"error": "Output not found"}), 404
    return Response(out.content, mimetype="text/plain; charset=utf-8")


@outputs_bp.get("/<output_id>/export")
@require_api_key
def export_output(output_id: str):
    import re as _re
    from outputs.manager import get_by_id
    out = get_by_id(output_id)
    if not out:
        return jsonify({"error": "Output not found"}), 404
    if not can_access_namespace(out.namespace):
        return jsonify({"error": "Output not found"}), 404
    fmt = request.args.get("format", "json")
    if fmt == "json":
        return jsonify(out.model_dump())
    elif fmt in ("markdown", "text"):
        safe = _re.sub(r"[^\w\s-]", "", out.title[:40]).strip().replace(" ", "_")
        ext = "md" if fmt == "markdown" else "txt"
        fname = f"{safe or output_id[:8]}.{ext}"
        mime = "text/markdown" if fmt == "markdown" else "text/plain"
        return Response(
            out.content,
            mimetype=mime,
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    return jsonify({"error": f"Unknown format: {fmt}"}), 400


@outputs_bp.delete("/<output_id>")
@require_api_key
@require_write
def delete_output(output_id: str):
    from outputs.manager import get_by_id, delete
    out = get_by_id(output_id)
    if not out:
        return jsonify({"error": "Output not found"}), 404
    if not can_access_namespace(out.namespace):
        return jsonify({"error": "Output not found"}), 404
    if not delete(output_id):
        return jsonify({"error": "Output not found"}), 404
    return jsonify({"deleted": output_id})


# ── helpers ───────────────────────────────────────────────────────────────────

def _out_dict(o, include_content: bool = False) -> dict:
    d = {
        "id": o.id,
        "namespace": o.namespace,
        "title": o.title,
        "summary": o.summary,
        "output_type": o.output_type,
        "format": o.format,
        "tags": o.tags,
        "size_bytes": o.size_bytes,
        "file_path": o.file_path,
        "agent_run_id": o.agent_run_id,
        "workflow_run_id": o.workflow_run_id,
        "created_at": o.created_at,
    }
    if include_content:
        d["content"] = o.content
    return d
