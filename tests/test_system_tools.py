"""Output tool lookups must not disclose records outside the run's namespace."""
import sqlite3

import pytest

from core.tools import call_tool


@pytest.fixture
def output_db(monkeypatch):
    from core import database
    from scripts.migrate import MIGRATIONS_DIR

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        monkeypatch.setattr(database, "_get_connection", lambda: conn)
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            database.run_migration(migration)
        yield conn


@pytest.mark.parametrize("namespace, deleted_at", [
    ("ns-b", None),
    ("global", None),
    ("ns-a", "2026-01-01 00:00:00"),
    ("ns-b", "2026-01-01 00:00:00"),
])
def test_get_output_hides_inaccessible_and_deleted_records(output_db, namespace, deleted_at):
    # Keep the ID identical while changing whether the record exists.
    tool_input = {"output_id": "requested-output", "namespace": namespace}
    missing = call_tool("get_output", tool_input, namespace="ns-a")
    assert missing == (
        "Output 'requested-output' not found. "
        "Use search_outputs or get_recent_outputs to find valid IDs."
    )
    output_db.execute(
        "INSERT INTO outputs (id, namespace, title, content, deleted_at) VALUES (?, ?, ?, ?, ?)",
        ("requested-output", namespace, "Private title", "Private content", deleted_at),
    )

    assert call_tool("get_output", tool_input, namespace="ns-a") == missing


@pytest.mark.parametrize("namespace", ["ns-a", "global"])
def test_get_output_reads_active_record_in_own_namespace(output_db, namespace):
    output_db.execute(
        "INSERT INTO outputs (id, namespace, title, content) VALUES (?, ?, ?, ?)",
        ("own-output", namespace, "Own title", "Own content"),
    )

    result = call_tool("get_output", {"output_id": "own-output"}, namespace=namespace)
    assert result.startswith("# Own title\n")
    assert "**ID:** own-output\n" in result
    assert result.endswith("---\nOwn content")
