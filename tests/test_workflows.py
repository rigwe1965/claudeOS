"""Workflow API tests — list, get, patch, webhook, run history."""
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


def _db_seed_workflow(name="test-wf", namespace="global"):
    """Insert a workflow directly via the registry (no POST API endpoint)."""
    from workflows.registry import upsert
    from workflows.schemas import WorkflowDefinition
    from core.utils import new_id
    wf = WorkflowDefinition(
        id=new_id(),
        name=name,
        display_name="Test Workflow",
        description="For testing",
        trigger_type="manual",
        steps=[],
        namespace=namespace,
    )
    upsert(wf)
    return wf


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_workflows(client, admin_headers):
    resp = client.get("/api/v1/workflows", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json, list)


def test_list_workflows_shows_seeded(client, admin_headers):
    _db_seed_workflow(name="listed-wf")
    resp = client.get("/api/v1/workflows", headers=admin_headers)
    assert resp.status_code == 200
    names = [w["name"] for w in resp.json]
    assert "listed-wf" in names


# ── Get ───────────────────────────────────────────────────────────────────────

def test_get_workflow(client, admin_headers):
    _db_seed_workflow(name="get-wf")
    resp = client.get("/api/v1/workflows/get-wf", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json["name"] == "get-wf"


def test_get_workflow_not_found(client, admin_headers):
    resp = client.get("/api/v1/workflows/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_workflow_patch_enabled(client, admin_headers):
    """PATCH /workflows/<name> only supports toggling 'enabled'."""
    _db_seed_workflow(name="update-wf")
    resp = client.patch(
        "/api/v1/workflows/update-wf",
        json={"enabled": 1},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["enabled"] in (1, True)


def test_enable_disable_workflow(client, admin_headers):
    _db_seed_workflow(name="toggle-wf")
    resp = client.patch(
        "/api/v1/workflows/toggle-wf",
        json={"enabled": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["enabled"] in (0, False)


# ── Run history ───────────────────────────────────────────────────────────────

def test_workflow_runs_empty(client, admin_headers):
    resp = client.get("/api/v1/workflows/runs/all", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json, list)


@pytest.fixture
def workflow_read_access(app, monkeypatch, tmp_path):
    from core.auth import create_access_token, create_user
    from vault import manager as vault
    from vault.schemas import NamespaceCreate
    from workflows.pipeline import create_run_record, _update_run

    monkeypatch.setattr(vault, "VAULT_ROOT", tmp_path / "vault")
    workflows, runs = [], []
    for namespace in ("ns-a", "ns-b"):
        vault.create_namespace(NamespaceCreate(slug=namespace, display_name=namespace, type="client"))
        wf = _db_seed_workflow(name=f"wf-{namespace}", namespace=namespace)
        workflows.append(wf)
        run_id = create_run_record(wf.id, "test", {"namespace": namespace, "private": namespace})
        _update_run(run_id, "done", output=f"private {namespace}",
                    steps_log=[{"output_preview": f"private {namespace}"}])
        runs.append(run_id)
    # Runs must be checked by their own context, even under an accessible workflow.
    foreign_run = create_run_record(workflows[0].id, "test", {"namespace": "ns-b"})
    runs.append(foreign_run)

    def headers(role, namespace=None):
        user = create_user("workflow_reader", "WorkflowReader123!", role=role, namespace=namespace)
        token = create_access_token(user["id"], user["username"], role, namespace)
        return {"Authorization": f"Bearer {token}"}

    return workflows, runs, headers


def _workflow_read_paths(workflow, run_id):
    return ("", f"/{workflow.name}", f"/{workflow.name}/runs", "/runs/all", f"/runs/{run_id}")


@pytest.mark.parametrize("role, namespace", [("staff", None), ("staff", "ns-a"), ("unknown", None)])
def test_roles_without_workflow_access_never_reach_storage(client, workflow_read_access, monkeypatch,
                                                         role, namespace):
    from workflows import pipeline, registry

    workflows, runs, make_headers = workflow_read_access
    headers = make_headers(role, namespace)

    def forbidden_storage(*args, **kwargs):
        pytest.fail("Unauthorized workflow request reached storage")

    monkeypatch.setattr(registry, "list_workflows", forbidden_storage)
    monkeypatch.setattr(registry, "get_by_name", forbidden_storage)
    monkeypatch.setattr(pipeline, "list_runs", forbidden_storage)
    monkeypatch.setattr(pipeline, "get_run", forbidden_storage)
    for path in _workflow_read_paths(workflows[0], runs[0]):
        response = client.get(f"/api/v1/workflows{path}", headers=headers)
        assert response.status_code == 403, (path, response.get_data(as_text=True))


def _assert_workflow_read_permissions(client, workflows, runs, headers, scoped):
    listing = client.get("/api/v1/workflows", headers=headers)
    assert listing.status_code == 200
    expected_workflows = workflows[:1] if scoped else workflows
    assert {wf["id"] for wf in listing.json} == {wf.id for wf in expected_workflows}
    all_runs = client.get("/api/v1/workflows/runs/all", headers=headers)
    assert all_runs.status_code == 200
    assert {run["id"] for run in all_runs.json} == set(runs[:1] if scoped else runs)
    for index, wf in enumerate(workflows):
        allowed = not scoped or index == 0
        detail = client.get(f"/api/v1/workflows/{wf.name}", headers=headers)
        assert detail.status_code == (200 if allowed else 404)
        if allowed:
            assert ("steps" in detail.json) == (not scoped)
        history = client.get(f"/api/v1/workflows/{wf.name}/runs", headers=headers)
        assert history.status_code == (200 if allowed else 404)
        if allowed:
            expected = {runs[index]}
            if not scoped and index == 0:
                expected.add(runs[2])
            assert {run["id"] for run in history.json} == expected
    for index, run_id in enumerate(runs):
        response = client.get(f"/api/v1/workflows/runs/{run_id}", headers=headers)
        assert response.status_code == (200 if not scoped or index == 0 else 404)


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer"])
def test_workflow_read_permissions(client, workflow_read_access, role):
    workflows, runs, make_headers = workflow_read_access
    scoped = role in ("client", "viewer")
    headers = make_headers(role, "ns-a" if scoped else None)
    _assert_workflow_read_permissions(client, workflows, runs, headers, scoped)


@pytest.mark.parametrize("namespace", ["global", "ns-a"])
def test_workflow_read_api_key_permissions(client, workflow_read_access, namespace):
    from core.api.auth import create_api_key

    workflows, runs, _ = workflow_read_access
    raw_key, _ = create_api_key("workflow-key", permissions=["read"], namespace=namespace)
    _assert_workflow_read_permissions(client, workflows, runs, {"X-API-Key": raw_key}, namespace == "ns-a")


# ── Run delete ───────────────────────────────────────────────────────────────


def _seed_run(status="done"):
    """Seed a workflow + run row, return the run id."""
    _db_seed_workflow(name="run-seed-wf")
    from workflows.registry import get_by_name
    from workflows.pipeline import create_run_record
    wf_row = get_by_name("run-seed-wf")
    run_id = create_run_record(wf_row.id, triggered_by="test", context={"namespace": "global"})
    if status != "pending":
        from core.database import get_db
        with get_db() as conn:
            conn.execute("UPDATE workflow_runs SET status=? WHERE id=?", (status, run_id))
    return run_id


def test_delete_single_run(client, admin_headers):
    run_id = _seed_run()
    resp = client.delete(f"/api/v1/workflows/runs/{run_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json["deleted"] == run_id

    # Confirm gone
    resp2 = client.get("/api/v1/workflows/runs/all", headers=admin_headers)
    ids = [r["id"] for r in resp2.json]
    assert run_id not in ids


def test_delete_single_run_not_found(client, admin_headers):
    resp = client.delete("/api/v1/workflows/runs/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404


def test_bulk_delete_runs(client, admin_headers):
    id1 = _seed_run(status="done")
    id2 = _seed_run(status="failed")
    id3 = _seed_run(status="done")

    resp = client.delete(
        "/api/v1/workflows/runs",
        json={"ids": [id1, id2]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json["deleted"] == 2

    # id3 survives
    resp2 = client.get("/api/v1/workflows/runs/all", headers=admin_headers)
    remaining_ids = [r["id"] for r in resp2.json]
    assert id1 not in remaining_ids
    assert id2 not in remaining_ids
    assert id3 in remaining_ids


def test_bulk_delete_runs_empty_ids(client, admin_headers):
    resp = client.delete("/api/v1/workflows/runs", json={"ids": []}, headers=admin_headers)
    assert resp.status_code == 400


def test_bulk_delete_runs_exceeds_limit(client, admin_headers):
    fake_ids = [f"fake-id-{i}" for i in range(201)]
    resp = client.delete("/api/v1/workflows/runs", json={"ids": fake_ids}, headers=admin_headers)
    assert resp.status_code == 422


def test_bulk_delete_select_failed(client, admin_headers):
    """Simulate the UI 'Select failed' → bulk delete flow."""
    failed1 = _seed_run(status="failed")
    failed2 = _seed_run(status="failed")
    done1 = _seed_run(status="done")

    # Get all runs, filter failed (as the UI does)
    resp = client.get("/api/v1/workflows/runs/all", headers=admin_headers)
    failed_ids = [r["id"] for r in resp.json if r.get("status") == "failed"]
    assert failed1 in failed_ids
    assert failed2 in failed_ids

    # Bulk delete the failed ones
    del_resp = client.delete(
        "/api/v1/workflows/runs",
        json={"ids": failed_ids},
        headers=admin_headers,
    )
    assert del_resp.status_code == 200

    # Done run untouched
    resp2 = client.get("/api/v1/workflows/runs/all", headers=admin_headers)
    surviving = [r["id"] for r in resp2.json]
    assert done1 in surviving
    assert failed1 not in surviving
    assert failed2 not in surviving


# ── Webhook ───────────────────────────────────────────────────────────────────

def test_webhook_trigger_no_secret(client, admin_headers):
    """Workflow with webhook disabled or missing secret must reject."""
    _db_seed_workflow(name="hook-wf")
    resp = client.post("/api/v1/workflows/hook-wf/trigger", json={"data": "test"})
    assert resp.status_code in (400, 403, 404)


def test_webhook_oversized_body(client, admin_headers):
    """Body >64KB must be rejected."""
    _db_seed_workflow(name="big-wf")
    big_payload = {"data": "x" * (65 * 1024)}
    resp = client.post(
        "/api/v1/workflows/big-wf/trigger",
        json=big_payload,
        headers={"X-Webhook-Secret": "some-secret"},
    )
    assert resp.status_code in (400, 403, 413)
