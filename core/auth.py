"""Central authentication module — passwords, JWT, sessions, decorators."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from flask import abort, g, jsonify, request

from core.database import get_db
from core.utils import new_id, utcnow

logger = logging.getLogger("claudeos.auth")

# ── Config helpers ─────────────────────────────────────────────────────────────

_cfg_cache: dict[str, tuple[str, float]] = {}
_CFG_TTL = 60.0  # seconds
_CFG_CACHE_MAX = 100


def _cfg(key: str, default: str) -> str:
    now = time.monotonic()
    if key in _cfg_cache and now < _cfg_cache[key][1]:
        return _cfg_cache[key][0]
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
        val = row["value"] if row else default
    except Exception as e:
        logger.warning("Config read failed for key %s: %s", key, e)
        val = default
    _cfg_cache[key] = (val, now + _CFG_TTL)
    if len(_cfg_cache) > _CFG_CACHE_MAX:
        evict = sorted(_cfg_cache.keys(), key=lambda k: _cfg_cache[k][1])[:_CFG_CACHE_MAX // 10]
        for k in evict:
            _cfg_cache.pop(k, None)
    return val


def _cfg_int(key: str, default: int) -> int:
    try:
        return int(_cfg(key, str(default)))
    except (ValueError, TypeError):
        return default


# ── Password ───────────────────────────────────────────────────────────────────

# Dummy hash for timing-safe login — computed lazily on first use to avoid
# expensive bcrypt at module import time (which causes issues in test collection).
_DUMMY_HASH: str = ""
_DUMMY_HASH_LOCK = threading.Lock()


def _get_dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH:
        return _DUMMY_HASH
    with _DUMMY_HASH_LOCK:
        if not _DUMMY_HASH:
            _DUMMY_HASH = bcrypt.hashpw(b"claudeos_timing_guard_xK9!", bcrypt.gensalt(rounds=12)).decode()
    return _DUMMY_HASH


def constant_time_dummy_check(plain: str) -> None:
    """Run a bcrypt check against a dummy hash. Matches the latency of a real password check."""
    bcrypt.checkpw(plain.encode("utf-8"), _get_dummy_hash().encode("utf-8"))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str, username: str = "") -> Optional[str]:
    """Returns an error message, or None if password is strong enough."""
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit"
    if username and username.lower() in password.lower():
        return "Password must not contain your username"
    return None


# ── JWT ────────────────────────────────────────────────────────────────────────

def _secret() -> str:
    from core.config import get_settings
    return get_settings().CLAUDEOS_SECRET_KEY


def create_access_token(user_id: str, username: str, role: str, namespace: Optional[str]) -> str:
    ttl_minutes = _cfg_int("access_token_minutes", 60)
    now = utcnow()
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "namespace": namespace,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure."""
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def decode_access_token_unverified(token: str) -> dict:
    """Decode without verifying expiry — used for refresh decision only."""
    return jwt.decode(token, _secret(), algorithms=["HS256"], options={"verify_exp": False})


# ── Refresh tokens (opaque) ────────────────────────────────────────────────────

def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store the hash, send the raw token."""
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, hashed


def store_refresh_token(user_id: str, token_hash: str, ip: str = "", ua: str = "") -> str:
    """Stores session row. Returns session id."""
    ttl_days = _cfg_int("refresh_token_days", 7)
    session_id = new_id()
    expires_at = (utcnow() + timedelta(days=ttl_days)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_sessions(id, user_id, token_hash, ip_address, user_agent, expires_at, token_purpose) "
            "VALUES (?,?,?,?,?,?,'refresh')",
            (session_id, user_id, token_hash, ip, ua, expires_at),
        )
    return session_id


def validate_refresh_token(raw_token: str) -> Optional[dict]:
    """Returns the session row if valid, None otherwise."""
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with get_db() as conn:
        # Normalize stored ISO timestamps and SQLite's clock before comparing.
        row = conn.execute(
            "SELECT * FROM user_sessions WHERE token_hash = ? AND revoked = 0 "
            "AND julianday(expires_at) > julianday('now') AND token_purpose = 'refresh'",
            (token_hash,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE user_sessions SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],)
            )
    return dict(row) if row else None


def revoke_session(session_id: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE user_sessions SET revoked = 1 WHERE id = ?", (session_id,))


def revoke_sessions_by_token_hash(token_hash: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE user_sessions SET revoked = 1 WHERE token_hash = ?", (token_hash,))


# ── Lockout ────────────────────────────────────────────────────────────────────

def check_lockout(user: dict) -> Optional[int]:
    """Returns seconds remaining in lockout, or None if not locked."""
    if not user.get("locked_until"):
        return None
    locked_until = datetime.fromisoformat(user["locked_until"])
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    remaining = (locked_until - utcnow()).total_seconds()
    return int(remaining) if remaining > 0 else None


def record_failed_attempt(user_id: str) -> None:
    max_attempts = _cfg_int("max_failed_attempts", 5)
    lockout_minutes = _cfg_int("lockout_minutes", 15)
    locked_username = None
    with get_db() as conn:
        conn.execute(
            """UPDATE users SET
                failed_attempts = failed_attempts + 1,
                locked_until = CASE
                    WHEN failed_attempts + 1 >= ? THEN datetime('now', '+' || ? || ' minutes')
                    ELSE locked_until
                END,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
            (max_attempts, lockout_minutes, user_id),
        )
        row = conn.execute(
            "SELECT username, failed_attempts FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row and row["failed_attempts"] >= max_attempts:
            locked_username = row["username"]
    audit_log("login_failure", user_id=user_id, ip=_client_ip(), ua=_client_ua())
    if locked_username:
        audit_log("lockout_triggered", user_id=user_id, username=locked_username,
                  ip=_client_ip(), ua=_client_ua())
        threading.Thread(target=_notify_lockout, args=(locked_username,), daemon=True).start()


def _notify_lockout(username: str) -> None:
    """Fire-and-forget: email all active admins when an account is locked."""
    try:
        from core.notifications import send_email, _is_configured
        if not _is_configured():
            return
        with get_db() as conn:
            rows = conn.execute(
                "SELECT email FROM users WHERE role='admin' AND is_active=1 AND email IS NOT NULL"
            ).fetchall()
        admin_emails = [r["email"] for r in rows if r["email"]]
        if not admin_emails:
            return
        body = (
            f"<p><b>Security Alert:</b> Account <code>{__import__('html').escape(username)}</code> has been "
            f"locked after too many failed login attempts.</p>"
            f"<p>Check the Admin Panel → Audit Log for details.</p>"
        )
        for email in admin_emails:
            send_email(to=email, subject=f"[ClaudeOS] Account locked: {' '.join(username.split())}", body_html=body)
    except Exception as e:
        logger.warning("Lockout notification failed: %s", e)


def clear_failed_attempts(user_id: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )


# ── Audit log ──────────────────────────────────────────────────────────────────

def audit_log(
    event_type: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    ip: str = "",
    ua: str = "",
    namespace: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO auth_events(id, event_type, user_id, username, ip_address, user_agent, namespace, detail) VALUES (?,?,?,?,?,?,?,?)",
                (new_id(), event_type, user_id, username, ip, ua, namespace, json.dumps(detail or {})),
            )
    except Exception as e:
        logger.warning("audit_log failed: %s", e)


# ── User CRUD helpers ──────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    # Keep password_hash accessible internally (needed by verify_password callers)
    # but mark it so accidental serialisation is detectable. Callers that need to
    # check the hash access user["password_hash"] explicitly; API responses must
    # use _user_public() or _user_dict_full() which never include the hash.
    return user


def get_user_by_id(user_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def create_user(username: str, password: str, role: str = "viewer",
                namespace: Optional[str] = None, email: Optional[str] = None,
                must_change_password: bool = False) -> dict:
    user_id = new_id()
    pw_hash = hash_password(password)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users(id, username, email, password_hash, role, namespace, must_change_password) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, username, email, pw_hash, role, namespace, int(must_change_password)),
        )
    user = get_user_by_id(user_id)
    audit_log("user_created", user_id=user_id, username=username, namespace=namespace)
    return user


# ── Flask request helpers ──────────────────────────────────────────────────────

def _client_ip() -> str:
    try:
        return request.remote_addr or ""
    except RuntimeError:
        return ""


def _client_ua() -> str:
    try:
        return request.headers.get("User-Agent", "")
    except RuntimeError:
        return ""


# ── API key fallback (re-uses existing api_keys table) ────────────────────────

# Debounce last_used writes: only hit DB once per 60s per key id
# Bounded to 500 entries — evict entries older than 2× interval to prevent unbounded growth
_api_key_last_updated: dict[str, float] = {}
_api_key_lock = threading.Lock()  # IN-04: protect dict from concurrent mutation
_API_KEY_UPDATE_INTERVAL = 60.0
_API_KEY_CACHE_MAX = 500


def _validate_api_key_header(raw_key: str) -> bool:
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, permissions, namespace FROM api_keys WHERE key_hash = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            (key_hash,),
        ).fetchone()
        if not row:
            return False
        now = time.monotonic()
        with _api_key_lock:
            if now - _api_key_last_updated.get(row["id"], 0) >= _API_KEY_UPDATE_INTERVAL:
                conn.execute("UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
                _api_key_last_updated[row["id"]] = now
                # Evict stale entries when cache exceeds bound
                if len(_api_key_last_updated) > _API_KEY_CACHE_MAX:
                    cutoff = now - _API_KEY_UPDATE_INTERVAL * 2
                    stale = [k for k, v in _api_key_last_updated.items() if v < cutoff]
                    for k in stale:
                        del _api_key_last_updated[k]
    # HI-05: propagate stored namespace and derive role from it
    stored_ns = row["namespace"] if row["namespace"] not in (None, "", "global") else None
    g.user_id = f"apikey:{row['id']}"
    g.username = row["name"]
    g.user_role = "client" if stored_ns else "operator"
    g.user_namespace = stored_ns
    g.auth_method = "api_key"
    try:
        perms = json.loads(row["permissions"] or "[]")
    except (TypeError, ValueError):
        perms = []
    g.api_read_only = "write" not in perms
    return True


# ── Decorators ────────────────────────────────────────────────────────────────

_jwt_cache: dict[str, tuple[dict, float]] = {}
_jwt_cache_lock = threading.Lock()
_JWT_CACHE_MAX = 500
_JWT_CACHE_TTL = 60.0


def _cached_decode_access_token(token: str) -> dict:
    """Decode and verify JWT, caching for at most 60s and never beyond exp."""
    tok_hash = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    with _jwt_cache_lock:
        entry = _jwt_cache.get(tok_hash)
        if entry:
            if "exp" in entry[0] and int(entry[0]["exp"]) <= time.time():
                _jwt_cache.pop(tok_hash, None)
                raise jwt.ExpiredSignatureError("Signature has expired")
            if now < entry[1]:
                return entry[0]
            _jwt_cache.pop(tok_hash, None)
    payload = decode_access_token(token)  # raises on invalid/expired
    ttl = _JWT_CACHE_TTL
    if "exp" in payload:
        ttl = min(ttl, int(payload["exp"]) - time.time())
        if ttl <= 0:
            raise jwt.ExpiredSignatureError("Signature has expired")
    with _jwt_cache_lock:
        _jwt_cache[tok_hash] = (payload, now + ttl)
        if len(_jwt_cache) > _JWT_CACHE_MAX:
            evict = sorted(_jwt_cache.keys(), key=lambda k: _jwt_cache[k][1])[:_JWT_CACHE_MAX // 10]
            for k in evict:
                _jwt_cache.pop(k, None)
    return payload


_user_state_cache: dict[str, tuple[Optional[dict], float]] = {}
_USER_STATE_TTL = 5.0


def _user_state(user_id: str) -> Optional[dict]:
    """Authoritative role/namespace/active/revocation state for a JWT subject (5s cache)."""
    now = time.monotonic()
    with _jwt_cache_lock:
        entry = _user_state_cache.get(user_id)
        if entry and now < entry[1]:
            return entry[0]
    with get_db() as conn:
        row = conn.execute(
            "SELECT role, namespace, is_active, tokens_valid_after FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    state = dict(row) if row else None
    with _jwt_cache_lock:
        _user_state_cache[user_id] = (state, now + _USER_STATE_TTL)
        if len(_user_state_cache) > _JWT_CACHE_MAX:
            _user_state_cache.clear()
    return state


def revoke_user_access(user_id: str) -> None:
    """Invalidate every access token, refresh session and dashboard handle for a user."""
    with get_db() as conn:
        conn.execute("UPDATE users SET tokens_valid_after = ? WHERE id = ?", (int(utcnow().timestamp()), user_id))
        conn.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM dashboard_sessions WHERE user_id = ?", (user_id,))
    with _jwt_cache_lock:
        _user_state_cache.pop(user_id, None)


def invalidate_user_state(user_id: str) -> None:
    with _jwt_cache_lock:
        _user_state_cache.pop(user_id, None)


def require_auth(f):
    """Accept JWT Bearer OR legacy X-API-Key. Sets g.user_* context."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. JWT Bearer
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = _cached_decode_access_token(token)
                state = _user_state(payload["sub"])
                if (not state or not state["is_active"]
                        or payload.get("iat", 0) < state["tokens_valid_after"]):
                    return jsonify({"error": "Invalid token"}), 401
                g.user_id        = payload["sub"]
                g.username       = payload["username"]
                # Role/namespace come from the DB, not the (possibly stale) token claims
                g.user_role      = state["role"]
                g.user_namespace = state["namespace"]
                g.auth_method    = "jwt"
                # Fail closed: a client/viewer without a namespace would otherwise be
                # treated as "unscoped" by effective_namespace() consumers.
                if g.user_role in ("client", "viewer") and not g.user_namespace:
                    return jsonify({"error": "Account has no namespace assigned"}), 403
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

        # 2. X-API-Key header fallback (query param removed — keys must not appear in URLs)
        raw_key = request.headers.get("X-API-Key")
        if raw_key and _validate_api_key_header(raw_key):
            if g.api_read_only and request.method not in ("GET", "HEAD", "OPTIONS"):
                return jsonify({"error": "API key is read-only"}), 403
            return f(*args, **kwargs)

        return jsonify({"error": "Authentication required"}), 401
    return decorated


def require_role(*allowed_roles: str):
    """403 if g.user_role is not in allowed_roles. Must be used after @require_auth."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if getattr(g, "user_role", None) not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_write(f):
    """403 for read-only roles (viewer). Must be used after @require_auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(g, "user_role", None) == "viewer":
            return jsonify({"error": "Read-only account"}), 403
        return f(*args, **kwargs)
    return decorated


def is_scoped() -> bool:
    """True when the caller is restricted to a single namespace (client/viewer)."""
    return getattr(g, "user_role", "admin") in ("client", "viewer")


def can_access_namespace(namespace: Optional[str]) -> bool:
    """True if the caller may touch data belonging to `namespace`."""
    role = getattr(g, "user_role", None)
    if role in ("admin", "operator"):
        return True
    return role in ("client", "viewer") and bool(namespace) and namespace == getattr(g, "user_namespace", None)


def effective_namespace(requested: Optional[str] = None) -> Optional[str]:
    """Return the namespace to query based on caller's role.
    Clients/viewers are always restricted to their own namespace — never trust caller value.
    Unsupported roles and client/viewer accounts without a namespace are denied.
    """
    role = getattr(g, "user_role", None)
    if role in ("admin", "operator"):
        return requested
    if role in ("client", "viewer"):
        namespace = getattr(g, "user_namespace", None)
        if namespace:
            return namespace
    abort(403)
