"""Model selection: one source of truth, legacy ids upgraded, explicit choices respected."""
import pytest

from agents.schemas import AgentDefinition
from core import models


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in ("CLAUDE_MODEL", "CLAUDE_FAST_MODEL", "CLAUDE_PRICE_IN_PER_MTOK", "CLAUDE_PRICE_OUT_PER_MTOK"):
        monkeypatch.delenv(var, raising=False)
    # Hermetic: never read the developer's real .env
    monkeypatch.setattr(models, "_ENV_FILE", tmp_path / ".env")
    monkeypatch.setitem(models._dotenv_cache, "mtime", None)


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


def test_empty_stored_model_inherits_current_default(monkeypatch):
    assert models.resolve_model("") == models.default_model()
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    assert models.resolve_model("") == "claude-opus-5-5"   # follows a bump with no DB edit


def test_env_file_edit_applies_without_restart(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CLAUDE_MODEL=claude-opus-5-5\n", encoding="utf-8")
    monkeypatch.setitem(models._dotenv_cache, "mtime", None)
    assert models.default_model() == "claude-opus-5-5"
    env.write_text('CLAUDE_MODEL="claude-sonnet-5"\n# comment\n', encoding="utf-8")
    import os
    os.utime(env, (env.stat().st_atime, env.stat().st_mtime + 5))   # mtime tick on fast filesystems
    assert models.default_model() == "claude-sonnet-5"


def test_env_inline_comment_is_not_part_of_the_value(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("CLAUDE_MODEL=   # blank on purpose\nCLAUDE_FAST_MODEL=claude-haiku-5-5  # judge\n",
                                   encoding="utf-8")
    monkeypatch.setitem(models._dotenv_cache, "mtime", None)
    assert models.default_model() == models.LATEST_MODEL
    assert models.fast_model() == "claude-haiku-5-5"


def test_model_label():
    assert models.model_label("claude-sonnet-5-5") == "Sonnet 5.5"
    assert models.model_label("claude-haiku-5-5") == "Haiku 5.5"
    assert models.model_label("claude-opus-5") == "Opus 5"
    assert models.model_label("something-else") == "something-else"


def test_cost_uses_current_model_price(monkeypatch):
    # Sonnet 5.5: $2 in / $10 out per million tokens
    assert models.estimate_cost(1_000_000, 1_000_000) == pytest.approx(12.0)
    assert models.estimate_cost(1_000_000, 0, "claude-haiku-5-5") == pytest.approx(0.10)
    monkeypatch.setenv("CLAUDE_PRICE_IN_PER_MTOK", "1")
    monkeypatch.setenv("CLAUDE_PRICE_OUT_PER_MTOK", "4")
    assert models.estimate_cost(1_000_000, 1_000_000) == pytest.approx(5.0)   # override wins


def test_registry_upsert_stores_inherit_not_a_concrete_id(fresh_db):
    from agents import registry
    agent = _agent()
    registry.upsert(agent)
    with registry.get_db() as conn:
        assert conn.execute("SELECT model FROM agents WHERE name='x'").fetchone()["model"] == ""
    assert registry.get_by_name("x").model == models.default_model()


def test_no_stale_model_names_or_prices_in_ui_and_api():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("dashboard/_pages/_usage.py", "dashboard/_pages/_observability.py", "core/api/routes/system.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "Sonnet 4.6" not in text, rel
        assert not re.search(r"\*\s*15\.0|\*\s*3\.0\)", text), f"hardcoded price in {rel}"


def test_no_hardcoded_model_ids_in_runtime_code():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("agents/evaluator.py", "memory/consolidator.py", "agents/executor.py", "agents/dispatcher.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert not re.search(r'"claude-(sonnet|haiku|opus)-', text), rel
