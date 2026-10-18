"""Memory role policy and namespace isolation at the API boundary."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask, g
from werkzeug.exceptions import Forbidden


@pytest.fixture
def memory_access(monkeypatch):
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "memory-authorization-test-secret-32-characters!")


@pytest.fixture
def memory_client(memory_access, fresh_db, monkeypatch, tmp_path):
    from core.api.routes.memory import memory_bp
    from core.auth import create_access_token, create_user
    from memory import engine, store, vector_store
    from memory.schemas import MemoryEntryCreate
    from vault import manager
    from vault.schemas import NamespaceCreate

    monkeypatch.setattr(manager, "VAULT_ROOT", tmp_path / "vault")
    entries = []
    for slug in ("ns-a", "ns-b"):
        manager.create_namespace(NamespaceCreate(slug=slug, display_name=slug, type="client"))
        entries.append(store.write(MemoryEntryCreate(namespace=slug, key="secret", value=f"private {slug}")))
    for name in ("upsert", "delete", "delete_bulk"):
        monkeypatch.setattr(vector_store, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "_context_cache", {})

    def headers(role, namespace=None):
        user = create_user("memory_user", "MemoryUser123!", role=role, namespace=namespace)
        token = create_access_token(user["id"], user["username"], role, namespace)
        return {"Authorization": f"Bearer {token}"}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(memory_bp)
    with ThreadPoolExecutor(max_workers=2) as pool, app.test_client() as client:
        monkeypatch.setattr(engine, "_bg_pool", pool)
        yield client, entries, headers


def _requests(entry_id):
    return [
        ("GET", "", None),
        ("GET", "?namespace=ns-b", None),
        ("GET", f"/{entry_id}", None),
        ("GET", "/namespaces", None),
        ("GET", "/context/ns-b", None),
        ("GET", "/hybrid-search?q=private&namespace=ns-b", None),
        ("POST", "/search", {"query": "private", "namespace": "ns-b", "mode": "text"}),
        ("POST", "", {"namespace": "ns-b", "key": "secret", "value": "injected"}),
        ("PUT", f"/{entry_id}", {"value": "injected"}),
        ("DELETE", f"/{entry_id}", None),
        ("DELETE", "/bulk", {"ids": [entry_id]}),
        ("POST", "/import", None),
        ("DELETE", "/expire", None),
        ("POST", "/consolidate", None),
        ("GET", "?limit=invalid", None),
        ("POST", "/search", None),
        ("PUT", f"/{entry_id}", None),
    ]


@pytest.mark.parametrize("role, namespace", [("staff", None), ("staff", "ns-a"), ("unknown", None)])
def test_unsupported_roles_never_reach_memory(memory_client, monkeypatch, role, namespace):
    from core.database import get_db
    from memory import engine

    client, entries, make_headers = memory_client
    headers = make_headers(role, namespace)

    def forbidden_storage(*args, **kwargs):
        pytest.fail("Unauthorized memory request reached storage")

    for name in ("list_entries", "get_by_id", "namespace_counts", "get_agent_context",
                 "search", "write", "update", "delete", "expire_stale"):
        monkeypatch.setattr(engine, name, forbidden_storage)
    # Bulk deletion queries SQLite directly, bypassing the engine facade.
    statements = []
    with get_db() as conn:
        conn.set_trace_callback(statements.append)
        try:
            for method, path, body in _requests(entries[1].id):
                response = client.open(f"/api/v1/memory{path}", method=method, headers=headers, json=body)
                assert response.status_code == 403, (method, path, response.json)
        finally:
            conn.set_trace_callback(None)
    assert not any("memory_entries" in sql.lower() for sql in statements)


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer"])
def test_memory_read_permissions(memory_client, role):
    client, entries, make_headers = memory_client
    scoped = role in ("client", "viewer")
    headers = make_headers(role, "ns-a" if scoped else None)
    expected = {entries[0].id} if scoped else {e.id for e in entries}
    listing = client.get("/api/v1/memory", headers=headers)
    assert listing.status_code == 200
    assert {e["id"] for e in listing.json["entries"]} == expected
    filtered = client.get("/api/v1/memory?namespace=ns-b", headers=headers)
    assert {e["id"] for e in filtered.json["entries"]} == {entries[0 if scoped else 1].id}
    counts = client.get("/api/v1/memory/namespaces", headers=headers)
    assert counts.json["namespaces"] == ({"ns-a": 1} if scoped else {"ns-a": 1, "ns-b": 1})
    search = client.post("/api/v1/memory/search", headers=headers, json={"query": "private", "mode": "text"})
    assert search.status_code == 200
    assert {e["id"] for e in search.json["results"]} == expected
    for entry in entries:
        allowed = entry.id in expected
        response = client.get(f"/api/v1/memory/{entry.id}", headers=headers)
        assert response.status_code == (200 if allowed else 404)
        context = client.get(f"/api/v1/memory/context/{entry.namespace}", headers=headers)
        assert context.status_code == (200 if allowed else 404)
        if allowed:
            assert entry.value in context.json["context"]


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer"])
def test_memory_write_permissions(memory_client, role):
    from memory import store

    client, entries, make_headers = memory_client
    headers = make_headers(role, "ns-a" if role in ("client", "viewer") else None)
    if role == "viewer":
        for method, path, body in _requests(entries[0].id):
            if method in ("PUT", "DELETE") or (method == "POST" and path != "/search"):
                assert client.open(f"/api/v1/memory{path}", method=method, headers=headers, json=body).status_code == 403
        assert [store.get_by_id(e.id).value for e in entries] == [e.value for e in entries]
        return

    created = client.post("/api/v1/memory", headers=headers,
                          json={"namespace": "ns-b", "key": "new", "value": "new"})
    assert created.status_code == 201
    assert created.json["namespace"] == ("ns-a" if role == "client" else "ns-b")
    path = f"/api/v1/memory/{created.json['id']}"
    updated = client.put(path, headers=headers, json={"value": "updated"})
    assert updated.status_code == 200 and updated.json["value"] == "updated"
    assert client.delete(path, headers=headers).status_code == 200
    if role == "client":
        foreign = f"/api/v1/memory/{entries[1].id}"
        assert client.put(foreign, headers=headers, json={"value": "injected"}).status_code == 404
        assert client.delete(foreign, headers=headers).status_code == 404
    deleted = client.delete("/api/v1/memory/bulk", headers=headers, json={"ids": [e.id for e in entries]})
    assert deleted.status_code == 200
    assert set(deleted.json["deleted"]) == ({entries[0].id} if role == "client" else {e.id for e in entries})
    if role == "client":
        assert store.get_by_id(entries[1].id).value == entries[1].value


@pytest.mark.parametrize("namespace", ["global", "ns-a"])
@pytest.mark.parametrize("permissions", [["read"], ["read", "write"]])
def test_memory_api_key_permissions(memory_client, namespace, permissions):
    from core.api.auth import create_api_key

    client, entries, _ = memory_client
    raw_key, _ = create_api_key("memory-key", permissions=permissions, namespace=namespace)
    headers = {"X-API-Key": raw_key}
    listing = client.get("/api/v1/memory?namespace=ns-b", headers=headers)
    assert listing.status_code == 200
    assert {e["id"] for e in listing.json["entries"]} == {entries[0 if namespace == "ns-a" else 1].id}
    created = client.post("/api/v1/memory", headers=headers,
                          json={"namespace": "ns-b", "key": "new", "value": "new"})
    assert created.status_code == (201 if "write" in permissions else 403)
    if "write" in permissions:
        assert created.json["namespace"] == ("ns-a" if namespace == "ns-a" else "ns-b")


def test_staff_keeps_assigned_ticket_access(memory_client):
    from core.api.auth import create_api_key
    from core.api.routes.tickets import tickets_bp

    client, _, make_headers = memory_client
    client.application.register_blueprint(tickets_bp)
    staff = make_headers("staff")
    raw_key, _ = create_api_key("ticket-operator")
    operator = {"X-API-Key": raw_key}
    tickets = []
    for namespace in ("ns-a", "ns-b"):
        response = client.post("/api/v1/tickets", headers=operator, json={
            "namespace": namespace, "title": "Ticket", "description": "Help",
        })
        assert response.status_code == 201
        tickets.append(response.json["id"])
    assigned = f"/api/v1/tickets/{tickets[0]}"
    assert client.post(f"{assigned}/assignees", headers=operator,
                       json={"usernames": ["memory_user"]}).status_code == 200
    assert {t["id"] for t in client.get("/api/v1/tickets", headers=staff).json} == {tickets[0]}
    assert client.get(assigned, headers=staff).status_code == 200
    assert client.patch(assigned, headers=staff, json={"status": "work_in_progress"}).status_code == 200
    assert client.get(f"/api/v1/tickets/{tickets[1]}", headers=staff).status_code == 403
    assert client.get("/api/v1/memory", headers=staff).status_code == 403


@pytest.mark.parametrize("role", ["staff", "unknown", None])
def test_namespace_helpers_deny_unsupported_roles(role):
    from core.auth import can_access_namespace, effective_namespace

    with Flask(__name__).test_request_context():
        if role is not None:
            g.user_role = role
        g.user_namespace = "ns-a"
        for namespace in (None, "ns-a", "ns-b"):
            assert not can_access_namespace(namespace)
            with pytest.raises(Forbidden):
                effective_namespace(namespace)


@pytest.mark.parametrize("role", ["client", "viewer"])
def test_namespace_helpers_deny_missing_namespace(role):
    from core.auth import can_access_namespace, effective_namespace

    with Flask(__name__).test_request_context():
        g.user_role = role
        g.user_namespace = None
        assert not can_access_namespace("ns-b")
        with pytest.raises(Forbidden):
            effective_namespace("ns-b")
