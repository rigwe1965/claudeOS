"""Phase 2 — Memory Engine tests."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory-like DB in a temp dir."""
    import core.config as cfg_module
    import core.database as db_module

    db_path = tmp_path / "test.db"
    chroma_path = tmp_path / "chromadb"
    chroma_path.mkdir()

    # Reset singletons
    cfg_module._settings = None
    db_module._local.__dict__.clear()

    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("CHROMADB_PATH", str(chroma_path))
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "test-secret-key-for-pytest-only!")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    cfg_module._settings = None

    from scripts.migrate import run_all
    run_all()

    yield

    cfg_module._settings = None
    db_module._local.__dict__.clear()
    import memory.vector_store as vs
    vs._client = None
    vs._ef = None


# ── store ──────────────────────────────────────────────────────────────────

def test_write_and_get():
    from memory import engine
    e = engine.write("global", "fact", "brand.color", "#407E3C")
    assert e.id
    assert e.key == "brand.color"
    assert e.value == "#407E3C"


def test_upsert_same_key():
    from memory import engine
    e1 = engine.write("global", "fact", "test.key", "v1")
    e2 = engine.write("global", "fact", "test.key", "v2")
    assert e1.id == e2.id
    assert e2.value == "v2"


def test_get_by_key():
    from memory import engine
    engine.write("global", "fact", "user.name", "Rigwe")
    result = engine.get("global", "user.name")
    assert result is not None
    assert result.value == "Rigwe"


def test_get_missing_key():
    from memory import engine
    result = engine.get("global", "does.not.exist")
    assert result is None


def test_namespace_isolation():
    from memory import engine
    engine.write("reci-transport", "fact", "fleet.size", "50")
    engine.write("ivycandy-hair", "fact", "fleet.size", "0")
    reci = engine.get("reci-transport", "fleet.size")
    ivy = engine.get("ivycandy-hair", "fleet.size")
    assert reci.value == "50"
    assert ivy.value == "0"


def test_list_entries():
    from memory import engine
    engine.write("global", "fact", "k1", "v1")
    engine.write("global", "preference", "k2", "v2")
    engine.write("reci-transport", "fact", "k3", "v3")

    all_entries = engine.list_entries()
    assert len(all_entries) >= 3

    global_entries = engine.list_entries(namespace="global")
    assert all(e.namespace == "global" for e in global_entries)

    pref_entries = engine.list_entries(category="preference")
    assert all(e.category == "preference" for e in pref_entries)


def test_delete():
    from memory import engine
    e = engine.write("global", "fact", "delete.me", "gone")
    assert engine.delete(e.id)
    assert engine.get_by_id(e.id) is None


def test_text_search():
    from memory import engine
    engine.write("global", "fact", "brand.primary_color", "#407E3C green")
    engine.write("global", "fact", "brand.secondary", "white")
    results = engine.search_text("green", namespace="global")
    assert any("green" in e.value for e in results)


def test_confidence_filter():
    from memory import engine
    engine.write("global", "fact", "high.confidence", "hi", confidence=0.95)
    engine.write("global", "fact", "low.confidence", "lo", confidence=0.3)
    entries = engine.list_entries(namespace="global", min_confidence=0.9)
    keys = [e.key for e in entries]
    assert "high.confidence" in keys
    assert "low.confidence" not in keys


def test_expire_stale():
    from memory import engine
    from datetime import datetime, timezone, timedelta
    e = engine.write(
        "global", "context", "stale.entry", "old",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    expired = engine.expire_stale()
    assert expired >= 1
    assert engine.get_by_id(e.id) is None


def test_namespace_counts():
    from memory import engine
    engine.write("global", "fact", "nc1", "v1")
    engine.write("global", "fact", "nc2", "v2")
    engine.write("ns-x", "fact", "nc3", "v3")
    counts = engine.namespace_counts()
    assert counts.get("global", 0) >= 2
    assert counts.get("ns-x", 0) >= 1


def test_agent_context_string():
    from memory import engine
    engine.write("global", "fact", "brand.color", "#407E3C", confidence=0.95)
    ctx = engine.get_agent_context("global", min_confidence=0.9)
    assert "#407E3C" in ctx
    assert "ClaudeOS Memory Context" in ctx


# ── API routes ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from unittest.mock import patch
    from core.api.app import create_app
    with patch("workflows.scheduler.init_scheduler"), patch("workflows.scheduler.shutdown_scheduler"):
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c


@pytest.fixture
def auth_headers(client):
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    return {"Authorization": f"Bearer {resp.json['access_token']}"}


def test_api_write_and_list(client, auth_headers):
    r = client.post("/api/v1/memory", json={
        "namespace": "global",
        "category": "fact",
        "key": "api.test",
        "value": "hello from API",
    }, headers=auth_headers)
    assert r.status_code == 201
    data = r.get_json()
    assert data["key"] == "api.test"

    r2 = client.get("/api/v1/memory?namespace=global", headers=auth_headers)
    assert r2.status_code == 200
    entries = r2.get_json()["entries"]
    assert any(e["key"] == "api.test" for e in entries)


def test_api_get_entry(client, auth_headers):
    r = client.post("/api/v1/memory", json={
        "key": "get.test", "value": "get me", "category": "fact"
    }, headers=auth_headers)
    entry_id = r.get_json()["id"]
    r2 = client.get(f"/api/v1/memory/{entry_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.get_json()["value"] == "get me"


def test_api_update(client, auth_headers):
    r = client.post("/api/v1/memory", json={"key": "upd.test", "value": "old", "category": "fact"}, headers=auth_headers)
    entry_id = r.get_json()["id"]
    r2 = client.put(f"/api/v1/memory/{entry_id}", json={"value": "new"}, headers=auth_headers)
    assert r2.status_code == 200
    assert r2.get_json()["value"] == "new"


def test_api_delete(client, auth_headers):
    r = client.post("/api/v1/memory", json={"key": "del.test", "value": "bye", "category": "fact"}, headers=auth_headers)
    entry_id = r.get_json()["id"]
    r2 = client.delete(f"/api/v1/memory/{entry_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert client.get(f"/api/v1/memory/{entry_id}", headers=auth_headers).status_code == 404


def test_api_search(client, auth_headers):
    client.post("/api/v1/memory", json={"key": "search.test", "value": "RECI Transport Nigeria", "category": "fact"}, headers=auth_headers)
    r = client.post("/api/v1/memory/search", json={
        "query": "RECI Transport",
        "mode": "text",
        "namespace": "global",
        "top_k": 5,
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] >= 1


def test_api_namespaces(client, auth_headers):
    client.post("/api/v1/memory", json={"key": "ns.test", "value": "v", "namespace": "reci-transport", "category": "fact"}, headers=auth_headers)
    r = client.get("/api/v1/memory/namespaces", headers=auth_headers)
    assert r.status_code == 200
    counts = r.get_json()["namespaces"]
    assert "reci-transport" in counts


def test_api_expire(client, auth_headers):
    r = client.delete("/api/v1/memory/expire", headers=auth_headers)
    assert r.status_code == 200
    assert "expired" in r.get_json()
