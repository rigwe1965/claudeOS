"""Agents → Runs tab: compact table row builder + duration formatting."""
import inspect

import pytest
import streamlit as st

from dashboard._pages._agents import _format_duration, _runs_table_rows


@pytest.mark.parametrize("ms,expected", [
    (None, "—"), (0, "—"), ("bad", "—"), (-5, "—"),
    (850, "850ms"), (999, "999ms"), (1000, "1.0s"), (1234, "1.2s"),
    (59_999, "60.0s"), (60_000, "1m 00s"), (125_000, "2m 05s"),
])
def test_format_duration(ms, expected):
    assert _format_duration(ms) == expected


RUN = {
    "id": "abcdef1234567890", "agent_id": "11111111-2222-3333-4444-555555555555",
    "agent_name": "analysis-agent", "agent_display_name": "Analysis Agent",
    "namespace": "faiyke-ai", "status": "done", "eval_score": 4.25,
    "tokens_in": 1200, "tokens_out": 300, "duration_ms": 2500,
    "created_at": "2026-10-17T13:43:04",
}


def test_row_fields():
    row = _runs_table_rows([RUN])[0]
    assert row == {
        "Agent": "analysis-agent", "Namespace": "faiyke-ai", "Status": "● done",
        "Quality": 4.25, "Tokens": 1500, "Duration": "2.5s",
        "Started": "2026-10-17 13:43", "Run": "abcdef12",
    }


def test_agent_name_fallback_chain():
    no_name = {**RUN, "agent_name": None}
    assert _runs_table_rows([no_name])[0]["Agent"] == "Analysis Agent"
    no_display = {**no_name, "agent_display_name": None}
    assert _runs_table_rows([no_display])[0]["Agent"] == "11111111-222"
    assert _runs_table_rows([{}])[0]["Agent"] == "—"


def test_missing_values_do_not_crash():
    row = _runs_table_rows([{"status": "running"}])[0]
    assert row["Status"] == "● running"
    assert row["Quality"] is None and row["Tokens"] == 0 and row["Duration"] == "—"
    assert row["Started"] == "" and row["Run"] == ""


def test_unknown_status_passes_through():
    assert _runs_table_rows([{**RUN, "status": "cancelled"}])[0]["Status"] == "cancelled"


def test_dataframe_kwargs_exist_in_installed_streamlit():
    """Guard against using a newer Streamlit kwarg than the venv ships (row_height crashed 1.38)."""
    params = inspect.signature(st.dataframe).parameters
    for kw in ("use_container_width", "hide_index", "column_config"):
        assert kw in params
    for col in ("TextColumn", "ProgressColumn", "NumberColumn"):
        assert hasattr(st.column_config, col)
