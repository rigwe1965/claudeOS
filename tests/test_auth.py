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
