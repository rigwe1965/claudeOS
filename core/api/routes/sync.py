"""Phase 7 — Sync API routes."""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from core.auth import require_auth, require_role


def require_api_key(f):
    """All sync routes are admin/operator only."""
    return require_auth(require_role("admin", "operator")(f))

logger = logging.getLogger("claudeos.api.sync")
sync_bp = Blueprint("sync", __name__, url_prefix="/api/v1/sync")


@sync_bp.get("/status")
@require_api_key
def get_status():
    from sync.engine import get_status
    return jsonify(get_status())


_ALLOWED_SYNC_TABLES = {
    "memory_entries", "agent_runs", "outputs", "namespaces", "projects",
    "system_events", "users", "tickets", "workflows",
}


@sync_bp.post("/push")
@require_api_key
def push_all():
    from sync.engine import push_all, push_table
    table = request.json.get("table") if request.is_json else None
    if table:
        if table not in _ALLOWED_SYNC_TABLES:
            return jsonify({"error": f"Unknown table: {table}"}), 400
        result = push_table(table)
        return jsonify(result.model_dump())
    result = push_all()
    return jsonify(result.model_dump()), 200 if result.success else 207


@sync_bp.post("/reset-watermark")
@require_api_key
def reset_watermark():
    from sync.engine import reset_watermark
    table = request.json.get("table") if request.is_json else None
    reset_watermark(table)
    return jsonify({"ok": True, "table": table or "all"})


@sync_bp.get("/log")
@require_api_key
def get_log():
    from sync.engine import get_sync_log
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify(get_sync_log(limit))


@sync_bp.delete("/log/<log_id>")
@require_api_key
def delete_log_entry(log_id):
    from sync.engine import delete_log_entries
    deleted = delete_log_entries([log_id])
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True, "deleted": deleted})


@sync_bp.delete("/log")
@require_api_key
def bulk_delete_log():
    ids = (request.json or {}).get("ids", [])
    if not ids:
        return jsonify({"error": "ids required"}), 400
    if len(ids) > 200:
        return jsonify({"error": "max 200 ids per request"}), 400
    from sync.engine import delete_log_entries
    deleted = delete_log_entries(ids)
    return jsonify({"ok": True, "deleted": deleted})
