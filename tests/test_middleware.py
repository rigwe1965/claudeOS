"""Request logs must not contain credentials carried in URLs."""
import logging

import pytest
from flask import Flask

from core.api.middleware import register_middleware


@pytest.fixture()
def logging_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_middleware(app)

    @app.route("/api/v1/auth/session/<key>", methods=["GET", "DELETE"])
    def session(key):
        status = 404 if key == "expired-secret" else 200
        return "", status

    @app.get("/api/v1/health")
    def health():
        return "", 200

    return app


@pytest.mark.parametrize("method,path,status,logged_route", [
    ("GET", "/api/v1/auth/session/live-secret", 200, "/api/v1/auth/session/<key>"),
    ("DELETE", "/api/v1/auth/session/live-secret", 200, "/api/v1/auth/session/<key>"),
    ("HEAD", "/api/v1/auth/session/live-secret", 200, "/api/v1/auth/session/<key>"),
    ("OPTIONS", "/api/v1/auth/session/live-secret", 200, "/api/v1/auth/session/<key>"),
    ("GET", "/api/v1/auth/session/expired-secret", 404, "/api/v1/auth/session/<key>"),
    ("GET", "/api/v1/auth/session/live%2Dsecret", 200, "/api/v1/auth/session/<key>"),
    ("POST", "/api/v1/auth/session/live-secret", 405, "unmatched"),
    ("GET", "/api/v1/auth/session/live-secret/extra", 404, "unmatched"),
    ("GET", "/api/v1/auth/session/live-secret/", 404, "unmatched"),
    ("GET", "/unknown/live-secret", 404, "unmatched"),
    ("GET", "/api/v1/health?_s=live-secret", 200, "/api/v1/health"),
])
def test_request_logs_exclude_url_secrets(logging_app, caplog, method, path, status, logged_route):
    with caplog.at_level(logging.INFO, logger="claudeos.api"):
        response = logging_app.test_client().open(path, method=method)

    assert response.status_code == status
    records = [record for record in caplog.records if record.name == "claudeos.api"]
    assert len(records) == 1
    record = records[0]
    assert record.args[:3] == (method, logged_route, status)
    assert isinstance(record.args[3], int) and record.args[3] >= 0
    assert record.getMessage() == f"{method} {logged_route} {status} {record.args[3]}ms"
    assert "secret" not in caplog.text
    assert "secret" not in repr(record.args)
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Response-Time"] == f"{record.args[3]}ms"
