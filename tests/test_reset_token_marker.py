"""A client-supplied User-Agent must never turn a session into a password-reset credential."""


def test_user_agent_cannot_forge_reset_token(client):
    from core.auth import create_user
    create_user("victim", "Victim12345!", role="viewer", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "victim", "password": "Victim12345!"},
                    headers={"User-Agent": "password_reset"})
    assert r.status_code == 200
    r = client.post("/api/v1/auth/reset-password",
                    json={"reset_token": r.json["refresh_token"], "new_password": "Changed12345!"})
    assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "victim", "password": "Victim12345!"})
    assert r.status_code == 200


def test_real_reset_token_still_works(client, admin_token):
    from core.auth import create_user
    create_user("target", "Target12345!", role="viewer", namespace=None)
    r = client.post("/api/v1/auth/forgot-password", json={"username": "target"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    r = client.post("/api/v1/auth/reset-password",
                    json={"reset_token": r.json["reset_token"], "new_password": "Changed12345!"})
    assert r.status_code == 200
