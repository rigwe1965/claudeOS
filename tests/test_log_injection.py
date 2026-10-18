"""Percent-decoded control characters in the request path must not forge log lines."""
import logging


def test_request_path_control_chars_are_escaped_in_logs(client, caplog):
    with caplog.at_level(logging.INFO, logger="claudeos.api"):
        client.get("/api/v1/health%0a2026-01-01%20INFO%20claudeos.api%20FAKE%0d%E2%80%A8x")
    msgs = [r.getMessage() for r in caplog.records if r.name == "claudeos.api"]
    assert msgs
    for m in msgs:
        assert "\n" not in m and "\r" not in m and " " not in m
    assert any("\\n" in m and "\\r" in m and "\\u2028" in m for m in msgs)
