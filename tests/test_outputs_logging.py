"""Untrusted output metadata must stay within one operational log line."""
import logging
from pathlib import Path

import pytest
from flask import Flask


@pytest.fixture
def output_logging_client(fresh_db, monkeypatch, tmp_path):
    from core.api.auth import create_api_key
    from core.api.routes.outputs import outputs_bp
    from outputs import manager

    monkeypatch.setattr(manager, "STORE_ROOT", tmp_path / "outputs")
    raw_key, _ = create_api_key("output-logging", permissions=["read", "write"])
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(outputs_bp)
    with app.test_client() as client:
        yield client, {"X-API-Key": raw_key}


@pytest.mark.parametrize("field", ["output_type", "namespace"])
@pytest.mark.parametrize("separator", [
    "\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", "\x1b",
])
def test_output_metadata_cannot_forge_log_lines(output_logging_client, caplog, field, separator):
    from outputs.manager import get_by_id

    client, headers = output_logging_client
    injected = f"Résumé{separator}2026 [INFO] claudeos.auth: forged event"
    body = {"namespace": "global", "title": "Report", "content": "Private output", field: injected}
    with caplog.at_level(logging.INFO, logger="claudeos.outputs.manager"):
        response = client.post("/api/v1/outputs", headers=headers, json=body)

    assert response.status_code == 201
    assert response.json[field] == injected
    saved = get_by_id(response.json["id"])
    assert getattr(saved, field) == injected
    assert saved.content == body["content"]
    assert Path(saved.file_path).read_text(encoding="utf-8") == body["content"]
    records = [record for record in caplog.records if record.name == "claudeos.outputs.manager"]
    assert len(records) == 1
    rendered = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ).format(records[0])
    assert len(rendered.splitlines()) == 1
    assert separator not in rendered
    assert repr(injected) in rendered
