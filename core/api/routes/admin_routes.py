"""Admin routes — /api/v1/admin/* (admin role only)."""
from __future__ import annotations

import json
import logging
from flask import Blueprint, jsonify, request, g

logger = logging.getLogger("claudeos.admin")

from core.auth import (
    audit_log, clear_failed_attempts, create_access_token, create_user,
    get_user_by_id, hash_password, require_auth, require_role,
    revoke_session, revoke_user_access, validate_password_strength, _cfg_cache,
)
from core.database import get_db
from core.utils import new_id

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

# Hardcoded column map — SQL column names are never taken from request keys directly
_ALLOWED_USER_UPDATES = {
    "role":                 "role",
    "namespace":            "namespace",
    "is_active":            "is_active",
    "email":                "email",
    "must_change_password": "must_change_password",
}


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.get("/users")
@require_auth
@require_role("admin")
def list_users():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, email, role, namespace, is_active, must_change_password, failed_attempts, locked_until, last_login_at, created_at, updated_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([_user_dict(r) for r in rows])


@admin_bp.post("/users")
@require_auth
@require_role("admin")
def create_user_admin():
    body = request.get_json(silent=True) or {}
    username             = (body.get("username") or "").strip()
    password             = body.get("password") or ""
    role                 = body.get("role", "viewer")
    namespace            = body.get("namespace") or None
    email                = body.get("email") or None
    must_change_password = bool(body.get("must_change_password", False))

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if role not in ("admin", "operator", "client", "viewer"):
        return jsonify({"error": "Invalid role"}), 422
    if role in ("client", "viewer") and not namespace:
        return jsonify({"error": "namespace required for client/viewer roles"}), 422

    err = validate_password_strength(password, username)
    if err:
        return jsonify({"error": err}), 422

    try:
        user = create_user(username, password, role=role, namespace=namespace,
                           email=email, must_change_password=must_change_password)
    except Exception as e:
        msg = str(e)
        if "UNIQUE constraint failed: users.email" in msg:
            return jsonify({"error": "Email already registered"}), 409
        if "UNIQUE constraint failed: users.username" in msg:
            return jsonify({"error": "Username already taken"}), 409
        logger.exception("User creation failed unexpectedly")
        return jsonify({"error": "Failed to create user"}), 500

    audit_log("user_created", user_id=g.user_id, username=g.username, detail={"created_user": username, "role": role})
    return jsonify(_user_dict_full(user)), 201


@admin_bp.get("/users/<user_id>")
@require_auth
@require_role("admin")
def get_user(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_dict_full(user))


@admin_bp.patch("/users/<user_id>")
@require_auth
@require_role("admin")
def update_user(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    # Derive SQL column names from the hardcoded map — never from request keys directly
    updates = {_ALLOWED_USER_UPDATES[k]: v for k, v in body.items() if k in _ALLOWED_USER_UPDATES}

    if "role" in updates and updates["role"] not in ("admin", "operator", "client", "viewer"):
        return jsonify({"error": "Invalid role"}), 422
    final_role = updates.get("role", user["role"])
    final_ns = updates["namespace"] if "namespace" in updates else user.get("namespace")
    if ("role" in updates or "namespace" in updates) and final_role in ("client", "viewer") and not final_ns:
        return jsonify({"error": "namespace required for client/viewer roles"}), 422

    if updates:
        set_clauses = ", ".join(f"{col} = ?" for col in updates)
        vals = list(updates.values()) + [user_id]
        with get_db() as conn:
            conn.execute(f"UPDATE users SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
        if {"role", "namespace", "is_active"} & set(updates):
            revoke_user_access(user_id)

    audit_log("user_updated", user_id=g.user_id, username=g.username, detail={"target": user_id, "updates": list(updates.keys())})
    return jsonify(_user_dict_full(get_user_by_id(user_id)))


@admin_bp.delete("/users/<user_id>")
@require_auth
@require_role("admin")
def deactivate_user(user_id: str):
    if user_id == g.user_id:
        return jsonify({"error": "Cannot deactivate your own account"}), 400
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    with get_db() as conn:
        conn.execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    revoke_user_access(user_id)
    audit_log("user_deactivated", user_id=g.user_id, username=g.username, detail={"target": user_id})
    return jsonify({"deactivated": user_id})


@admin_bp.delete("/users/bulk")
@require_auth
@require_role("admin")
def bulk_deactivate_users():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422
    safe = [i for i in ids if i != g.user_id]
    if not safe:
        return jsonify({"error": "Cannot deactivate your own account"}), 400
    placeholders = ",".join("?" * len(safe))
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM users WHERE id IN ({placeholders})", safe
        ).fetchall()
        deactivated = [r["id"] for r in existing]
        if deactivated:
            ph2 = ",".join("?" * len(deactivated))
            conn.execute(
                f"UPDATE users SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id IN ({ph2})",
                deactivated,
            )
        for _uid in deactivated:
            revoke_user_access(_uid)
    audit_log("bulk_users_deactivated", user_id=g.user_id, username=g.username, detail={"targets": deactivated})
    return jsonify({"deactivated": deactivated, "count": len(deactivated)})


@admin_bp.delete("/users/<user_id>/permanent")
@require_auth
@require_role("admin")
def hard_delete_user(user_id: str):
    """Permanently remove a user and all their sessions/events from the DB."""
    if user_id == g.user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    # Prevent deleting the last admin
    with get_db() as conn:
        admin_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1"
        ).fetchone()[0]
        if user["role"] == "admin" and admin_count <= 1:
            return jsonify({"error": "Cannot delete the last active admin"}), 400
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM auth_events WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    audit_log("user_deleted", user_id=g.user_id, username=g.username,
              detail={"target_id": user_id, "target_username": user["username"]})
    return jsonify({"deleted": user_id, "username": user["username"]})


@admin_bp.post("/users/<user_id>/unlock")
@require_auth
@require_role("admin")
def unlock_user(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    clear_failed_attempts(user_id)
    audit_log("lockout_cleared", user_id=g.user_id, username=g.username, detail={"target": user_id})
    return jsonify({"unlocked": user_id})


@admin_bp.post("/users/<user_id>/reset-password")
@require_auth
@require_role("admin")
def reset_password(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    new_pw = body.get("new_password") or ""
    if not new_pw:
        return jsonify({"error": "new_password required"}), 400

    err = validate_password_strength(new_pw, user["username"])
    if err:
        return jsonify({"error": err}), 422

    new_hash = hash_password(new_pw)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_hash, user_id),
        )
    revoke_user_access(user_id)

    audit_log("password_reset", user_id=g.user_id, username=g.username, detail={"target": user_id})
    return jsonify({"message": "Password reset", "must_change_password": True})


# ── Audit log ─────────────────────────────────────────────────────────────────

@admin_bp.get("/audit")
@require_auth
@require_role("admin")
def get_audit():
    limit  = min(int(request.args.get("limit", 50)), 500)
    offset = int(request.args.get("offset", 0))
    event_type = request.args.get("event_type")
    username   = request.args.get("username")
    since      = request.args.get("since")   # ISO datetime e.g. "2026-01-01T00:00:00"
    until      = request.args.get("until")

    import re as _re
    _DT_PAT = _re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$")
    if since and not _DT_PAT.match(since):
        return jsonify({"error": "since must be ISO datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"}), 400
    if until and not _DT_PAT.match(until):
        return jsonify({"error": "until must be ISO datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"}), 400

    conditions, params = [], []
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if username:
        conditions.append("username = ?")
        params.append(username)
    if since:
        conditions.append("created_at >= ?")
        params.append(since)
    if until:
        conditions.append("created_at <= ?")
        params.append(until)

    # Safe: conditions list contains only hardcoded SQL fragments ("event_type = ?",
    # "username = ?"), never user-supplied strings. Values are always in params list.
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]

    filter_params = params[: len(params)]  # params before limit/offset appended
    count_params = [p for p in params if p not in [limit, offset]]

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM auth_events {where}", count_params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM auth_events {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params
        ).fetchall()

    return jsonify({
        "events": [dict(r) for r in rows],
        "count": len(rows),
        "total": total,
        "offset": offset,
        "limit": limit,
    })


# ── Sessions ──────────────────────────────────────────────────────────────────

@admin_bp.get("/sessions")
@require_auth
@require_role("admin")
def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.id, s.user_id, u.username, s.ip_address, s.user_agent,
                      s.expires_at, s.created_at, s.last_used_at, s.revoked
               FROM user_sessions s JOIN users u ON s.user_id = u.id
               WHERE s.revoked = 0 AND datetime(s.expires_at) > datetime('now')
               ORDER BY s.created_at DESC"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@admin_bp.delete("/sessions/<session_id>")
@require_auth
@require_role("admin")
def delete_session(session_id: str):
    revoke_session(session_id)
    audit_log("session_revoked", user_id=g.user_id, username=g.username, detail={"session": session_id})
    return jsonify({"revoked": session_id})


@admin_bp.delete("/sessions/bulk")
@require_auth
@require_role("admin")
def bulk_revoke_sessions():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422
    ph = ",".join("?" * len(ids))
    with get_db() as conn:
        conn.execute(f"UPDATE user_sessions SET revoked = 1 WHERE id IN ({ph})", ids)
    audit_log("session_revoked", user_id=g.user_id, username=g.username, detail={"sessions": ids, "count": len(ids)})
    return jsonify({"revoked": ids, "count": len(ids)})


# ── API Keys ──────────────────────────────────────────────────────────────────

@admin_bp.get("/api-keys")
@require_auth
@require_role("admin", "operator")
def list_api_keys():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, permissions, namespace, last_used, created_at, expires_at FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@admin_bp.post("/api-keys")
@require_auth
@require_role("admin", "operator")
def create_api_key():
    from core.api.auth import create_api_key as _create
    body = request.get_json(silent=True) or {}
    name        = (body.get("name") or "").strip()
    namespace   = body.get("namespace", "global")
    permissions = body.get("permissions", ["read", "write"])
    if permissions is None:
        permissions = ["read", "write"]

    if not name:
        return jsonify({"error": "name required"}), 400

    try:
        raw_key, key_id = _create(name, permissions, namespace)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    audit_log("api_key_created", user_id=g.user_id, username=g.username, namespace=namespace, detail={"name": name})
    return jsonify({"raw_key": raw_key, "id": key_id, "name": name, "namespace": namespace,
                    "permissions": permissions, "warning": "Copy this key — it will not be shown again"}), 201


@admin_bp.delete("/api-keys/bulk")
@require_auth
@require_role("admin")
def bulk_revoke_api_keys():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422
    placeholders = ",".join("?" * len(ids))
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id, name FROM api_keys WHERE id IN ({placeholders})", ids
        ).fetchall()
        revoked_keys = [{"id": r["id"], "name": r["name"]} for r in existing]
        if revoked_keys:
            del_ph = ",".join("?" * len(revoked_keys))
            conn.execute(f"DELETE FROM api_keys WHERE id IN ({del_ph})", [r["id"] for r in revoked_keys])
    for r in revoked_keys:
        audit_log("api_key_revoked", user_id=g.user_id, username=g.username, detail={"key_id": r["id"], "name": r["name"]})
    return jsonify({"revoked": [r["id"] for r in revoked_keys], "count": len(revoked_keys)})


@admin_bp.post("/api-keys/<key_id>/regenerate")
@require_auth
@require_role("admin", "operator")
def regenerate_api_key(key_id: str):
    """Generate a new secret for an existing API key — old key immediately invalidated."""
    import secrets as _secrets, hashlib as _hashlib
    with get_db() as conn:
        row = conn.execute("SELECT id, name, namespace FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            return jsonify({"error": "API key not found"}), 404
        raw_key  = _secrets.token_urlsafe(32)
        key_hash = _hashlib.sha256(raw_key.encode()).hexdigest()
        conn.execute(
            "UPDATE api_keys SET key_hash = ?, last_used = NULL WHERE id = ?",
            (key_hash, key_id),
        )
    audit_log("api_key_regenerated", user_id=g.user_id, username=g.username,
              detail={"key_id": key_id, "name": row["name"]})
    return jsonify({
        "raw_key": raw_key, "id": key_id,
        "name": row["name"], "namespace": row["namespace"],
        "warning": "Copy this key — it will not be shown again",
    })


@admin_bp.delete("/api-keys/<key_id>")
@require_auth
@require_role("admin")
def revoke_api_key(key_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT id, name FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            return jsonify({"error": "API key not found"}), 404
        conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    audit_log("api_key_revoked", user_id=g.user_id, username=g.username, detail={"key_id": key_id, "name": row["name"]})
    return jsonify({"revoked": key_id})


# ── Security settings ─────────────────────────────────────────────────────────

@admin_bp.get("/security-settings")
@require_auth
@require_role("admin")
def get_security_settings():
    keys = ["max_failed_attempts", "lockout_minutes", "access_token_minutes", "refresh_token_days", "allow_self_register"]
    with get_db() as conn:
        rows = conn.execute(f"SELECT key, value FROM system_config WHERE key IN ({','.join('?'*len(keys))})", keys).fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})


@admin_bp.patch("/security-settings")
@require_auth
@require_role("admin")
def update_security_settings():
    body = request.get_json(silent=True) or {}
    allowed_keys = {"max_failed_attempts", "lockout_minutes", "access_token_minutes", "refresh_token_days", "allow_self_register"}
    updates = {k: str(v) for k, v in body.items() if k in allowed_keys}
    if not updates:
        return jsonify({"error": "No valid settings provided"}), 400
    bounds = {"max_failed_attempts": (1, 100), "lockout_minutes": (1, 1440),
              "access_token_minutes": (1, 1440), "refresh_token_days": (1, 90)}
    for k, v in updates.items():
        if k == "allow_self_register":
            if v not in ("0", "1"):
                return jsonify({"error": "allow_self_register must be 0 or 1"}), 422
        else:
            lo, hi = bounds[k]
            if not v.isdigit() or not lo <= int(v) <= hi:
                return jsonify({"error": f"{k} must be an integer between {lo} and {hi}"}), 422

    with get_db() as conn:
        conn.executemany("INSERT OR REPLACE INTO system_config(key, value) VALUES (?, ?)", updates.items())

    # Invalidate TTL cache so new settings take effect immediately
    for k in updates:
        _cfg_cache.pop(k, None)

    audit_log("security_settings_updated", user_id=g.user_id, username=g.username, detail={"keys": list(updates.keys())})
    return jsonify({"updated": list(updates.keys())})


@admin_bp.post("/backup")
@require_auth
@require_role("admin")
def trigger_backup():
    """Run an on-demand SQLite backup. Admin only."""
    from core.backup import create_backup
    result = create_backup()
    status = 200 if result["ok"] else 500
    return jsonify(result), status


@admin_bp.get("/backup")
@require_auth
@require_role("admin")
def list_backups():
    """List existing DB backups. Admin only."""
    from core.backup import list_backups as _list
    return jsonify({"backups": _list()})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_dict(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "username": d["username"],
        "email": d.get("email"),
        "role": d["role"],
        "namespace": d.get("namespace"),
        "is_active": bool(d["is_active"]),
        "must_change_password": bool(d.get("must_change_password", 0)),
        "failed_attempts": d.get("failed_attempts", 0),
        "locked_until": d.get("locked_until"),
        "last_login_at": d.get("last_login_at"),
        "created_at": d.get("created_at"),
    }


def _user_dict_full(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user["role"],
        "namespace": user.get("namespace"),
        "is_active": bool(user["is_active"]),
        "must_change_password": bool(user.get("must_change_password", 0)),
        "failed_attempts": user.get("failed_attempts", 0),
        "locked_until": user.get("locked_until"),
        "last_login_at": user.get("last_login_at"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }
