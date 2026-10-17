"""Shared pytest fixtures for ClaudeOS test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Isolated SQLite + ChromaDB per test. Runs all migrations."""
    import core.config as cfg_module
    import core.database as db_module

    db_path = tmp_path / "test.db"
    chroma_path = tmp_path / "chromadb"
    chroma_path.mkdir()

    cfg_module._settings = None
    db_module._local.__dict__.clear()

    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("CHROMADB_PATH", str(chroma_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32-chars-long!!!!")

    cfg_module._settings = None

    from scripts.migrate import run_all
    run_all()

    yield

    cfg_module._settings = None
    db_module._local.__dict__.clear()
    import memory.vector_store as vs
    vs._client = None
    vs._ef = None
    try:
        import agents.executor as ex
        ex._client = None
    except Exception:
        pass


@pytest.fixture()
def app(fresh_db):
    """Flask test app with scheduler disabled."""
    from unittest.mock import patch
    with patch("workflows.scheduler.init_scheduler"), \
         patch("workflows.scheduler.shutdown_scheduler"):
        from core.api.app import create_app
        application = create_app()
        application.config["TESTING"] = True
        yield application


@pytest.fixture()
def client(app):
    """Flask test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture()
def admin_token(client):
    """Create admin user and return JWT access token."""
    from core.auth import create_user
    create_user("admin", "Admin1234!", role="admin", namespace=None)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin1234!"})
    assert resp.status_code == 200, resp.json
    return resp.json["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    """Authorization header dict for admin."""
    return {"Authorization": f"Bearer {admin_token}"}
