"""Single source of truth for which Claude models ClaudeOS calls.

Bump CLAUDE_MODEL / CLAUDE_FAST_MODEL in .env (or the defaults below) and every agent run,
eval and consolidation job follows — no per-agent YAML edits.
"""
from __future__ import annotations

import os

LATEST_MODEL = "claude-sonnet-5-5"       # agents, chat, streaming
LATEST_FAST_MODEL = "claude-haiku-5-5"   # LLM-as-Judge eval, memory consolidation

# Retired defaults that older DB rows / YAML files still carry. Rows holding one of these
# are upgraded to the current model at read time; any other explicit model is respected.
LEGACY_MODELS = frozenset({
    "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",
    "claude-haiku-4-5", "claude-haiku-4-5-20251001", "claude-3-5-haiku-20241022",
})


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
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
    """Map an agent's stored model to the one that should actually be called."""
    stored = (stored or "").strip()
    if not stored or stored in LEGACY_MODELS:
        return default_model()
    return stored
