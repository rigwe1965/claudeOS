"""Auth API tests — login, register, refresh, roles, lockout."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _db(fresh_db):
    pass


@pytest.fixture()
def _admin(client):
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    return "admin", "Admin1234!"


@pytest.fixture()
def admin_tok(client, _admin):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    assert resp.status_code == 200
    return resp.json["access_token"]


# ── Login ────────────────────────────────────────────────────────────────────

def test_login_success(client, _admin):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    assert resp.status_code == 200
    assert "access_token" in resp.json
    assert "refresh_token" in resp.json


def test_login_bad_password(client, _admin):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "Admin1234!"})
    assert resp.status_code == 401


def test_login_case_insensitive(client, _admin):
    resp = client.post("/api/v1/auth/login", json={"username": "ADMIN", "password": "Admin1234!"})
    assert resp.status_code == 200


# ── /auth/me ─────────────────────────────────────────────────────────────────

def test_me_returns_user(client, admin_tok):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_tok}"})
    assert resp.status_code == 200
    assert resp.json["username"] == "admin"
    assert resp.json["role"] == "admin"


def test_me_no_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

def test_token_refresh(client, _admin):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    refresh_token = login.json["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json


def test_token_refresh_invalid(client):
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad-token"})
    assert resp.status_code == 401


# ── Credential purpose ──────────────────────────────────────────────────────

@pytest.mark.parametrize("issuer", ["login", "dashboard", "change-password"])
def test_user_agent_cannot_authorize_password_reset(client, _admin, issuer):
    from core.auth import get_user_by_username

    credentials = {"username": "admin", "password": "Admin1234!"}
    spoofed = {"User-Agent": "password_reset"}
    login = client.post("/api/v1/auth/login", json=credentials,
                        headers=spoofed if issuer == "login" else {})
    assert login.status_code == 200
    tokens = login.json
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    if issuer == "dashboard":
        session = client.post("/api/v1/auth/session", headers=headers,
                              json={"refresh_token": tokens["refresh_token"]})
        assert session.status_code == 200
        restored = client.get(f"/api/v1/auth/session/{session.json['session_key']}", headers=spoofed)
        assert restored.status_code == 200
        tokens = restored.json
    elif issuer == "change-password":
        changed = client.post("/api/v1/auth/change-password", headers={**headers, **spoofed},
                              json={"current_password": credentials["password"],
                                    "new_password": "ChangedPass123!"})
        assert changed.status_code == 200
        tokens = changed.json

    original_hash = get_user_by_username("admin")["password_hash"]
    reset = client.post("/api/v1/auth/reset-password",
                        json={"reset_token": tokens["refresh_token"], "new_password": "StolenPass123!"})
    assert reset.status_code == 401
    assert get_user_by_username("admin")["password_hash"] == original_hash
    assert client.post("/api/v1/auth/refresh",
                       json={"refresh_token": tokens["refresh_token"]}).status_code == 200


@pytest.mark.parametrize("user_agent", ["Admin browser", "password_reset"])
def test_admin_reset_token_is_separate_and_single_use(client, admin_tok, user_agent):
    from core.auth import create_user, get_user_by_id, verify_password
    from core.database import get_db

    user = create_user("reset_user", "OriginalPass123!", role="operator", namespace=None)
    login = client.post("/api/v1/auth/login",
                        json={"username": "reset_user", "password": "OriginalPass123!"}).json
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    handle = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": login["refresh_token"]}).json["session_key"]
    assert client.post("/api/v1/auth/forgot-password",
                       json={"username": "reset_user"}).status_code == 401
    assert client.post("/api/v1/auth/forgot-password", headers=headers,
                       json={"username": "reset_user"}).status_code == 403
    issued = client.post("/api/v1/auth/forgot-password",
                         headers={"Authorization": f"Bearer {admin_tok}", "User-Agent": user_agent},
                         json={"username": "reset_user", "token_purpose": "refresh"})
    assert issued.status_code == 200
    token = issued.json["reset_token"]
    with get_db() as conn:
        row = conn.execute("SELECT * FROM user_sessions WHERE token_purpose='password_reset'").fetchone()
    assert row["user_agent"] == user_agent
    # Both migration entry points may run after credentials have been issued.
    from scripts.migrate import run_all
    from core.api.app import _run_migrations
    run_all()
    _run_migrations()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401
    assert client.post("/api/v1/auth/session", headers=headers,
                       json={"refresh_token": token}).status_code == 401
    reset_body = {"reset_token": token, "new_password": "Replacement123!"}
    assert client.post("/api/v1/auth/reset-password", json=reset_body).status_code == 200
    assert verify_password(reset_body["new_password"], get_user_by_id(user["id"])["password_hash"])
    assert client.post("/api/v1/auth/reset-password", json=reset_body).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401
    assert client.get(f"/api/v1/auth/session/{handle}").status_code == 404


@pytest.mark.parametrize("invalid_state", ["expired", "revoked", "disabled"])
def test_reset_token_requires_live_credential_and_user(client, admin_tok, invalid_state):
    from core.auth import get_user_by_username
    from core.database import get_db

    issued = client.post("/api/v1/auth/forgot-password",
                         headers={"Authorization": f"Bearer {admin_tok}"}, json={"username": "admin"})
    assert issued.status_code == 200
    original_hash = get_user_by_username("admin")["password_hash"]
    with get_db() as conn:
        if invalid_state == "expired":
            conn.execute("UPDATE user_sessions SET expires_at=datetime('now', '-1 hour')")
        elif invalid_state == "revoked":
            conn.execute("UPDATE user_sessions SET revoked=1")
        else:
            conn.execute("UPDATE users SET is_active=0 WHERE username='admin'")
    assert client.post("/api/v1/auth/reset-password",
                       json={"reset_token": issued.json["reset_token"],
                             "new_password": "Replacement123!"}).status_code == 401
    assert get_user_by_username("admin")["password_hash"] == original_hash


def test_session_purpose_migration_revokes_ambiguous_legacy_credentials():
    import sqlite3
    from scripts.migrate import MIGRATIONS_DIR

    migration = MIGRATIONS_DIR / "025_session_token_purpose.sql"
    with sqlite3.connect(":memory:") as conn:
        for previous in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if previous.name < migration.name:
                conn.executescript(previous.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO users(id, username, password_hash) VALUES ('u', 'legacy', 'unused')")
        for session_id, ua in [("normal", "Browser"), ("reset", "password_reset"), ("forged", "password_reset")]:
            conn.execute(
                "INSERT INTO user_sessions(id, user_id, token_hash, user_agent, expires_at) "
                "VALUES (?, 'u', ?, ?, datetime('now', '+1 hour'))", (session_id, session_id, ua),
            )
        conn.commit()
        conn.executescript(migration.read_text(encoding="utf-8"))
        rows = {row[0]: row[1:] for row in conn.execute("SELECT id, token_purpose, revoked FROM user_sessions")}
        assert rows == {"normal": ("refresh", 0), "reset": ("refresh", 1), "forged": ("refresh", 1)}
        assert not conn.in_transaction


# ── Self-registration ─────────────────────────────────────────────────────────

def test_self_register(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "password": "Newpass123!",
        "email": "new@example.com",
    })
    # 201/200 = created; 403 = self-register disabled; 422 = validation error
    assert resp.status_code in (201, 200, 403, 422)


def test_register_weak_password(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "weakuser",
        "password": "short",
    })
    assert resp.status_code in (400, 422, 403)


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout(client, _admin):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    tok = login.json["access_token"]
    refresh = login.json["refresh_token"]
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200


# ── Account lockout ───────────────────────────────────────────────────────────

def test_lockout_after_failed_attempts(client, _admin):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpass"})
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    # 423 Locked or 401 Unauthorized — both indicate locked account
    assert resp.status_code in (401, 423)
    body = resp.json.get("error", "") or ""
    assert "lock" in body.lower() or resp.status_code == 423


# ── Role enforcement ──────────────────────────────────────────────────────────

def test_viewer_cannot_access_admin(client):
    from core.auth import create_user
    # namespace=None avoids FK constraint against namespaces table
    create_user("viewer1", "Viewer1234!", role="viewer", namespace=None)
    login = client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "Viewer1234!"})
    tok = login.json["access_token"]
    resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403
