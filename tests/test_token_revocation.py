"""Account revocation must distinguish tokens issued within the same second."""
from datetime import timedelta

import jwt
import pytest

from core import auth


@pytest.fixture
def same_second(monkeypatch):
    now = auth.utcnow().replace(microsecond=100_000)
    monkeypatch.setattr(auth, "utcnow", lambda: now)
    return now


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client):
    result = client.post("/api/v1/auth/login", json={
        "username": "revocation_user", "password": "OriginalPass123!",
    })
    assert result.status_code == 200
    return result.json


@pytest.mark.parametrize("event", [
    "change-password", "reset-password", "admin-reset", "role-change", "reactivate",
])
def test_security_events_reject_earlier_tokens_in_same_second(
        client, admin_token, same_second, monkeypatch, event):
    from core.database import get_db

    user = auth.create_user("revocation_user", "OriginalPass123!", role="operator")
    tokens = _login(client)
    headers = _headers(tokens["access_token"])
    handle = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": tokens["refresh_token"]}).json["session_key"]
    # Populate both JWT verification and authorization state caches, if present.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    monkeypatch.setattr(auth, "utcnow", lambda: same_second + timedelta(microseconds=800_000))
    admin_headers = _headers(admin_token)
    password = "ReplacementPass123!"
    if event == "change-password":
        changed = client.post("/api/v1/auth/change-password", headers=headers, json={
            "current_password": "OriginalPass123!", "new_password": password,
        })
        assert changed.status_code == 200
        replacement = changed.json["access_token"]
    else:
        if event == "reset-password":
            reset = client.post("/api/v1/auth/forgot-password", headers=admin_headers,
                                json={"username": user["username"]})
            assert reset.status_code == 200
            result = client.post("/api/v1/auth/reset-password", json={
                "reset_token": reset.json["reset_token"], "new_password": password,
            })
        elif event == "admin-reset":
            result = client.post(f"/api/v1/admin/users/{user['id']}/reset-password",
                                 headers=admin_headers, json={"new_password": password})
        else:
            updates = {"role": "admin"} if event == "role-change" else {"is_active": False}
            result = client.patch(f"/api/v1/admin/users/{user['id']}", headers=admin_headers, json=updates)
            password = "OriginalPass123!"
            if event == "reactivate":
                assert result.status_code == 200
                result = client.patch(f"/api/v1/admin/users/{user['id']}", headers=admin_headers,
                                      json={"is_active": True})
        assert result.status_code == 200
        login = client.post("/api/v1/auth/login", json={"username": user["username"], "password": password})
        assert login.status_code == 200
        replacement = login.json["access_token"]

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/outputs", headers=headers, json={
        "namespace": "global", "title": "revoked", "content": "must not be saved",
    }).status_code == 401
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.get(f"/api/v1/auth/session/{handle}").status_code == 404
    assert client.get("/api/v1/auth/me", headers=admin_headers).status_code == 200
    assert auth.decode_access_token(replacement)["iat"] == auth.decode_access_token(tokens["access_token"])["iat"]
    expected = 403 if event == "admin-reset" else 200
    assert client.get("/api/v1/auth/me", headers=_headers(replacement)).status_code == expected
    if event == "admin-reset":
        changed = client.post("/api/v1/auth/change-password", headers=_headers(replacement), json={
            "current_password": password, "new_password": "FinalPassword123!",
        })
        assert changed.status_code == 200
        assert client.get("/api/v1/auth/me", headers=_headers(changed.json["access_token"])).status_code == 200


def test_repeated_revocations_and_migration_replay_preserve_generation(client, same_second):
    from scripts.migrate import run_all
    from core.api.app import _run_migrations

    user = auth.create_user("revocation_user", "OriginalPass123!", role="operator")
    tokens = []
    for generation in range(3):
        current = _login(client)["access_token"]
        assert client.get("/api/v1/auth/me", headers=_headers(current)).status_code == 200
        assert auth.decode_access_token(current)["token_generation"] == generation
        for old in tokens:
            assert client.get("/api/v1/auth/me", headers=_headers(old)).status_code == 401
        tokens.append(current)
        if generation < 2:
            auth.revoke_user_access(user["id"])
    run_all()
    _run_migrations()
    assert auth.get_user_by_id(user["id"])["token_generation"] == 2
    assert client.get("/api/v1/auth/me", headers=_headers(tokens[-1])).status_code == 200


@pytest.mark.parametrize("generation", [None, "0", False, 0.0, -1, 1])
def test_missing_malformed_or_stale_generation_is_denied(client, same_second, generation):
    auth.create_user("revocation_user", "OriginalPass123!", role="operator")
    payload = auth.decode_access_token(_login(client)["access_token"])
    if generation is None:
        payload.pop("token_generation", None)
    else:
        payload["token_generation"] = generation
    token = jwt.encode(payload, auth._secret(), algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers=_headers(token)).status_code == 401


def test_revocation_in_another_worker_is_seen_on_next_request(client, same_second):
    from core.database import get_db

    user = auth.create_user("revocation_user", "OriginalPass123!", role="operator")
    token = _login(client)["access_token"]
    assert client.get("/api/v1/auth/me", headers=_headers(token)).status_code == 200
    # Another process only shares database state, not in-memory cache invalidation.
    with get_db() as conn:
        conn.execute("UPDATE users SET token_generation = token_generation + 1 WHERE id = ?", (user["id"],))
    assert client.get("/api/v1/auth/me", headers=_headers(token)).status_code == 401


@pytest.mark.parametrize("issuer", ["login", "refresh", "dashboard", "change-password"])
def test_revocation_during_issuance_cannot_upgrade_old_credentials(
        client, same_second, monkeypatch, issuer):
    from core.api.routes import auth_routes

    user = auth.create_user("revocation_user", "OriginalPass123!", role="operator")
    tokens = _login(client)
    headers = _headers(tokens["access_token"])
    handle = client.post("/api/v1/auth/session", headers=headers,
                         json={"refresh_token": tokens["refresh_token"]}).json["session_key"]
    if issuer == "refresh":
        validate = auth_routes.validate_refresh_token

        def revoke_after_validation(raw):
            session = validate(raw)
            auth.revoke_user_access(user["id"])
            return session

        monkeypatch.setattr(auth_routes, "validate_refresh_token", revoke_after_validation)
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    else:
        create = auth_routes.create_access_token

        def revoke_before_signing(*args, **kwargs):
            auth.revoke_user_access(user["id"])
            return create(*args, **kwargs)

        monkeypatch.setattr(auth_routes, "create_access_token", revoke_before_signing)
        if issuer == "login":
            response = client.post("/api/v1/auth/login", json={
                "username": user["username"], "password": "OriginalPass123!",
            })
        elif issuer == "dashboard":
            response = client.get(f"/api/v1/auth/session/{handle}")
        else:
            response = client.post("/api/v1/auth/change-password", headers=headers, json={
                "current_password": "OriginalPass123!", "new_password": "ReplacementPass123!",
            })
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=_headers(response.json["access_token"])).status_code == 401


def test_generation_migration_preserves_existing_revocation_cutoff():
    import sqlite3
    from scripts.migrate import MIGRATIONS_DIR

    migration = MIGRATIONS_DIR / "027_access_token_generation.sql"
    with sqlite3.connect(":memory:") as conn:
        for previous in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if previous.name < migration.name:
                conn.executescript(previous.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO users(id, username, password_hash, tokens_valid_after) "
                     "VALUES ('legacy', 'legacy', 'unused', 1234567890)")
        conn.commit()
        conn.executescript(migration.read_text(encoding="utf-8"))
        assert conn.execute("SELECT token_generation, tokens_valid_after FROM users").fetchone() == (0, 1234567890)
        assert not conn.in_transaction
