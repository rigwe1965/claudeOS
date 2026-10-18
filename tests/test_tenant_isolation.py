"""Regression tests: client/viewer tenant isolation (security audit fixes)."""
import pytest


def _login(client, name, pw):
    r = client.post("/api/v1/auth/login", json={"username": name, "password": pw})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.json['access_token']}"}


@pytest.fixture
def tenants(client, app):
    from core.auth import create_user
    from vault.manager import create_namespace
    from vault.schemas import NamespaceCreate
    for slug in ("ns-a", "ns-b"):
        create_namespace(NamespaceCreate(slug=slug, display_name=slug, type="client"))
    create_user("client_a", "ClientA1234!", role="client", namespace="ns-a")
    create_user("viewer_a", "ViewerA1234!", role="viewer", namespace="ns-a")
    create_user("orphan", "Orphan12345!", role="client", namespace=None)
    from outputs.manager import save
    other = save(namespace="ns-b", title="secret", content="b-only")
    own = save(namespace="ns-a", title="mine", content="a-only")
    return {
        "a": _login(client, "client_a", "ClientA1234!"),
        "v": _login(client, "viewer_a", "ViewerA1234!"),
        "orphan_login": client.post("/api/v1/auth/login",
                                    json={"username": "orphan", "password": "Orphan12345!"}),
        "other": other, "own": own,
    }


def test_orphan_client_is_rejected(client, tenants):
    tok = tenants["orphan_login"].json["access_token"]
    r = client.get("/api/v1/outputs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_client_cannot_read_or_delete_other_output(client, tenants):
    oid = tenants["other"].id
    assert client.get(f"/api/v1/outputs/{oid}", headers=tenants["a"]).status_code == 404
    r = client.delete("/api/v1/outputs/bulk", json={"ids": [oid]}, headers=tenants["a"])
    assert r.json["deleted"] == [] and oid in r.json["failed"]


def test_client_save_forced_into_own_namespace(client, tenants):
    r = client.post("/api/v1/outputs", json={"namespace": "ns-b", "title": "x", "content": "y"},
                    headers=tenants["a"])
    assert r.status_code == 201 and r.json["namespace"] == "ns-a"


def test_viewer_is_read_only(client, tenants):
    r = client.post("/api/v1/outputs", json={"title": "x", "content": "y"}, headers=tenants["v"])
    assert r.status_code == 403
    r = client.delete(f"/api/v1/outputs/{tenants['own'].id}", headers=tenants["v"])
    assert r.status_code == 403


def test_client_blocked_from_sync_and_stats_all(client, tenants):
    assert client.get("/api/v1/sync/status", headers=tenants["a"]).status_code == 403
    assert client.post("/api/v1/sync/push", headers=tenants["a"]).status_code == 403
    assert client.get("/api/v1/outputs/stats/all", headers=tenants["a"]).status_code == 403


def test_client_cannot_touch_other_vault(client, tenants):
    h = tenants["a"]
    assert client.get("/api/v1/namespaces/ns-b/context", headers=h).status_code == 404
    r = client.post("/api/v1/namespaces/ns-b/context",
                    json={"filename": "x.md", "content": "inj"}, headers=h)
    assert r.status_code in (403, 404)
    assert client.delete("/api/v1/projects/anything", headers=h).status_code == 403


def test_agent_run_namespace_forced(client, tenants, monkeypatch):
    seen = {}
    from agents import dispatcher
    monkeypatch.setattr(dispatcher, "dispatch",
                        lambda name, req, block=False: seen.setdefault("ns", req.namespace) and "rid")
    client.post("/api/v1/agents/any/run", json={"prompt": "hi", "namespace": "ns-b"},
                headers=tenants["a"])
    assert seen.get("ns") == "ns-a"


def test_admin_cannot_create_namespaceless_client(client, admin_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/api/v1/admin/users", json={"username": "nsless", "password": "Nsless12345!",
                                                  "role": "client"}, headers=admin_headers)
    assert r.status_code == 422


# ── workflows / SSRF / dashboard session ─────────────────────────────────────

def test_client_cannot_run_workflows_or_see_scheduler(client, tenants):
    h = tenants["a"]
    assert client.post("/api/v1/workflows/anything/run", headers=h, json={}).status_code == 403
    assert client.get("/api/v1/workflows/scheduler/jobs", headers=h).status_code == 403


def test_ssrf_blocks_private_addresses():
    from core.tools.web_search import fetch_page
    for u in ("http://127.0.0.1:5000/api/v1/health", "http://169.254.169.254/latest/meta-data/",
              "http://[::1]/", "http://10.0.0.1/", "http://localhost/"):
        assert fetch_page(u).startswith("Blocked URL"), u


def test_dashboard_session_stores_no_tokens_and_remints(client, app):
    from core.auth import create_user
    from core.database import get_db
    create_user("sess_u", "SessUser1234!", role="operator", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "sess_u", "password": "SessUser1234!"})
    h = {"Authorization": f"Bearer {r.json['access_token']}"}
    # a stranger's refresh token must not be accepted
    assert client.post("/api/v1/auth/session", headers=h, json={"refresh_token": "bogus"}).status_code == 401
    key = client.post("/api/v1/auth/session", headers=h,
                      json={"refresh_token": r.json["refresh_token"]}).json["session_key"]
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM dashboard_sessions").fetchall()
    assert all(row["session_key"] != key and not row["access_token"] and not row["refresh_token"] for row in rows)
    got = client.get(f"/api/v1/auth/session/{key}")
    assert got.status_code == 200 and got.json["refresh_token"] != r.json["refresh_token"]


def test_deactivation_and_role_change_take_effect_immediately(client, admin_token):
    from core.auth import create_user
    adm = {"Authorization": f"Bearer {admin_token}"}
    u = create_user("victim", "Victim12345!", role="operator", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "victim", "password": "Victim12345!"})
    h = {"Authorization": f"Bearer {r.json['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    assert client.delete(f"/api/v1/admin/users/{u['id']}", headers=adm).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": r.json["refresh_token"]}).status_code == 401


def test_password_change_revokes_old_tokens_and_returns_new(client, app):
    from core.auth import create_user
    create_user("pwuser", "OldPass12345!", role="operator", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "pwuser", "password": "OldPass12345!"})
    old = {"Authorization": f"Bearer {r.json['access_token']}"}
    import time; time.sleep(1.1)
    c = client.post("/api/v1/auth/change-password", headers=old,
                    json={"current_password": "OldPass12345!", "new_password": "NewPass12345!"})
    assert c.status_code == 200
    assert client.get("/api/v1/auth/me", headers=old).status_code == 401
    new = {"Authorization": f"Bearer {c.json['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new).status_code == 200


def test_brand_validation_and_setting_bounds(client, admin_token):
    adm = {"Authorization": f"Bearer {admin_token}"}
    bad = client.post("/api/v1/namespaces", headers=adm,
                      json={"slug": "xss", "display_name": "X", "color": "red;}</style><script>"})
    assert bad.status_code == 422
    assert client.patch("/api/v1/admin/security-settings", headers=adm,
                        json={"lockout_minutes": "abc"}).status_code == 422
    assert client.patch("/api/v1/admin/security-settings", headers=adm,
                        json={"allow_self_register": "0"}).status_code == 200


def test_read_only_api_key_cannot_write(client, admin_token):
    adm = {"Authorization": f"Bearer {admin_token}"}
    k = client.post("/api/v1/admin/api-keys", headers=adm, json={"name": "ro", "permissions": ["read"]})
    key = {"X-API-Key": k.json["raw_key"]}
    assert client.get("/api/v1/memory", headers=key).status_code != 403
    assert client.post("/api/v1/memory", headers=key, json={"namespace": "x", "key": "k", "value": "v"}).status_code == 403


def test_login_does_not_reveal_account_state_without_password(client, admin_token):
    from core.auth import create_user
    adm = {"Authorization": f"Bearer {admin_token}"}
    u = create_user("gone", "Gone12345678!", role="operator", namespace=None)
    client.delete(f"/api/v1/admin/users/{u['id']}", headers=adm)
    assert client.post("/api/v1/auth/login", json={"username": "gone", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "gone", "password": "Gone12345678!"}).status_code == 403


def test_revoking_origin_session_kills_dashboard_handle(client, app):
    from core.auth import create_user, revoke_session, validate_refresh_token
    create_user("sess_r", "SessRevoke1234!", role="operator", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "sess_r", "password": "SessRevoke1234!"})
    h = {"Authorization": f"Bearer {r.json['access_token']}"}
    key = client.post("/api/v1/auth/session", headers=h,
                      json={"refresh_token": r.json["refresh_token"]}).json["session_key"]
    revoke_session(validate_refresh_token(r.json["refresh_token"])["id"])
    assert client.get(f"/api/v1/auth/session/{key}").status_code == 404


def test_staff_has_no_output_access(client, tenants):
    from core.auth import create_user
    create_user("staff_u", "StaffUser1234!", role="staff", namespace=None)
    h = _login(client, "staff_u", "StaffUser1234!")
    oid = tenants["other"].id
    assert client.get("/api/v1/outputs", headers=h).status_code == 403
    assert client.get(f"/api/v1/outputs/{oid}", headers=h).status_code == 403
    assert client.get(f"/api/v1/outputs/{oid}/content", headers=h).status_code == 403
    assert client.delete(f"/api/v1/outputs/{oid}", headers=h).status_code == 403
    assert client.post("/api/v1/outputs", headers=h, json={"namespace": "ns-b", "title": "x", "content": "y"}).status_code == 403
    assert client.get("/api/v1/outputs/search?q=b", headers=h).status_code == 403


def test_staff_has_no_workflow_access(client, tenants):
    from core.auth import create_user
    create_user("staff_w", "StaffWork1234!", role="staff", namespace=None)
    h = _login(client, "staff_w", "StaffWork1234!")
    for path in ("/api/v1/workflows", "/api/v1/workflows/runs/all", "/api/v1/workflows/runs/nope",
                 "/api/v1/workflows/anything", "/api/v1/workflows/anything/runs"):
        assert client.get(path, headers=h).status_code == 403, path


def test_staff_has_no_vault_access(client, tenants):
    from core.auth import create_user
    create_user("staff_v", "StaffVault1234!", role="staff", namespace=None)
    h = _login(client, "staff_v", "StaffVault1234!")
    for path in ("/api/v1/namespaces", "/api/v1/namespaces/ns-b", "/api/v1/namespaces/ns-b/workspace",
                 "/api/v1/namespaces/ns-b/context", "/api/v1/projects", "/api/v1/projects/anything"):
        assert client.get(path, headers=h).status_code == 403, path


def test_get_output_tool_does_not_reveal_foreign_namespace(client, tenants):
    from core.tools.system_tools import _get_output
    foreign = _get_output(tenants["other"].id, "ns-a")
    missing = _get_output("no-such-id", "ns-a")
    assert "ns-b" not in foreign and "belongs" not in foreign
    assert foreign.replace(tenants["other"].id, "X") == missing.replace("no-such-id", "X")
