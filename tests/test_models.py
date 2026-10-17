"""Model selection: one source of truth, legacy ids upgraded, explicit choices respected."""
import pytest

from agents.schemas import AgentDefinition
from core import models


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_FAST_MODEL", raising=False)


def _agent(**kw):
    return AgentDefinition(id="a", name="x", display_name="X", system_prompt="p", **kw)


def test_defaults_are_latest():
    assert models.default_model() == models.LATEST_MODEL
    assert models.fast_model() == models.LATEST_FAST_MODEL


def test_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    assert models.default_model() == "claude-opus-5-5"
    assert _agent().model == "claude-opus-5-5"


@pytest.mark.parametrize("legacy", sorted(models.LEGACY_MODELS))
def test_legacy_models_are_upgraded(legacy):
    assert _agent(model=legacy).model == models.default_model()


def test_explicit_non_legacy_model_is_kept():
    assert _agent(model="claude-opus-5-5").model == "claude-opus-5-5"


def test_no_hardcoded_model_ids_in_runtime_code():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("agents/evaluator.py", "memory/consolidator.py", "agents/executor.py", "agents/dispatcher.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert not re.search(r'"claude-(sonnet|haiku|opus)-', text), rel
