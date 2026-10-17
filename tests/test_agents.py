"""Phase 3 — Agent Registry + Dispatcher tests (no live Claude API calls)."""
import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
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
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "test-secret-key-for-pytest-only!")

    cfg_module._settings = None

    from scripts.migrate import run_all
    run_all()

    from agents.registry import seed_from_directory
    seed_from_directory()

    yield

    cfg_module._settings = None
    db_module._local.__dict__.clear()
    import memory.vector_store as vs
    vs._client = None
    vs._ef = None
    import agents.executor as ex
    ex._client = None


def _real_agent_id() -> str:
    from agents.registry import get_by_name
    return get_by_name("briefing-agent").id


# ── Registry ────────────────────────────────────────────────────────────────

def test_seed_loads_12_agents():
    from agents.registry import list_agents
    agents = list_agents(enabled_only=False)
    assert len(agents) == 12


def test_get_agent_by_name():
    from agents.registry import get_by_name
    a = get_by_name("briefing-agent")
    assert a is not None
    assert a.category == "ops"
    assert "Morning Briefing" in a.display_name


def test_get_agent_by_id():
    from agents.registry import get_by_name, get_by_id
    a = get_by_name("research-agent")
    a2 = get_by_id(a.id)
    assert a2 is not None
    assert a2.name == "research-agent"


def test_namespace_lock_on_transport_agent():
    from agents.registry import get_by_name
    a = get_by_name("transport-ops-agent")
    assert a.namespace_lock == "reci-transport"


def test_list_by_category():
    from agents.registry import list_agents
    ops = list_agents(category="ops")
    assert all(a.category == "ops" for a in ops)
    assert len(ops) >= 1


def test_upsert_updates_existing():
    from agents.registry import get_by_name, upsert
    a = get_by_name("qa-agent")
    a.description = "Updated description"
    upsert(a)
    a2 = get_by_name("qa-agent")
    assert a2.description == "Updated description"


def test_delete_agent():
    from agents.registry import get_by_name, delete
    a = get_by_name("scheduling-agent")
    assert delete(a.id)
    assert get_by_name("scheduling-agent") is None


# ── Executor (mocked Claude API) ─────────────────────────────────────────────

def _mock_response(text: str = "Test output from agent"):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    mock.model = "claude-sonnet-4-6"
    mock.stop_reason = "end_turn"
    mock.usage.input_tokens = 100
    mock.usage.output_tokens = 50
    return mock


def test_executor_creates_run_record():
    from agents.executor import create_run_record
    from agents.dispatcher import get_run
    agent_id = _real_agent_id()
    run_id = create_run_record(
        agent_id=agent_id,
        namespace="global",
        prompt="Test prompt",
        context={},
        session_id=None,
        triggered_by="test",
        workflow_run_id=None,
    )
    assert run_id
    run = get_run(run_id)
    assert run["status"] == "pending"


def test_executor_execute_success():
    from agents import executor
    agent_id = _real_agent_id()
    run_id = executor.create_run_record(
        agent_id=agent_id,
        namespace="global",
        prompt="Hello",
        context={},
        session_id=None,
        triggered_by="test",
        workflow_run_id=None,
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("Hello from agent")

    with patch.object(executor, "_get_client", return_value=mock_client):
        result = executor.execute(
            run_id=run_id,
            agent_name="briefing-agent",
            system_prompt="You are a test agent.",
            prompt="Hello",
            namespace="global",
            model="claude-sonnet-4-6",
            max_tokens=100,
            temperature=0.5,
            context={},
            session_id=None,
            triggered_by="test",
            workflow_run_id=None,
            save_output=False,
            agent_id=agent_id,
        )

    assert result["status"] == "done"
    assert result["output"]["text"] == "Hello from agent"
    assert result["tokens_in"] == 100
    assert result["tokens_out"] == 50


def test_executor_execute_failure():
    from agents import executor
    agent_id = _real_agent_id()
    run_id = executor.create_run_record(
        agent_id=agent_id,
        namespace="global",
        prompt="Hello",
        context={},
        session_id=None,
        triggered_by="test",
        workflow_run_id=None,
    )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    with patch.object(executor, "_get_client", return_value=mock_client):
        result = executor.execute(
            run_id=run_id,
            agent_name="briefing-agent",
            system_prompt="You are a test agent.",
            prompt="Hello",
            namespace="global",
            model="claude-sonnet-4-6",
            max_tokens=100,
            temperature=0.5,
            context={},
            session_id=None,
            triggered_by="test",
            workflow_run_id=None,
            save_output=False,
            agent_id=agent_id,
        )

    assert result["status"] == "failed"
    assert "API error" in result["error"]


# ── Dispatcher ────────────────────────────────────────────────────────────────

def test_dispatcher_dispatch_unknown_agent():
    from agents.dispatcher import dispatch
    from agents.schemas import AgentDispatchRequest
    with pytest.raises(ValueError, match="not found"):
        dispatch("nonexistent-agent", AgentDispatchRequest(prompt="test"))


def test_dispatcher_namespace_lock_enforced():
    from agents.dispatcher import dispatch
    from agents.schemas import AgentDispatchRequest
    with pytest.raises(PermissionError):
        dispatch(
            "transport-ops-agent",
            AgentDispatchRequest(prompt="test", namespace="global"),
            block=True,
        )


def test_dispatcher_dispatch_returns_run_id():
    from agents import executor
    from agents.dispatcher import dispatch, get_run
    from agents.schemas import AgentDispatchRequest

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("Brief output")

    with patch.object(executor, "_get_client", return_value=mock_client):
        run_id = dispatch(
            "briefing-agent",
            AgentDispatchRequest(prompt="Give me a morning brief", namespace="global"),
            block=True,
        )

    assert run_id
    run = get_run(run_id)
    assert run is not None
    assert run["status"] == "done"


def test_dispatcher_list_runs():
    from agents.dispatcher import list_runs
    runs, total = list_runs(limit=10)
    assert isinstance(runs, list)
    assert isinstance(total, int)


def test_dispatcher_cancel_run():
    from agents.executor import create_run_record
    from agents.dispatcher import cancel_run, get_run
    agent_id = _real_agent_id()
    run_id = create_run_record(
        agent_id=agent_id,
        namespace="global",
        prompt="test",
        context={},
        session_id=None,
        triggered_by="test",
        workflow_run_id=None,
    )
    assert cancel_run(run_id)
    run = get_run(run_id)
    assert run["status"] == "cancelled"


# ── API routes ────────────────────────────────────────────────────────────────

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


def test_api_list_agents(client, auth_headers):
    r = client.get("/api/v1/agents", headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 12
    names = [a["name"] for a in data["agents"]]
    assert "briefing-agent" in names
    assert "transport-ops-agent" in names


def test_api_get_agent_by_name(client, auth_headers):
    r = client.get("/api/v1/agents/research-agent", headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["category"] == "research"


def test_api_get_agent_not_found(client, auth_headers):
    r = client.get("/api/v1/agents/fake-agent", headers=auth_headers)
    assert r.status_code == 404


def test_api_run_agent(client, auth_headers):
    from agents import executor
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("API dispatch test output")

    with patch.object(executor, "_get_client", return_value=mock_client):
        r = client.post("/api/v1/agents/briefing-agent/run", json={
            "prompt": "Morning brief please",
            "namespace": "global",
        }, headers=auth_headers)

    assert r.status_code == 202
    data = r.get_json()
    assert "run_id" in data
    assert data["status"] == "pending"


def test_api_namespace_lock_rejected(client, auth_headers):
    r = client.post("/api/v1/agents/transport-ops-agent/run", json={
        "prompt": "Fleet report",
        "namespace": "global",
    }, headers=auth_headers)
    assert r.status_code == 403


def test_api_get_run(client, auth_headers):
    from agents import executor
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("Run result")

    with patch.object(executor, "_get_client", return_value=mock_client):
        r = client.post("/api/v1/agents/briefing-agent/run", json={
            "prompt": "test",
            "namespace": "global",
        }, headers=auth_headers)
    run_id = r.get_json()["run_id"]

    time.sleep(0.5)
    r2 = client.get(f"/api/v1/agents/runs/{run_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.get_json()["id"] == run_id


def test_api_system_events(client, auth_headers):
    r = client.get("/api/v1/system/events", headers=auth_headers)
    assert r.status_code == 200
    assert "events" in r.get_json()
