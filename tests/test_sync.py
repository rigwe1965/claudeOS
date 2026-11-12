"""Sync engine tests — watermark, push logic, log management."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _db(fresh_db, monkeypatch):
    # Clear Supabase config so unit tests run without real credentials
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    import core.config as cfg
    cfg._settings = None
    # Reset sync engine migration flag so it re-runs with fresh DB
    import sync.engine as se
    se._migration_done = False
    yield
    cfg._settings = None
    se._migration_done = False


# ── Sync status ───────────────────────────────────────────────────────────────

def test_get_status_shape():
    from sync.engine import get_status
    status = get_status()
    assert "configured" in status
    assert "table_states" in status
    assert "auto_sync_interval_min" in status


def test_get_status_unconfigured():
    """When Supabase is not configured, configured must be False."""
    from unittest.mock import patch
    from sync.engine import get_status
    # pydantic-settings reads from .env directly, so patch at the settings level
    with patch("sync.engine.get_settings") as mock_cfg:
        mock_cfg.return_value.SUPABASE_URL = ""
        mock_cfg.return_value.SUPABASE_SERVICE_KEY = ""
        mock_cfg.return_value.SYNC_INTERVAL_MIN = 15
        status = get_status()
    assert status["configured"] is False


# ── Watermark ─────────────────────────────────────────────────────────────────

def test_reset_watermark_all():
    from sync.engine import reset_watermark, get_status
    reset_watermark()
    status = get_status()
    for _table, state in status["table_states"].items():
        assert state["last_synced_at"] is None


def test_reset_watermark_single():
    from sync.engine import reset_watermark, get_status, _update_watermark
    _update_watermark("agent_runs", "2026-01-01T00:00:00", 5, 0, None)
    reset_watermark("agent_runs")
    status = get_status()
    ar = status["table_states"].get("agent_runs")
    if ar:
        assert ar["last_synced_at"] is None


# ── Push with no Supabase ────────────────────────────────────────────────────

def test_push_all_unconfigured():
    from unittest.mock import patch
    from sync.engine import push_all
    with patch("sync.engine._get_supabase", return_value=None):
        result = push_all()
    assert result.success is False
    assert any("not configured" in (t.error or "").lower() for t in result.tables)


def test_push_table_unconfigured():
    from unittest.mock import patch
    from sync.engine import push_table
    with patch("sync.engine._get_supabase", return_value=None):
        result = push_table("agent_runs")
    assert result.error is not None
    assert "not configured" in result.error.lower()


def test_push_unknown_table():
    from sync.engine import push_table
    result = push_table("nonexistent_table")
    assert result.error is not None


# ── Sync log ─────────────────────────────────────────────────────────────────

def test_get_sync_log_empty():
    from sync.engine import get_sync_log
    logs = get_sync_log()
    assert isinstance(logs, list)


def test_delete_log_entries_no_op():
    from sync.engine import delete_log_entries
    deleted = delete_log_entries([])
    assert deleted == 0


def test_delete_log_entry_not_found():
    from sync.engine import delete_log_entries
    deleted = delete_log_entries(["nonexistent-id"])
    assert deleted == 0


def test_sync_log_roundtrip():
    from sync.engine import _log_sync_run, get_sync_log, delete_log_entries
    from core.utils import new_id, utcnow_str
    log_id = new_id()
    _log_sync_run(log_id, "agent_runs", 5, 0, 123, None, utcnow_str())
    logs = get_sync_log(limit=10)
    assert any(l["id"] == log_id for l in logs)
    deleted = delete_log_entries([log_id])
    assert deleted == 1
    logs2 = get_sync_log(limit=10)
    assert not any(l["id"] == log_id for l in logs2)


# ── API endpoints ─────────────────────────────────────────────────────────────

@pytest.fixture()
def admin_headers(client):
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


def test_sync_status_endpoint(client, admin_headers):
    resp = client.get("/api/v1/sync/status", headers=admin_headers)
    assert resp.status_code == 200
    assert "configured" in resp.json


def test_sync_log_endpoint(client, admin_headers):
    resp = client.get("/api/v1/sync/log", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json, list)


def test_sync_push_endpoint(client, admin_headers):
    resp = client.post("/api/v1/sync/push", headers=admin_headers)
    assert resp.status_code in (200, 207)


def test_sync_reset_watermark_endpoint(client, admin_headers):
    resp = client.post("/api/v1/sync/reset-watermark", json={}, headers=admin_headers)
    assert resp.status_code == 200


def test_sync_push_unknown_table(client, admin_headers):
    resp = client.post("/api/v1/sync/push", json={"table": "hacker_table"}, headers=admin_headers)
    assert resp.status_code == 400


def test_workflow_webhook_secret_never_pushed():
    """Webhook secrets must not reach the cloud copy (audit H-2)."""
    import sync.engine as se
    from core.database import get_db
    from core.utils import new_id

    secret = "s3cr3t-" + "a" * 57
    with get_db() as conn:
        conn.execute(
            "INSERT INTO workflows (id, name, display_name, webhook_secret, webhook_enabled) "
            "VALUES (?, ?, ?, ?, 1)",
            (new_id(), "wf-secret-test", "WF Secret Test", secret),
        )

    pushed = []

    class _Query:
        def upsert(self, batch):
            pushed.extend(batch)
            return self

        def execute(self):
            return None

    class _Client:
        def table(self, name):
            return _Query()

    result = se._push_table(_Client(), "workflows", "created_at")

    assert result.error is None
    assert pushed, "expected the workflow row to be pushed"
    assert all("webhook_secret" not in rec for rec in pushed)
    assert secret not in repr(pushed)


def test_user_token_generation_stays_local():
    """The local revocation counter must not change the remote users schema."""
    from unittest.mock import Mock
    from core.auth import create_user, revoke_user_access
    from sync.engine import _push_table

    user = create_user("sync_user", "SyncPassword123!", role="operator")
    revoke_user_access(user["id"])
    remote = Mock()
    result = _push_table(remote, "users", "created_at")

    assert result.error is None
    assert result.rows_pushed == 1
    remote.table.assert_called_once_with("users")
    records = remote.table.return_value.upsert.call_args.args[0]
    assert records[0]["id"] == user["id"]
    assert "token_generation" not in records[0]


@pytest.fixture()
def rejecting_cloud():
    """Reject a whole upsert containing PostgreSQL-incompatible text."""
    from unittest.mock import Mock
    from postgrest.exceptions import APIError

    remote = Mock()
    delivered = {}
    attempts = []

    def execute():
        batch = remote.table.return_value.upsert.call_args.args[0]
        attempts.append(batch)
        if any("\x00" in value for record in batch for value in record.values()
               if isinstance(value, str)):
            raise APIError({"code": "22021", "message": "NUL is not supported in text"})
        delivered.update((record["id"], record) for record in batch)

    remote.table.return_value.upsert.return_value.execute.side_effect = execute
    return remote, delivered, attempts


@pytest.mark.parametrize("initial_state", ["missing", None, "2026-01-01T00:00:00+00:00"])
@pytest.mark.parametrize("count,rejected_index", [(1, 0), (201, 0), (201, 200)])
def test_failed_rows_remain_pending(initial_state, count, rejected_index, rejecting_cloud):
    """Failures in either batch must survive the next watermark selection."""
    from datetime import datetime, timedelta, timezone
    from core.database import get_db
    from sync.engine import _push_table, _update_watermark, get_status, get_sync_log

    if initial_state != "missing":
        _update_watermark("tickets", initial_state, 0, 0, None)
    timestamps = [
        (datetime(2026, 1, 2, tzinfo=timezone.utc) + timedelta(seconds=i)).isoformat()
        for i in range(count)
    ]
    with get_db() as conn:
        conn.execute("INSERT INTO namespaces (id, slug, display_name) VALUES ('sync', 'sync', 'Sync')")
        conn.executemany(
            "INSERT INTO tickets (id, namespace, created_by, title, description, created_at) "
            "VALUES (?, 'sync', ?, ?, 'description', ?)",
            [(str(i), f"user-{i}", "bad\x00title" if i == rejected_index else "good", timestamps[i])
             for i in range(count)],
        )

    remote, delivered, attempts = rejecting_cloud
    result = _push_table(remote, "tickets", "created_at")
    assert result.rows_pushed == count - 1
    assert result.rows_failed == 1
    assert result.error
    state = get_status()["table_states"]["tickets"]
    assert state["last_synced_at"] == (None if initial_state == "missing" else initial_state)
    assert state["rows_failed"] == 1
    assert state["last_error"] == result.error
    log = get_sync_log()[0]
    assert (log["rows_ok"], log["rows_fail"]) == (count - 1, 1)
    assert set(delivered) == {str(i) for i in range(count) if i != rejected_index}

    # Correcting the rejected row must make it eligible without resetting sync state.
    with get_db() as conn:
        conn.execute("UPDATE tickets SET title = 'fixed' WHERE id = ?", (str(rejected_index),))
    result = _push_table(remote, "tickets", "created_at")
    assert result.rows_pushed == count
    assert result.rows_failed == 0
    assert result.error is None
    assert len(delivered) == count
    state = get_status()["table_states"]["tickets"]
    assert state["last_synced_at"] == timestamps[-1]
    assert state["rows_failed"] == 0
    assert state["last_error"] is None

    # A successful watermark still prevents unnecessary resends.
    attempts_before = len(attempts)
    assert _push_table(remote, "tickets", "created_at").rows_pushed == 0
    assert len(attempts) == attempts_before


@pytest.mark.parametrize("field", ["title", "description"])
def test_client_ticket_cannot_suppress_another_tenants_sync(field, rejecting_cloud):
    from flask import Flask
    from core.api.routes.tickets import tickets_bp
    from core.auth import create_access_token, create_user
    from core.database import get_db
    from sync.engine import _push_table, get_status

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(tickets_bp)
    ticket_ids = []
    with app.test_client() as client:
        for namespace in ("attacker", "victim"):
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO namespaces (id, slug, display_name) VALUES (?, ?, ?)",
                    (namespace, namespace, namespace),
                )
            user = create_user(namespace, "SyncPassword123!", role="client", namespace=namespace)
            token = create_access_token(user["id"], namespace, "client", namespace)
            body = {"title": "Title", "description": "Description"}
            if namespace == "attacker":
                body[field] += "\x00"
            response = client.post("/api/v1/tickets", json=body,
                                   headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 201
            ticket_ids.append(response.json["id"])

    remote, delivered, _ = rejecting_cloud
    result = _push_table(remote, "tickets", "created_at")
    assert result.rows_pushed == 1
    assert result.rows_failed == 1
    assert set(delivered) == {ticket_ids[1]}
    assert delivered[ticket_ids[1]]["namespace"] == "victim"
    assert get_status()["table_states"]["tickets"]["last_synced_at"] is None
