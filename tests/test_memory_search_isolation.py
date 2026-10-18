"""Semantic search must authorize vector hits against SQLite namespaces."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask


@pytest.fixture
def memory_env(monkeypatch):
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "memory-search-test-secret-32-characters!")


@pytest.fixture
def search_data(memory_env, fresh_db, monkeypatch, tmp_path):
    from memory import engine, retriever, store, vector_store
    from memory.schemas import MemoryEntryCreate
    from vault import manager
    from vault.schemas import NamespaceCreate

    monkeypatch.setattr(manager, "VAULT_ROOT", tmp_path / "vault")
    for slug in ("ns-a", "ns_a"):
        manager.create_namespace(NamespaceCreate(slug=slug, display_name=slug))

    def write(namespace, key, **kwargs):
        return store.write(MemoryEntryCreate(
            namespace=namespace, key=key, value=f"private {namespace}", **kwargs,
        ))

    own = write("ns-a", "first")
    second = write("ns-a", "second")
    foreign = write("ns_a", "foreign")
    low = write("ns-a", "low", confidence=0.1)
    expired = write("ns-a", "expired", expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    # A colliding/stale index may return foreign IDs, even with misleading metadata.
    hits = [{"memory_id": e.id, "metadata": {"namespace": "ns-a"}}
            for e in (foreign, second, low, expired, own)]
    hits.append({"memory_id": "missing", "metadata": {}})
    monkeypatch.setattr(vector_store, "search", lambda *args, **kwargs: hits)
    # Worker connections and the BM25 cache must not outlive this test's database.
    monkeypatch.setattr(retriever, "_bm25_cache", {})
    with ThreadPoolExecutor(max_workers=2) as search_pool, \
         ThreadPoolExecutor(max_workers=2) as retriever_pool:
        monkeypatch.setattr(engine, "_search_pool", search_pool)
        monkeypatch.setattr(retriever, "_RETRIEVER_POOL", retriever_pool)
        yield own, second, foreign, hits


def test_semantic_search_filters_namespace_and_preserves_rank(search_data):
    from memory import engine

    own, second, foreign, _ = search_data
    results = engine.search_semantic("unmatched", "ns-a", top_k=10, min_confidence=0.8)
    assert [e.id for e in results] == [second.id, own.id]
    # Namespace equality must work in both directions for colliding collection names.
    assert [e.id for e in engine.search_semantic("unmatched", "ns_a")] == [foreign.id]


@pytest.mark.parametrize("foreign_only", [True, False])
def test_semantic_search_without_authorized_hits_returns_empty(search_data, foreign_only):
    from memory import engine

    _, _, _, hits = search_data
    hits[:] = hits[:1] if foreign_only else []
    assert engine.search_semantic("unmatched", "ns-a") == []


@pytest.mark.parametrize("role", ["client", "viewer", "api_key"])
@pytest.mark.parametrize("mode", ["semantic", "both", "hybrid"])
def test_scoped_search_never_returns_foreign_vector_hits(search_data, role, mode):
    from core.api.routes.memory import memory_bp
    from core.auth import create_access_token, create_user

    own, second, _, _ = search_data
    if role == "api_key":
        from core.api.auth import create_api_key
        raw_key, _ = create_api_key("search-key", namespace="ns-a", permissions=["read", "write"])
        headers = {"X-API-Key": raw_key}
    else:
        user = create_user("search_user", "SearchUser123!", role=role, namespace="ns-a")
        token = create_access_token(user["id"], user["username"], role, "ns-a")
        headers = {"Authorization": f"Bearer {token}"}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(memory_bp)
    with app.test_client() as client:
        if mode == "hybrid":
            response = client.get("/api/v1/memory/hybrid-search", headers=headers, query_string={
                "q": "unmatched", "namespace": "ns_a", "top_k": 10,
            })
        else:
            response = client.post("/api/v1/memory/search", headers=headers, json={
                "query": "unmatched", "namespace": "ns_a", "mode": mode,
                "top_k": 10, "min_confidence": 0.8,
            })
    assert response.status_code == 200, response.json
    assert response.json["namespace"] == "ns-a"
    results = response.json["results"]
    assert all(e["namespace"] == "ns-a" for e in results)
    assert {own.id, second.id} <= {e["id"] for e in results}
