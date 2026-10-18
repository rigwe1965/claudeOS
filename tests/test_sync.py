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


def _fake_sb(bad_ids, pushed):
    class _Q:
        def __init__(self, rows): self.rows = rows
        def execute(self):
            if any(r["id"] in bad_ids for r in self.rows):
                raise RuntimeError("rejected")
            pushed.extend(r["id"] for r in self.rows)

    class _T:
        def upsert(self, rows): return _Q(rows)

    class _SB:
        def table(self, name): return _T()

    return _SB()


def test_failed_record_does_not_advance_watermark_or_block_others(monkeypatch):
    import sync.engine as se
    rows = [{"id": f"r{i}", "updated_at": f"2026-01-0{i + 1}T00:00:00"} for i in range(3)]

    class _Conn:
        def execute(self, sql, params=()):
            class _C:
                def fetchone(s): return None
                def fetchall(s): return rows
            return _C()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(se, "get_db", lambda: _Conn())
    saved = {}
    monkeypatch.setattr(se, "_update_watermark", lambda t, w, ok, fail, err: saved.update(w=w, ok=ok, fail=fail))
    monkeypatch.setattr(se, "_log_sync_run", lambda *a, **k: None)
    pushed = []
    res = se._push_table(_fake_sb({"r1"}, pushed), "tickets", "updated_at")
    assert pushed == ["r0", "r2"] and res.rows_failed == 1
    assert saved["w"] == "2026-01-01T00:00:00"  # stops before the failed record

    pushed.clear()
    se._push_table(_fake_sb({"r0"}, pushed), "tickets", "updated_at")
    assert saved["w"] is None  # nothing before the failure, no prior watermark: stay unset
