"""Mandatory password changes must be enforced by the API for every token issuer."""
import pytest


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer", "staff"])
def test_password_change_required_blocks_protected_operations(client, role):
    from core.auth import create_user, get_user_by_id
    from core.database import get_db

    with get_db() as conn:
        conn.execute("INSERT INTO namespaces(id, slug, display_name) VALUES ('tenant', 'tenant', 'Tenant')")
    user = create_user("temporary", "TemporaryPass123!", role=role,
                       namespace="tenant", must_change_password=True)
    login = client.post("/api/v1/auth/login", json={
        "username": user["username"], "password": "TemporaryPass123!",
    })
    assert login.status_code == 200
    assert login.json["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json['access_token']}"}

    requests = [
        ("GET", "/api/v1/outputs", None),
        ("POST", "/api/v1/outputs", {"namespace": "tenant", "title": "blocked", "content": "private"}),
        ("GET", "/api/v1/auth/me", None),
        ("POST", "/api/v1/auth/onboarding-done", {}),
        ("PATCH", f"/api/v1/admin/users/{user['id']}", {"must_change_password": False}),
        ("POST", "/api/v1/auth/session", {"refresh_token": login.json["refresh_token"]}),
    ]
    for method, path, body in requests:
        response = client.open(path, method=method, headers=headers, json=body)
        assert response.status_code == 403, (method, path, response.json)
        assert response.json == {"error": "Password change required", "must_change_password": True}
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM dashboard_sessions").fetchone()[0] == 0
    assert get_user_by_id(user["id"])["must_change_password"] == 1

    # A refreshed token must carry the same restriction, including on a cache hit.
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": login.json["refresh_token"]})
    assert refreshed.status_code == 200
    refreshed_headers = {"Authorization": f"Bearer {refreshed.json['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=refreshed_headers).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=headers,
                       json={"refresh_token": login.json["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh",
                       json={"refresh_token": login.json["refresh_token"]}).status_code == 401

    invalid = client.post("/api/v1/auth/change-password", headers=headers,
                          json={"current_password": "wrong", "new_password": "ReplacementPass123!"})
    assert invalid.status_code == 401
    assert get_user_by_id(user["id"])["must_change_password"] == 1
    unchanged = client.post("/api/v1/auth/change-password", headers=headers,
                            json={"current_password": "TemporaryPass123!", "new_password": "TemporaryPass123!"})
    assert unchanged.status_code == 422
    assert get_user_by_id(user["id"])["must_change_password"] == 1

    changed = client.post("/api/v1/auth/change-password", headers=headers,
                          json={"current_password": "TemporaryPass123!", "new_password": "ReplacementPass123!"})
    assert changed.status_code == 200
    assert get_user_by_id(user["id"])["must_change_password"] == 0
    new_headers = {"Authorization": f"Bearer {changed.json['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200


def test_admin_password_requirement_applies_to_cached_and_restored_tokens(
        client, admin_token, monkeypatch, tmp_path):
    from core.auth import create_user
    from outputs import manager

    monkeypatch.setattr(manager, "STORE_ROOT", tmp_path / "outputs")
    user = create_user("existing", "ExistingPass123!", role="operator")
    login = client.post("/api/v1/auth/login", json={
        "username": user["username"], "password": "ExistingPass123!",
    }).json
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    session = client.post("/api/v1/auth/session", headers=headers,
                          json={"refresh_token": login["refresh_token"]})
    assert session.status_code == 200
    assert client.get("/api/v1/outputs", headers=headers).status_code == 200

    # Hold the cache clock fixed so state changes are checked on JWT cache hits.
    monkeypatch.setattr("core.auth.time.monotonic", lambda: 100.0)
    assert client.get("/api/v1/outputs", headers=headers).status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    patched = client.patch(f"/api/v1/admin/users/{user['id']}", headers=admin_headers,
                           json={"must_change_password": True})
    assert patched.status_code == 200
    assert client.get("/api/v1/outputs", headers=headers).status_code == 403

    restored = client.get(f"/api/v1/auth/session/{session.json['session_key']}")
    assert restored.status_code == 200
    assert restored.json["must_change_password"] is True
    restored_headers = {"Authorization": f"Bearer {restored.json['access_token']}"}
    assert client.post("/api/v1/outputs", headers=restored_headers, json={
        "namespace": "global", "title": "blocked", "content": "private",
    }).status_code == 403

    cleared = client.patch(f"/api/v1/admin/users/{user['id']}", headers=admin_headers,
                           json={"must_change_password": False})
    assert cleared.status_code == 200
    assert client.get("/api/v1/outputs", headers=headers).status_code == 200
    assert client.post("/api/v1/outputs", headers=headers, json={
        "namespace": "global", "title": "allowed", "content": "saved after clearing the restriction",
    }).status_code == 201
