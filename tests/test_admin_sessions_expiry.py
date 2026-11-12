"""GET /api/v1/admin/sessions lists only sessions that have not expired.

user_sessions.expires_at is written with datetime.isoformat() ("2026-11-12T13:25:33+00:00", a "T" between date and time), but the
list compared it to CURRENT_TIMESTAMP ("2026-11-12 13:25:33", a space) as text. On the same calendar day "T" sorts after " ", so a
session that expired a minute ago still looked active until midnight UTC. Comparing as times fixes it.
"""
from datetime import timedelta

import pytest

from core.utils import new_id, utcnow


@pytest.fixture(autouse=True)
def _db(fresh_db):
    pass


@pytest.fixture()
def admin_headers(client):
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


def _add_session(expires_at, revoked=0):
    from core.database import get_db
    with get_db() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"]
        session_id = new_id()
        conn.execute(
            "INSERT INTO user_sessions(id, user_id, token_hash, user_agent, expires_at, revoked) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, new_id(), "test", expires_at.isoformat(), revoked),
        )
    return session_id


def _listed_ids(client, headers):
    resp = client.get("/api/v1/admin/sessions", headers=headers)
    assert resp.status_code == 200
    return {row["id"] for row in resp.json}


def test_session_that_expired_seconds_ago_is_not_listed(client, admin_headers):
    # One second ago is on the same calendar day (except in the first second after midnight UTC), the case that was wrong.
    expired = _add_session(utcnow() - timedelta(seconds=1))
    assert expired not in _listed_ids(client, admin_headers)


def test_session_that_expired_an_hour_ago_is_not_listed(client, admin_headers):
    expired = _add_session(utcnow() - timedelta(hours=1))
    assert expired not in _listed_ids(client, admin_headers)


def test_session_that_expires_later_is_listed(client, admin_headers):
    live = _add_session(utcnow() + timedelta(hours=1))
    assert live in _listed_ids(client, admin_headers)


def test_revoked_session_is_not_listed_even_if_unexpired(client, admin_headers):
    revoked = _add_session(utcnow() + timedelta(hours=1), revoked=1)
    assert revoked not in _listed_ids(client, admin_headers)


def test_the_admins_own_login_session_is_listed(client, admin_headers):
    assert _listed_ids(client, admin_headers), "the session created by the login above must be listed"
