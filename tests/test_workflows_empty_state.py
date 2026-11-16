"""The Workflows page must tell "the API is down" apart from "there are no workflows yet".

Regression test: an empty list from a healthy API (HTTP 200, []) used to show "API unreachable", because the page tested
`if not data` and an empty list is falsy. A fresh install, a new client or the hosted demo (no workflows seeded) hit it."""
from types import SimpleNamespace

import pytest

pytest.importorskip("streamlit")
from dashboard._pages import _workflows


@pytest.fixture
def recorded(monkeypatch):
    calls = {"error": [], "info": []}
    fake_st = SimpleNamespace(
        error=lambda msg, *a, **k: calls["error"].append(msg),
        info=lambda msg, *a, **k: calls["info"].append(msg),
    )
    monkeypatch.setattr(_workflows, "st", fake_st)
    return calls


def test_empty_list_is_not_reported_as_unreachable(recorded):
    _workflows._render_workflow_list(lambda path: [], lambda *a, **k: None)
    assert recorded["error"] == []
    assert len(recorded["info"]) == 1 and "No workflows" in recorded["info"][0]


def test_failed_api_call_is_still_reported_as_unreachable(recorded):
    _workflows._render_workflow_list(lambda path: None, lambda *a, **k: None)
    assert recorded["error"] == ["API unreachable"]
    assert recorded["info"] == []
