"""Single source of truth for which Claude models ClaudeOS calls — and what they cost.

Bump CLAUDE_MODEL / CLAUDE_FAST_MODEL in .env (or the defaults below) and every agent run,
eval and consolidation job follows — no per-agent YAML edits and no restart: the .env file is
re-read whenever its modification time changes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

LATEST_MODEL = "claude-sonnet-5-5"       # agents, chat, streaming
LATEST_FAST_MODEL = "claude-haiku-5-5"   # LLM-as-Judge eval, memory consolidation

# Retired defaults that older DB rows / YAML files still carry. Rows holding one of these
# are upgraded to the current model at read time; any other explicit model is respected.
LEGACY_MODELS = frozenset({
    "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",
    "claude-haiku-4-5", "claude-haiku-4-5-20251001", "claude-3-5-haiku-20241022",
})

# USD per million tokens (input, output) — Anthropic first-party list prices.
# Override for the active default model without a code change via .env:
#   CLAUDE_PRICE_IN_PER_MTOK / CLAUDE_PRICE_OUT_PER_MTOK
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5":   (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-5-5":  (0.10, 0.50),   # prompts up to 100K tokens
    "claude-haiku-4-5":  (1.0, 5.0),
    "claude-opus-5-5":   (4.0, 20.0),
    "claude-opus-5":     (5.0, 25.0),
    "claude-opus-4-8":   (5.0, 25.0),
    "claude-fable-5-1":  (10.0, 50.0),
}

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_dotenv_cache: dict = {"mtime": None, "values": {}}


def _dotenv_values() -> dict[str, str]:
    """Parse .env, re-reading only when the file changed (so edits apply live)."""
    try:
        mtime = _ENV_FILE.stat().st_mtime
    except OSError:
        return {}
    if mtime != _dotenv_cache["mtime"]:
        values: dict[str, str] = {}
        try:
            for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, raw = line.partition("=")
                raw = raw.strip()
                if raw[:1] in ('"', "'"):
                    raw = raw.strip(raw[0])
                else:
                    raw = re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()   # drop inline comment
                values[key.strip()] = raw
        except OSError:
            return {}
        _dotenv_cache.update(mtime=mtime, values=values)
    return _dotenv_cache["values"]


def _env(name: str, default: str) -> str:
    value = _dotenv_values().get(name, "").strip() or os.environ.get(name, "").strip()
    if not value:
        try:
            from core.config import get_settings
            value = str(getattr(get_settings(), name, "") or "").strip()
        except Exception:
            value = ""
    return value or default


def default_model() -> str:
    return _env("CLAUDE_MODEL", LATEST_MODEL)


def fast_model() -> str:
    return _env("CLAUDE_FAST_MODEL", LATEST_FAST_MODEL)


def resolve_model(stored: str | None) -> str:
    """Map an agent's stored model to the one that should actually be called.

    An empty value means "inherit the current default", so a model bump needs no DB edit.
    """
    stored = (stored or "").strip()
    if not stored or stored in LEGACY_MODELS:
        return default_model()
    return stored


_LABEL_RE = re.compile(r"claude-(?P<family>[a-z]+)-(?P<ver>\d+(?:-\d+)?)(?:-\d{8})?$")


def model_label(model: str | None = None) -> str:
    """'claude-sonnet-5-5' -> 'Sonnet 5.5' (falls back to the raw id)."""
    model = (model or default_model()).strip()
    m = _LABEL_RE.match(model)
    if not m:
        return model
    return f"{m['family'].capitalize()} {m['ver'].replace('-', '.')}"


def price_per_mtok(model: str | None = None) -> tuple[float, float]:
    """(input, output) USD per million tokens for `model` (default: the active default model)."""
    model = model or default_model()
    if model == default_model():
        try:
            p_in = float(_env("CLAUDE_PRICE_IN_PER_MTOK", ""))
            p_out = float(_env("CLAUDE_PRICE_OUT_PER_MTOK", ""))
            return p_in, p_out
        except ValueError:
            pass
    return PRICING.get(model) or PRICING.get(LATEST_MODEL, (2.0, 10.0))


def estimate_cost(tokens_in: int, tokens_out: int, model: str | None = None) -> float:
    p_in, p_out = price_per_mtok(model)
    return (tokens_in or 0) / 1_000_000 * p_in + (tokens_out or 0) / 1_000_000 * p_out


def model_info() -> dict:
    """Everything the UI needs to describe the models currently in force."""
    d, f = default_model(), fast_model()
    return {
        "default_model": d, "default_label": model_label(d), "default_price": price_per_mtok(d),
        "fast_model": f, "fast_label": model_label(f), "fast_price": price_per_mtok(f),
    }
