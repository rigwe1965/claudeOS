"""Reminder input must stay within a single operational log line."""
import json
import logging
from email import message_from_string
from unittest.mock import MagicMock

import pytest
from flask import Flask

from notifications import email as reminder_email, reminder_job


@pytest.fixture
def reminder_env(monkeypatch):
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "reminder-logging-test-secret-32-characters!")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("NOTIFY_EMAIL", "recipient@example.com")


@pytest.fixture
def reminder_client(reminder_env, fresh_db, monkeypatch):
    from core.api.routes.memory import memory_bp
    from core.auth import create_access_token, create_user
    from core.database import get_db
    from memory import engine

    with get_db() as conn:
        conn.execute(
            "INSERT INTO namespaces (id, slug, display_name) VALUES (?, ?, ?)",
            ("reminder-ns", "reminder-ns", "Reminders"),
        )
    user = create_user("reminder_user", "ReminderUser123!", role="client", namespace="reminder-ns")
    token = create_access_token(user["id"], user["username"], "client", "reminder-ns")
    # Exercise the real API and SQLite write; embeddings are unrelated to delivery.
    pool = MagicMock()
    pool._work_queue.qsize.return_value = 0
    monkeypatch.setattr(engine, "_bg_pool", pool)
    transport = MagicMock()
    transport.__enter__.return_value = transport
    monkeypatch.setattr(reminder_email.smtplib, "SMTP", MagicMock(return_value=transport))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(memory_bp)
    with app.test_client() as client:
        yield client, {"Authorization": f"Bearer {token}"}, transport


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n", "\u2028"])
@pytest.mark.parametrize("field", ["key", "action"])
def test_reminder_logs_contain_client_input(reminder_client, caplog, newline, field):
    from core.database import get_db

    client, headers, transport = reminder_client
    injected = f"Réunion{newline}2026-10-18 [INFO] claudeos.auth: forged event"
    key = injected if field == "key" else "meeting"
    value = {"confirmation": "Private reminder"}
    if field == "action":
        value["action"] = injected
    response = client.post("/api/v1/memory", headers=headers, json={
        "namespace": "other-namespace", "category": "reminder", "key": key,
        "value": json.dumps(value), "expires_at": "2000-01-01T12:00:00Z",
    })
    assert response.status_code == 201
    assert response.json["namespace"] == "reminder-ns"
    assert response.json["key"] == key

    with caplog.at_level(logging.INFO, logger="claudeos.notifications"):
        assert reminder_job.run() == 1
        assert reminder_job.run() == 0

    records = [r for r in caplog.records if r.name in {
        "claudeos.notifications.email", "claudeos.notifications.reminder_job",
    }]
    assert len(records) == 2
    for record in records:
        assert len(logging.Formatter("%(levelname)s %(name)s: %(message)s").format(record).splitlines()) == 1
    assert repr(injected)[1:-1] in records[0].getMessage()
    if field == "key":
        assert repr(key) in records[1].getMessage()
    transport.sendmail.assert_called_once()
    message = message_from_string(transport.sendmail.call_args.args[2])
    assert f"Key: {key}\n" in message.get_payload()[0].get_payload(decode=True).decode("utf-8")
    with get_db() as conn:
        row = conn.execute("SELECT key, notified_at FROM memory_entries WHERE id = ?", (response.json["id"],)).fetchone()
    assert row["key"] == key
    assert row["notified_at"] is not None


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
def test_reminder_failure_log_contains_exception_text(reminder_client, caplog, newline):
    from core.database import get_db

    client, headers, transport = reminder_client
    response = client.post("/api/v1/memory", headers=headers, json={
        "category": "reminder", "key": "meeting", "value": "Private reminder",
        "expires_at": "2000-01-01T12:00:00Z",
    })
    assert response.status_code == 201
    error = f"Rejected reminder{newline}[INFO] claudeos.auth: forged event"
    transport.sendmail.side_effect = RuntimeError(error)
    with caplog.at_level(logging.ERROR, logger=reminder_job.logger.name):
        assert reminder_job.run() == 0

    records = [r for r in caplog.records if r.name == reminder_job.logger.name]
    assert len(records) == 1
    assert len(records[0].getMessage().splitlines()) == 1
    assert repr(error) in records[0].getMessage()
    with get_db() as conn:
        row = conn.execute("SELECT notified_at FROM memory_entries WHERE id = ?", (response.json["id"],)).fetchone()
    assert row["notified_at"] is None
