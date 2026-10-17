"""API key authentication middleware."""
import hashlib
from functools import wraps
from flask import request, jsonify, g

from core.database import get_db


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        raw_key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if not raw_key:
            return jsonify({"error": "Missing API key"}), 401

        key_hash = _hash_key(raw_key)
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, permissions, namespace FROM api_keys WHERE key_hash = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
                (key_hash,),
            ).fetchone()

        if not row:
            return jsonify({"error": "Invalid or expired API key"}), 401

        # Update last_used
        with get_db() as conn:
            conn.execute("UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))

        g.api_key_id = row["id"]
        g.api_key_name = row["name"]
        g.api_key_namespace = row["namespace"]
        g.api_key_permissions = row["permissions"]
        return f(*args, **kwargs)

    return decorated


def create_api_key(name: str, permissions: list[str] = None, namespace: str = "global") -> tuple[str, str]:
    """Create a new API key. Returns (raw_key, key_id)."""
    import secrets
    import json
    from core.utils import new_id

    raw_key = f"cos-{secrets.token_urlsafe(32)}"
    key_id = new_id()
    key_hash = _hash_key(raw_key)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO api_keys(id, name, key_hash, permissions, namespace) VALUES (?, ?, ?, ?, ?)",
            (key_id, name, key_hash, json.dumps(permissions or ["read", "write"]), namespace),
        )

    return raw_key, key_id
