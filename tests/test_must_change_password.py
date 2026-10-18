"""must_change_password must be enforced by the API, not only by the dashboard."""


def _login(client, user, pw):
    r = client.post("/api/v1/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.json
    return {"Authorization": f"Bearer {r.json['access_token']}"}


def test_must_change_password_blocks_api_until_changed(client, admin_token):
    from core.auth import create_user
    create_user("tempuser", "TempPass1234!", role="operator", namespace=None, must_change_password=True)
    h = _login(client, "tempuser", "TempPass1234!")

    blocked = client.get("/api/v1/memory", headers=h)
    assert blocked.status_code == 403 and blocked.json["must_change_password"] is True
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200

    r = client.post("/api/v1/auth/change-password", headers=h,
                    json={"current_password": "TempPass1234!", "new_password": "NewPass1234!x"})
    assert r.status_code == 200, r.json
    h2 = {"Authorization": f"Bearer {r.json['access_token']}"}
    assert client.get("/api/v1/memory", headers=h2).status_code == 200
