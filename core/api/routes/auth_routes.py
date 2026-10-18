"""Auth routes — /api/v1/auth/*"""
from __future__ import annotations

import datetime
import hashlib
import secrets
import time

from flask import Blueprint, jsonify, request

from core.api.limiter import limiter
from core.auth import (
    audit_log, check_lockout, clear_failed_attempts, constant_time_dummy_check,
    create_access_token, create_refresh_token, create_user, effective_namespace,
    get_user_by_id, get_user_by_username, hash_password, record_failed_attempt,
    require_auth, require_role, revoke_sessions_by_token_hash, revoke_user_access, store_refresh_token,
    validate_password_strength, validate_refresh_token, verify_password,
)
from core.database import get_db
from core.utils import new_id, utcnow

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def _ip() -> str:
    return request.remote_addr or ""


def _ua() -> str:
    return request.headers.get("User-Agent", "")


# ── POST /auth/login ──────────────────────────────────────────────────────────

@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user = get_user_by_username(username)
    if not user:
        # Constant-time response — run dummy bcrypt to match real-user timing
        constant_time_dummy_check(password)
        audit_log("login_failure", username=username, ip=_ip(), ua=_ua(), detail={"reason": "not_found"})
        return jsonify({"error": "Invalid username or password"}), 401

    # Status is revealed only to someone who knows the password, so the 403/423
    # responses cannot be used to enumerate usernames. Locked accounts still
    # refuse a correct password.
    remaining = check_lockout(user)
    password_ok = verify_password(password, user["password_hash"])
    if not password_ok or not user["is_active"] or remaining is not None:
        if not password_ok and user["is_active"] and remaining is None:
            record_failed_attempt(user["id"])
        if password_ok and not user["is_active"]:
            return jsonify({"error": "Account disabled"}), 403
        if password_ok and remaining is not None:
            return jsonify({"error": "Account locked", "retry_after_seconds": remaining}), 423
        return jsonify({"error": "Invalid username or password"}), 401

    clear_failed_attempts(user["id"])
    audit_log("login_success", user_id=user["id"], username=username, ip=_ip(), ua=_ua(), namespace=user.get("namespace"))

    access_token = create_access_token(user["id"], user["username"], user["role"], user.get("namespace"))
    raw_refresh, refresh_hash = create_refresh_token()
    store_refresh_token(user["id"], refresh_hash, ip=_ip(), ua=_ua())

    return jsonify({
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "expires_in": 3600,
        "must_change_password": bool(user.get("must_change_password")),
        "user": _user_public(user),
    })


# ── POST /auth/register ───────────────────────────────────────────────────────

@auth_bp.post("/register")
@limiter.limit("5 per minute")
def register():
    # Check if self-registration is enabled
    with get_db() as conn:
        cfg = conn.execute("SELECT value FROM system_config WHERE key = 'allow_self_register'").fetchone()
    if not cfg or cfg["value"] != "1":
        return jsonify({"error": "Self-registration is disabled"}), 403

    body = request.get_json(silent=True) or {}
    username  = (body.get("username") or "").strip()
    password  = body.get("password") or ""
    email     = (body.get("email") or "").strip() or None
    namespace = (body.get("namespace") or "").strip() or None

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    # Password strength
    err = validate_password_strength(password, username)
    if err:
        return jsonify({"error": err}), 422

    # Namespace must be a client-type namespace
    if not namespace:
        return jsonify({"error": "namespace required for self-registration"}), 422

    with get_db() as conn:
        ns_row = conn.execute(
            "SELECT slug, type FROM namespaces WHERE slug = ? AND enabled = 1", (namespace,)
        ).fetchone()
    if not ns_row or ns_row["type"] not in ("client",):
        # Same error for both cases — prevents namespace slug enumeration
        return jsonify({"error": "Registration not available for this namespace"}), 422

    # One client account per namespace
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE namespace = ? AND role = 'client'", (namespace,)
        ).fetchone()
    if existing:
        return jsonify({"error": "Registration not available for this namespace"}), 409

    # Username uniqueness
    if get_user_by_username(username):
        return jsonify({"error": "Username already taken"}), 409

    user = create_user(username, password, role="client", namespace=namespace, email=email)
    audit_log("register", user_id=user["id"], username=username, ip=_ip(), ua=_ua(), namespace=namespace)
    return jsonify({"message": "Account created. Please sign in.", "user": _user_public(user)}), 201


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@auth_bp.post("/refresh")
@limiter.limit("20 per minute")
def refresh():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("refresh_token") or ""
    if not raw_token:
        return jsonify({"error": "refresh_token required"}), 400

    session = validate_refresh_token(raw_token)
    if not session:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    user = get_user_by_id(session["user_id"])
    if not user or not user["is_active"]:
        return jsonify({"error": "User not found or disabled"}), 401

    access_token = create_access_token(user["id"], user["username"], user["role"], user.get("namespace"))
    audit_log("token_refresh", user_id=user["id"], username=user["username"], ip=_ip(), ua=_ua())

    return jsonify({"access_token": access_token, "expires_in": 3600})


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@auth_bp.post("/logout")
@require_auth
def logout():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("refresh_token") or ""
    if raw_token:
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        revoke_sessions_by_token_hash(token_hash)
    from flask import g as _g
    audit_log("logout", user_id=getattr(_g, "user_id", None), username=getattr(_g, "username", None), ip=_ip(), ua=_ua())
    return jsonify({"message": "Logged out"})


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@auth_bp.get("/me")
@require_auth
def me():
    from flask import g as _g
    user = get_user_by_id(_g.user_id.replace("apikey:", "") if _g.user_id.startswith("apikey:") else _g.user_id)
    if not user:
        # API key auth — return synthetic user object
        return jsonify({
            "id": _g.user_id,
            "username": _g.username,
            "role": _g.user_role,
            "namespace": _g.user_namespace,
            "auth_method": _g.auth_method,
        })
    return jsonify(_user_public(user))


# ── POST /auth/change-password ────────────────────────────────────────────────

@auth_bp.post("/change-password")
@limiter.limit("5 per minute")
@require_auth
def change_password():
    from flask import g as _g
    body = request.get_json(silent=True) or {}
    current_pw = body.get("current_password") or ""
    new_pw     = body.get("new_password") or ""

    if not current_pw or not new_pw:
        return jsonify({"error": "current_password and new_password required"}), 400

    if _g.user_id.startswith("apikey:"):
        return jsonify({"error": "Not applicable for API key auth"}), 400

    user = get_user_by_id(_g.user_id)
    if not user or not verify_password(current_pw, user["password_hash"]):
        return jsonify({"error": "Current password incorrect"}), 401

    if user["must_change_password"] and new_pw == current_pw:
        return jsonify({"error": "New password must be different from current password"}), 422

    err = validate_password_strength(new_pw, user["username"])
    if err:
        return jsonify({"error": err}), 422

    new_hash = hash_password(new_pw)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_hash, user["id"]),
        )
    # Kill every other session/token, then hand this caller a fresh pair
    revoke_user_access(user["id"])
    access_token = create_access_token(user["id"], user["username"], user["role"], user.get("namespace"))
    raw_refresh, refresh_hash = create_refresh_token()
    store_refresh_token(user["id"], refresh_hash, ip=_ip(), ua=_ua())

    audit_log("password_change", user_id=user["id"], username=user["username"], ip=_ip(), ua=_ua())
    return jsonify({"message": "Password updated", "access_token": access_token,
                    "refresh_token": raw_refresh, "expires_in": 3600})


# ── POST /auth/forgot-password ────────────────────────────────────────────────

@auth_bp.post("/forgot-password")
@limiter.limit("20/hour")
@require_auth
@require_role("admin")
def forgot_password():
    """Generate a password-reset token. Admin-only — token is returned to the admin
    who relays it to the user out-of-band. When SMTP is configured, send via email instead.
    """
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    user = get_user_by_username(username)
    if not user or not user["is_active"]:
        return jsonify({"error": "User not found or inactive"}), 404

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = (utcnow() + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_sessions(id, user_id, token_hash, user_agent, ip_address, expires_at, token_purpose) "
            "VALUES (?,?,?,?,?,?,'password_reset')",
            (new_id(), user["id"], token_hash, _ua(), _ip(), expires),
        )

    audit_log("password_reset_request", user_id=user["id"], username=username, ip=_ip(), ua=_ua())
    return jsonify({
        "message": "Reset token issued. Share with the user securely.",
        "reset_token": raw_token,
        "expires_in_hours": 1,
        "username": username,
    })


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@auth_bp.post("/reset-password")
@limiter.limit("10/hour")
def reset_password():
    """Consume a reset token and set a new password."""
    import hashlib
    body = request.get_json(silent=True) or {}
    raw_token   = body.get("reset_token") or ""
    new_password = body.get("new_password") or ""

    if not raw_token or not new_password:
        return jsonify({"error": "reset_token and new_password required"}), 400

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_db() as conn:
        session = conn.execute(
            "SELECT * FROM user_sessions WHERE token_hash=? AND token_purpose='password_reset' "
            "AND revoked=0 AND expires_at > datetime('now')",
            (token_hash,),
        ).fetchone()

    if not session:
        return jsonify({"error": "Invalid or expired reset token"}), 401

    user = get_user_by_id(session["user_id"])
    if not user or not user["is_active"]:
        return jsonify({"error": "User not found or disabled"}), 401

    err = validate_password_strength(new_password, user["username"])
    if err:
        return jsonify({"error": err}), 422

    new_hash = hash_password(new_password)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=0, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_hash, user["id"]),
        )
        conn.execute("UPDATE user_sessions SET revoked=1 WHERE token_hash=?", (token_hash,))
    revoke_user_access(user["id"])

    audit_log("password_reset", user_id=user["id"], username=user["username"], ip=_ip(), ua=_ua())
    return jsonify({"message": "Password reset successful. You can now sign in."})


# ── Dashboard session store (page-refresh persistence) ────────────────────────

def _session_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@auth_bp.post("/session")
@require_auth
def create_dashboard_session():
    """Create a page-refresh session handle. Only a hash of the handle is stored, and no tokens.

    The caller must prove ownership by presenting its own live refresh token.
    """
    from flask import g as _g
    body = request.get_json(silent=True) or {}
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        return jsonify({"error": "refresh_token required"}), 400
    if _g.user_id.startswith("apikey:"):
        return jsonify({"error": "API-key sessions cannot be persisted"}), 400

    session = validate_refresh_token(refresh_token)
    if not session or session["user_id"] != _g.user_id:
        return jsonify({"error": "Invalid refresh token"}), 401

    key = secrets.token_urlsafe(32)
    expires_at = (utcnow() + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        # Purge expired sessions (housekeeping)
        conn.execute("DELETE FROM dashboard_sessions WHERE expires_at < datetime('now')")
        inserted = conn.execute(
            "INSERT INTO dashboard_sessions "
            "(session_key, user_id, username, user_role, user_namespace, must_change_password, access_token, refresh_token, expires_at, auth_session_id) "
            "SELECT ?, ?, ?, ?, ?, 0, '', '', ?, id FROM user_sessions "
            "WHERE id = ? AND user_id = ? AND revoked = 0 AND token_purpose = 'refresh' "
            "AND julianday(expires_at) > julianday('now')",
            (_session_key_hash(key), _g.user_id, _g.username, _g.user_role, _g.user_namespace,
             expires_at, session["id"], _g.user_id),
        )
        # Revocation may have happened after validate_refresh_token returned.
        if not inserted.rowcount:
            return jsonify({"error": "Invalid refresh token"}), 401
    return jsonify({"session_key": key})


@auth_bp.get("/session/<key>")
@limiter.limit("20 per minute")
def restore_dashboard_session(key):
    """Rotate credentials within the handle's live authentication session."""
    with get_db() as conn:
        # Serialize restoration with revocation and other restorations. Do not
        # open nested get_db contexts here: they would commit this transaction.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT d.session_key, d.auth_session_id, u.* FROM dashboard_sessions d "
            "JOIN user_sessions s ON s.id = d.auth_session_id AND s.user_id = d.user_id "
            "JOIN users u ON u.id = s.user_id "
            "WHERE d.session_key = ? AND julianday(d.expires_at) > julianday('now') "
            "AND s.revoked = 0 AND s.token_purpose = 'refresh' "
            "AND julianday(s.expires_at) > julianday('now')",
            (_session_key_hash(key),),
        ).fetchone()
        user = dict(row) if row else None
        if not user or not user["is_active"] or check_lockout(user) is not None:
            conn.execute("DELETE FROM dashboard_sessions WHERE session_key = ?", (_session_key_hash(key),))
            return jsonify({"error": "session not found or expired"}), 404

        raw_refresh, refresh_hash = create_refresh_token()
        # Keep the original id and expiry so restored credentials cannot escape
        # administrative revocation or extend the authentication session.
        conn.execute(
            "UPDATE user_sessions SET token_hash = ?, last_used_at = CURRENT_TIMESTAMP "
            "WHERE id = ?", (refresh_hash, row["auth_session_id"]),
        )

    access_token = create_access_token(user["id"], user["username"], user["role"], user.get("namespace"))
    return jsonify({
        "access_token":         access_token,
        "refresh_token":        raw_refresh,
        "username":             user["username"],
        "user_role":            user["role"],
        "user_namespace":       user.get("namespace"),
        "must_change_password": bool(user.get("must_change_password")),
    })


@auth_bp.delete("/session/<key>")
@limiter.limit("20 per minute")
def delete_dashboard_session(key):
    """Delete session on logout."""
    with get_db() as conn:
        conn.execute("DELETE FROM dashboard_sessions WHERE session_key = ?", (_session_key_hash(key),))
    return jsonify({"message": "session deleted"})


# ── Helper ────────────────────────────────────────────────────────────────────

def _user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user["role"],
        "namespace": user.get("namespace"),
        "is_active": bool(user["is_active"]),
        "must_change_password": bool(user.get("must_change_password")),
        "onboarding_done": bool(user.get("onboarding_done", 0)),
        "last_login_at": user.get("last_login_at"),
        "created_at": user.get("created_at"),
    }


# ── POST /auth/onboarding-done ────────────────────────────────────────────────

@auth_bp.post("/onboarding-done")
@require_auth
def mark_onboarding_done():
    from flask import g as _g
    if _g.user_id.startswith("apikey:"):
        return jsonify({"ok": True})  # API key users — no-op
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET onboarding_done = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (_g.user_id,),
        )
    return jsonify({"ok": True})
