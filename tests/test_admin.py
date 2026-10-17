"""Admin API tests — user management, API keys, audit log, backup."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _db(fresh_db):
    pass


@pytest.fixture()
def admin_headers(client):
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


# ── User management ───────────────────────────────────────────────────────────

def test_list_users(client, admin_headers):
    resp = client.get("/api/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json, list)
    assert any(u["username"] == "admin" for u in resp.json)


def test_create_user(client, admin_headers):
    resp = client.post(
        "/api/v1/admin/users",
        json={"username": "newop", "password": "Operator1!", "role": "operator"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json["role"] == "operator"


def test_create_duplicate_user(client, admin_headers):
    client.post(
        "/api/v1/admin/users",
        json={"username": "dup", "password": "Dupuser1!", "role": "viewer"},
        headers=admin_headers,
    )
    resp = client.post(
        "/api/v1/admin/users",
        json={"username": "dup", "password": "Dupuser1!", "role": "viewer"},
        headers=admin_headers,
    )
    assert resp.status_code in (409, 422, 400)


def test_patch_user_role(client, admin_headers):
    from core.auth import create_user
    u = create_user("patchme", "Patchme1!", role="viewer", namespace=None)
    resp = client.patch(
        f"/api/v1/admin/users/{u['id']}",
        json={"role": "operator"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["role"] == "operator"


def test_deactivate_user(client, admin_headers):
    from core.auth import create_user
    u = create_user("deactivate_me", "Deact1234!", role="viewer", namespace=None)
    resp = client.patch(
        f"/api/v1/admin/users/{u['id']}",
        json={"is_active": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["is_active"] is False


def test_delete_user(client, admin_headers):
    from core.auth import create_user
    u = create_user("delete_me", "Deleteme1!", role="viewer", namespace=None)
    resp = client.delete(f"/api/v1/admin/users/{u['id']}/permanent", headers=admin_headers)
    assert resp.status_code == 200


def test_cannot_delete_last_admin(client, admin_headers):
    from core.auth import get_user_by_username
    admin = get_user_by_username("admin")
    resp = client.delete(f"/api/v1/admin/users/{admin['id']}/permanent", headers=admin_headers)
    assert resp.status_code == 400


def test_unlock_user(client, admin_headers):
    from core.auth import create_user
    u = create_user("lockeduser", "Locked1234!", role="viewer", namespace=None)
    # Force lockout via DB
    from core.database import get_db
    from core.utils import utcnow_str
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts=5, locked_until=datetime('now','+15 minutes') WHERE id=?",
            (u["id"],),
        )
    resp = client.post(f"/api/v1/admin/users/{u['id']}/unlock", headers=admin_headers)
    assert resp.status_code == 200


# ── API Keys ──────────────────────────────────────────────────────────────────

def test_create_api_key(client, admin_headers):
    resp = client.post(
        "/api/v1/admin/api-keys",
        json={"name": "test-key", "namespace": "global", "permissions": ["read", "write"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert "raw_key" in resp.json
    assert resp.json["raw_key"].startswith("cos-")


def test_list_api_keys(client, admin_headers):
    client.post(
        "/api/v1/admin/api-keys",
        json={"name": "list-key", "namespace": "global", "permissions": ["read"]},
        headers=admin_headers,
    )
    resp = client.get("/api/v1/admin/api-keys", headers=admin_headers)
    assert resp.status_code == 200
    assert any(k["name"] == "list-key" for k in resp.json)


def test_regenerate_api_key(client, admin_headers):
    created = client.post(
        "/api/v1/admin/api-keys",
        json={"name": "regen-key", "namespace": "global", "permissions": ["read"]},
        headers=admin_headers,
    ).json
    resp = client.post(
        f"/api/v1/admin/api-keys/{created['id']}/regenerate",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "raw_key" in resp.json
    assert resp.json["raw_key"] != created.get("raw_key")


def test_delete_api_key(client, admin_headers):
    created = client.post(
        "/api/v1/admin/api-keys",
        json={"name": "del-key", "namespace": "global", "permissions": ["read"]},
        headers=admin_headers,
    ).json
    resp = client.delete(f"/api/v1/admin/api-keys/{created['id']}", headers=admin_headers)
    assert resp.status_code == 200


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_log_returns_events(client, admin_headers):
    resp = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json
    assert "events" in data
    assert "total" in data


def test_audit_log_event_type_filter(client, admin_headers):
    resp = client.get("/api/v1/admin/audit?event_type=login_success", headers=admin_headers)
    assert resp.status_code == 200
    events = resp.json.get("events", [])
    assert all(e["event_type"] == "login_success" for e in events)


# ── Security settings ─────────────────────────────────────────────────────────

def test_get_security_settings(client, admin_headers):
    resp = client.get("/api/v1/admin/security-settings", headers=admin_headers)
    assert resp.status_code == 200
    assert "max_failed_attempts" in resp.json


def test_update_security_settings(client, admin_headers):
    resp = client.patch(
        "/api/v1/admin/security-settings",
        json={"max_failed_attempts": "10", "lockout_minutes": "30"},
        headers=admin_headers,
    )
    assert resp.status_code == 200


# ── Backup ────────────────────────────────────────────────────────────────────

def test_list_backups(client, admin_headers):
    resp = client.get("/api/v1/admin/backup", headers=admin_headers)
    assert resp.status_code == 200
    assert "backups" in resp.json


def test_trigger_backup(client, admin_headers):
    resp = client.post("/api/v1/admin/backup", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json.get("ok") is True
    assert "file" in resp.json
