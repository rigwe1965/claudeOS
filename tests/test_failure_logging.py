"""Failure audit details must stay inside their originating namespace."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask


@pytest.fixture
def failure_env(monkeypatch):
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "failure-logging-test-secret-32-characters!")


@pytest.fixture
def failure_data(failure_env, fresh_db, monkeypatch):
    from agents import executor
    from core.database import get_db
    from memory import context_builder, engine, store
    from memory.schemas import MemoryEntryCreate

    with get_db() as conn:
        for namespace in ("ns-a", "ns-b"):
            conn.execute(
                "INSERT INTO namespaces (id, slug, display_name) VALUES (?, ?, ?)",
                (namespace, namespace, namespace),
            )
    store.write(MemoryEntryCreate(key="shared-policy", value="Intentionally shared policy"))
    monkeypatch.setattr(engine, "_context_cache", {})
    monkeypatch.setattr(context_builder, "_ns_summary_cache", {})
    monkeypatch.setattr(context_builder, "_recent_cache", {})
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(executor, "_ctx_pool", pool)
        yield


def test_failure_inserts_and_appends_stay_in_originating_namespace(failure_data):
    from agents.executor import _log_failure_to_memory
    from core.database import get_db

    _log_failure_to_memory("agent-a", "ns-a", "private-a-first", "run-a-first")
    _log_failure_to_memory("agent-b", "ns-b", "private-b", "run-b-first")
    _log_failure_to_memory("agent-a", "ns-a", "private-a-second", "run-a-second")

    with get_db() as conn:
        rows = conn.execute("SELECT namespace, value FROM memory_entries WHERE key='error_log'").fetchall()
    logs = {row["namespace"]: row["value"] for row in rows}
    assert len(rows) == 2
    assert set(logs) == {"ns-a", "ns-b"}
    assert "private-a-first" in logs["ns-a"] and "private-a-second" in logs["ns-a"]
    assert "private-b" not in logs["ns-a"]
    assert "private-b" in logs["ns-b"] and "private-a" not in logs["ns-b"]
    assert "agent-a (ns=ns-a, run=run-a-fi)" in logs["ns-a"]


@pytest.mark.parametrize("role", ["client", "viewer", "api_key"])
def test_authorized_context_does_not_disclose_other_tenant_failures(failure_data, role):
    from agents.executor import _log_failure_to_memory
    from core.api.routes.memory import memory_bp
    from core.auth import create_access_token, create_user

    _log_failure_to_memory("agent-b", "ns-b", "private-b", "run-b-first")
    _log_failure_to_memory("agent-a", "ns-a", "private-a", "run-a-first")
    if role == "api_key":
        from core.api.auth import create_api_key
        raw_key, _ = create_api_key("failure-key", namespace="ns-a", permissions=["read"])
        headers = {"X-API-Key": raw_key}
    else:
        user = create_user("failure_user", "FailureUser123!", role=role, namespace="ns-a")
        token = create_access_token(user["id"], user["username"], role, "ns-a")
        headers = {"Authorization": f"Bearer {token}"}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(memory_bp)
    with app.test_client() as client:
        response = client.get("/api/v1/memory/context/ns-a", headers=headers)
        assert response.status_code == 200
        context = response.json["context"]
        assert "private-a" in context
        assert "private-b" not in context
        assert "Intentionally shared policy" in context
        assert client.get("/api/v1/memory/context/ns-b", headers=headers).status_code == 404


@pytest.mark.parametrize("reader", ["flat", "tiered", "fallback"])
def test_legacy_global_error_log_is_excluded_from_shared_context(failure_data, monkeypatch, reader):
    from agents import executor
    from memory import context_builder, engine, store
    from memory.schemas import MemoryEntryCreate

    store.write(MemoryEntryCreate(
        key="error_log", category="context", value="legacy-private-b", confidence=0.9,
    ))
    if reader == "flat":
        context = engine.get_agent_context("ns-a", min_confidence=0)
    elif reader == "tiered":
        context = context_builder.build_context("ns-a", "hi")
    else:
        def unavailable(*args, **kwargs):
            raise RuntimeError("context builder unavailable")
        monkeypatch.setattr(context_builder, "build_context", unavailable)
        context = executor._build_memory_context("ns-a", "hi")
        assert context.startswith(executor._CTX_DEG_PREFIX)

    assert "Intentionally shared policy" in context
    assert "legacy-private-b" not in context


def test_legacy_global_error_log_is_not_consolidated_into_shared_memory(failure_data, monkeypatch):
    from core.database import get_db
    from memory import consolidator, store
    from memory.schemas import MemoryEntryCreate

    for key in ("error_log", "one", "two", "three", "four"):
        store.write(MemoryEntryCreate(key=key, category="context", value="legacy details"))
    with get_db() as conn:
        conn.execute("UPDATE memory_entries SET created_at=datetime('now', '-2 days')")

    seen = []

    def capture_clusters(entries):
        seen.extend(e["key"] for e in entries)
        return []

    monkeypatch.setattr(consolidator, "_cluster_entries", capture_clusters)
    consolidator.run_consolidation(namespace="global", dry_run=True)
    assert "error_log" not in seen
    assert {"one", "two", "three", "four"} <= set(seen)
