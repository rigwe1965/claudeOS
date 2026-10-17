"""Tickets API tests — CRUD, status transitions, bulk ops, SLA."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _db(fresh_db):
    pass


@pytest.fixture()
def admin_headers(client):
    from core.auth import create_user
    from core.database import get_db
    from core.utils import new_id, utcnow_str
    # Seed "global" namespace — tickets table FKs on namespaces.slug
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO namespaces (id, slug, display_name, created_at) VALUES (?, 'global', 'Global', ?)",
            (new_id(), utcnow_str()),
        )
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


def _create_ticket(client, headers, **kwargs):
    payload = {
        "title": "Test ticket",
        "description": "Test description",
        "namespace": "global",
        **kwargs,
    }
    return client.post("/api/v1/tickets", json=payload, headers=headers)


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_ticket(client, admin_headers):
    resp = _create_ticket(client, admin_headers)
    assert resp.status_code == 201
    assert resp.json["title"] == "Test ticket"
    assert resp.json["status"] == "open"


def test_create_ticket_missing_fields(client, admin_headers):
    resp = client.post("/api/v1/tickets", json={"title": "no desc"}, headers=admin_headers)
    assert resp.status_code in (400, 422)


def test_create_ticket_unauthenticated(client):
    resp = _create_ticket(client, {})
    assert resp.status_code == 401


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_tickets(client, admin_headers):
    _create_ticket(client, admin_headers, title="T1")
    _create_ticket(client, admin_headers, title="T2")
    resp = client.get("/api/v1/tickets", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json) >= 2


def test_list_tickets_filter_status(client, admin_headers):
    _create_ticket(client, admin_headers)
    resp = client.get("/api/v1/tickets?status=open", headers=admin_headers)
    assert resp.status_code == 200
    assert all(t["status"] == "open" for t in resp.json)


# ── Get single ───────────────────────────────────────────────────────────────

def test_get_ticket_by_id(client, admin_headers):
    created = _create_ticket(client, admin_headers).json
    resp = client.get(f"/api/v1/tickets/{created['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json["id"] == created["id"]


def test_get_ticket_not_found(client, admin_headers):
    resp = client.get("/api/v1/tickets/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404


# ── Update — valid statuses: open→work_in_progress→completed/closed ──────────

def test_update_ticket_status(client, admin_headers):
    created = _create_ticket(client, admin_headers).json
    # open → work_in_progress is a valid transition
    resp = client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "work_in_progress"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["status"] == "work_in_progress"


def test_complete_ticket(client, admin_headers):
    created = _create_ticket(client, admin_headers).json
    # Move to work_in_progress first
    client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "work_in_progress"},
        headers=admin_headers,
    )
    resp = client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "completed", "resolution": "Done."},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["status"] == "completed"


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_ticket(client, admin_headers):
    created = _create_ticket(client, admin_headers).json
    resp = client.delete(f"/api/v1/tickets/{created['id']}", headers=admin_headers)
    assert resp.status_code == 200
    get_resp = client.get(f"/api/v1/tickets/{created['id']}", headers=admin_headers)
    assert get_resp.status_code == 404


def test_bulk_delete_tickets(client, admin_headers):
    ids = [_create_ticket(client, admin_headers).json["id"] for _ in range(3)]
    resp = client.delete(
        "/api/v1/tickets/bulk",
        json={"ids": ids},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    # Response may use "deleted" count or list
    body = resp.json
    deleted = body.get("deleted", [])
    count = deleted if isinstance(deleted, int) else len(deleted)
    assert count >= 3


# ── Priority / SLA ───────────────────────────────────────────────────────────

def test_ticket_priority_field(client, admin_headers):
    resp = _create_ticket(client, admin_headers, priority=1)
    assert resp.status_code == 201
    assert resp.json["priority"] == 1


def test_ticket_sla_tier(client, admin_headers):
    resp = _create_ticket(client, admin_headers, sla_tier="gold")
    assert resp.status_code == 201
