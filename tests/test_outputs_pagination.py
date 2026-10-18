"""Output pagination must bound database reads, including for direct callers."""
import sqlite3

import pytest
from flask import Flask


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
        conn.executemany(
            """INSERT INTO outputs
               (id, namespace, title, content, tags, created_at, deleted_at)
               VALUES (?, ?, 'needle', 'large private payload', '["needle"]', ?, ?)""",
            [(f"output-{i}", "ns-a", f"2026-01-01T00:{i // 60:02}:{i % 60:02}", None)
             for i in range(225)]
            + [("other-tenant", "ns-b", "2026-01-02T00:00:00", None),
               ("deleted", "ns-a", "2026-01-03T00:00:00", "2026-01-03T00:00:00")],
        )
        yield conn


@pytest.fixture
def output_client(output_db):
    from core.api.auth import create_api_key
    from core.api.routes.outputs import outputs_bp

    raw_key, _ = create_api_key("pagination-test", permissions=["read"], namespace="ns-a")
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(outputs_bp)
    with app.test_client() as client:
        yield client, {"X-API-Key": raw_key}


@pytest.mark.parametrize("operation, maximum", [("list_outputs", 200), ("search", 100)])
@pytest.mark.parametrize("limit", [-1, 0, 2**63, "1", 1.5, True, None])
def test_storage_rejects_invalid_limits_before_database(monkeypatch, operation, maximum, limit):
    from outputs import manager

    def forbidden_db():
        pytest.fail("Invalid pagination reached the database")

    monkeypatch.setattr(manager, "get_db", forbidden_db)
    kwargs = {"query": "needle"} if operation == "search" else {}
    for invalid in (limit, maximum + 1):
        with pytest.raises(ValueError):
            getattr(manager, operation)(limit=invalid, **kwargs)


@pytest.mark.parametrize("offset", [-1, 2**63, "0", 0.5, True, None])
def test_storage_rejects_invalid_offsets_before_database(monkeypatch, offset):
    from outputs import manager

    def forbidden_db():
        pytest.fail("Invalid offset reached the database")

    monkeypatch.setattr(manager, "get_db", forbidden_db)
    with pytest.raises(ValueError):
        manager.list_outputs(offset=offset)


@pytest.mark.parametrize("path, maximum", [("", 200), ("/search", 100)])
@pytest.mark.parametrize("limit", ["-1", "0", "over-max", str(2**63), "invalid", "1.5", ""])
def test_http_rejects_invalid_limits_before_database(output_client, monkeypatch, path, maximum, limit):
    from outputs import manager

    client, headers = output_client

    def forbidden_db():
        pytest.fail("Invalid HTTP pagination reached output storage")

    monkeypatch.setattr(manager, "get_db", forbidden_db)
    response = client.get(f"/api/v1/outputs{path}", headers=headers,
                          query_string={"q": "needle", "limit": maximum + 1 if limit == "over-max" else limit})
    assert response.status_code == 400
    assert "error" in response.json


@pytest.mark.parametrize("offset", ["-1", str(2**63), "invalid", "1.5", ""])
def test_http_rejects_invalid_offsets(output_client, monkeypatch, offset):
    from outputs import manager

    client, headers = output_client

    def forbidden_db():
        pytest.fail("Invalid HTTP offset reached output storage")

    monkeypatch.setattr(manager, "get_db", forbidden_db)
    response = client.get("/api/v1/outputs", headers=headers, query_string={"offset": offset})
    assert response.status_code == 400


@pytest.mark.parametrize("path, default, maximum", [("", 50, 200), ("/search", 20, 100)])
@pytest.mark.parametrize("page", ["default", "minimum", "maximum"])
def test_http_pages_are_bounded_and_namespace_scoped(output_client, path, default, maximum, page):
    client, headers = output_client
    params = {"q": "needle", "namespace": "ns-b"}
    expected = {"default": default, "minimum": 1, "maximum": maximum}[page]
    if page != "default":
        params["limit"] = expected
    response = client.get(f"/api/v1/outputs{path}", headers=headers, query_string=params)
    assert response.status_code == 200
    assert len(response.json) == expected
    assert all(row["namespace"] == "ns-a" and row["id"] != "deleted" for row in response.json)
    assert all("content" not in row for row in response.json)


def test_listing_does_not_read_content_and_preserves_pagination(output_db):
    from outputs import manager

    def deny_content(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and table == "outputs" and column == "content":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    output_db.set_authorizer(deny_content)
    try:
        rows = manager.list_outputs(namespace="ns-a", output_type="report", tags=["needle"], limit=2, offset=1)
    finally:
        output_db.set_authorizer(None)
    assert [row.id for row in rows] == ["output-223", "output-222"]
    assert all(row.content == "" and row.tags == ["needle"] for row in rows)
    assert manager.get_by_id(rows[0].id).content == "large private payload"
    assert manager.list_outputs(namespace="ns-a", offset=225) == []
