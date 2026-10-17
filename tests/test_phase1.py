"""Phase 1 smoke tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_loads():
    from core.config import get_settings
    s = get_settings()
    assert s.CLAUDEOS_VERSION == "1.0.0"
    assert s.FLASK_PORT == 5000


def test_db_migration():
    from core.config import get_settings
    from scripts.migrate import run_all
    run_all()
    from core.database import get_db
    with get_db() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {"memory_entries", "agents", "workflows", "namespaces", "outputs", "system_events", "api_keys"}
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_flask_health(tmp_path):
    from core.api.app import create_app
    app = create_app()
    client = app.test_client()
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_flask_system_status(client, auth_headers):
    r = client.get("/api/v1/system/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert "services" in data
    assert data["services"]["database"]["status"] == "ok"


def test_flask_stats(client, auth_headers):
    r = client.get("/api/v1/system/stats", headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert "counts" in data
    assert "memory_entries" in data["counts"]
