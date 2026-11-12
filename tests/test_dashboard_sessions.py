"""Dashboard handles must stay within the originating refresh session."""
import hashlib

import pytest


@pytest.fixture
def dashboard_session(client):
    from core.auth import create_user, validate_refresh_token

    create_user("dashboard_user", "Dashboard123!", role="operator")
    tokens = client.post("/api/v1/auth/login", json={
        "username": "dashboard_user", "password": "Dashboard123!",
    }).json
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    issued = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": tokens["refresh_token"]})
    assert issued.status_code == 200
    return tokens, headers, issued.json["session_key"], validate_refresh_token(tokens["refresh_token"])


def test_restoration_rotates_within_original_session(client, dashboard_session):
    from core.auth import validate_refresh_token
    from core.database import get_db
    from scripts.migrate import run_all
    from core.api.app import _run_migrations

    tokens, _, key, original = dashboard_session
    # Both migration entry points must preserve new, bound handles on replay.
    run_all()
    _run_migrations()
    previous = tokens["refresh_token"]
    for _ in range(2):
        restored = client.get(f"/api/v1/auth/session/{key}")
        assert restored.status_code == 200
        current = restored.json["refresh_token"]
        assert current != previous
        assert validate_refresh_token(previous) is None
        session = validate_refresh_token(current)
        assert session["id"] == original["id"]
        assert session["expires_at"] == original["expires_at"]
        assert session["token_purpose"] == "refresh"
        assert client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {restored.json['access_token']}"}).status_code == 200
        previous = current
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0] == 1
        handle = conn.execute("SELECT * FROM dashboard_sessions").fetchone()
    assert handle["auth_session_id"] == original["id"]
    assert handle["session_key"] != key
    assert not handle["access_token"] and not handle["refresh_token"]


@pytest.mark.parametrize("control", ["single", "bulk", "logout"])
def test_revocation_invalidates_all_bound_handles_and_restored_refresh(
        client, dashboard_session, admin_token, control):
    from core.database import get_db

    tokens, headers, key, original = dashboard_session
    second = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": tokens["refresh_token"]}).json["session_key"]
    # Another login for the same user must survive revocation of this session.
    other = client.post("/api/v1/auth/login", json={
        "username": "dashboard_user", "password": "Dashboard123!",
    }).json
    other_key = client.post("/api/v1/auth/session", headers=headers,
                           json={"refresh_token": other["refresh_token"]}).json["session_key"]
    restored = client.get(f"/api/v1/auth/session/{key}")
    assert restored.status_code == 200
    raw_refresh = restored.json["refresh_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    if control == "single":
        result = client.delete(f"/api/v1/admin/sessions/{original['id']}", headers=admin_headers)
    elif control == "bulk":
        result = client.delete("/api/v1/admin/sessions/bulk", headers=admin_headers,
                               json={"ids": [original["id"]]})
    else:
        result = client.post("/api/v1/auth/logout", headers=headers,
                             json={"refresh_token": raw_refresh})
    assert result.status_code == 200
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions WHERE auth_session_id=?",
                            (original["id"],)).fetchone()[0] == 0
    for handle in (key, second):
        assert client.get(f"/api/v1/auth/session/{handle}").status_code == 404
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]}).status_code == 200
    assert client.get(f"/api/v1/auth/session/{other_key}").status_code == 200


@pytest.mark.parametrize("state", ["expired", "reset", "deleted", "unbound", "wrong_user", "disabled", "locked"])
def test_restoration_requires_live_matching_refresh_session_and_user(client, dashboard_session, state):
    from core.auth import create_user
    from core.database import get_db
    from core.utils import utcnow

    _, _, key, original = dashboard_session
    if state == "wrong_user":
        other = create_user("other_user", "OtherPass123!", role="operator")
    with get_db() as conn:
        if state == "expired":
            # ISO timestamps with 'T' must be compared chronologically, even today.
            conn.execute("UPDATE user_sessions SET expires_at=? WHERE id=?",
                         (utcnow().isoformat(), original["id"]))
        elif state == "reset":
            conn.execute("UPDATE user_sessions SET token_purpose='password_reset' WHERE id=?", (original["id"],))
        elif state == "deleted":
            conn.execute("DELETE FROM user_sessions WHERE id=?", (original["id"],))
            assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions").fetchone()[0] == 0
        elif state == "unbound":
            conn.execute("UPDATE dashboard_sessions SET auth_session_id=NULL")
        elif state == "wrong_user":
            conn.execute("UPDATE dashboard_sessions SET user_id=?", (other["id"],))
        elif state == "disabled":
            conn.execute("UPDATE users SET is_active=0 WHERE id=?", (original["user_id"],))
        else:
            conn.execute("UPDATE users SET locked_until=datetime('now', '+1 hour') WHERE id=?",
                         (original["user_id"],))
    assert client.get(f"/api/v1/auth/session/{key}").status_code == 404
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions").fetchone()[0] == 0


def test_revocation_during_handle_creation_cannot_leave_usable_handle(client, dashboard_session, monkeypatch):
    from core.api.routes import auth_routes
    from core.auth import revoke_session
    from core.database import get_db

    tokens, headers, _, original = dashboard_session
    validate = auth_routes.validate_refresh_token

    def revoke_after_validation(raw):
        session = validate(raw)
        revoke_session(original["id"])
        return session

    monkeypatch.setattr(auth_routes, "validate_refresh_token", revoke_after_validation)
    result = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": tokens["refresh_token"]})
    assert result.status_code == 401
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions").fetchone()[0] == 0


def test_migration_discards_unverifiable_legacy_handles():
    import sqlite3
    from scripts.migrate import MIGRATIONS_DIR

    migration = MIGRATIONS_DIR / "026_dashboard_session_binding.sql"
    with sqlite3.connect(":memory:") as conn:
        for previous in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if previous.name < migration.name:
                conn.executescript(previous.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO dashboard_sessions "
            "(session_key, user_id, username, user_role, access_token, refresh_token, expires_at) "
            "VALUES (?, 'legacy', 'legacy', 'operator', '', '', datetime('now', '+1 day'))",
            (hashlib.sha256(b"legacy-handle").hexdigest(),),
        )
        conn.commit()
        conn.executescript(migration.read_text(encoding="utf-8"))
        assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions").fetchone()[0] == 0
        assert not conn.in_transaction
