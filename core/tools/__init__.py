"""Unified tool dispatcher for ClaudeOS agents.

Routes tool calls to the correct backend:
  - Web tools (web_search, get_news, search_wikipedia, multi_search, fetch_page)
  - System tools (search_outputs, get_output, get_recent_outputs)
"""
from __future__ import annotations

from core.tools.web_search import (
    TOOL_DEFINITIONS as _WEB_DEFS,
    call_tool as _web_call,
)
from core.tools.system_tools import (
    TOOL_DEFINITIONS as _SYS_DEFS,
    call_tool as _sys_call,
)

ALL_TOOL_DEFINITIONS = _WEB_DEFS + _SYS_DEFS
_ALL_MAP = {t["name"]: t for t in ALL_TOOL_DEFINITIONS}
_WEB_NAMES = {t["name"] for t in _WEB_DEFS}
_SYS_NAMES = {t["name"] for t in _SYS_DEFS}


def get_definitions(tool_names: list[str]) -> list[dict]:
    """Return Claude API tool definitions for the given tool name list."""
    return [_ALL_MAP[n] for n in tool_names if n in _ALL_MAP]


def call_tool(name: str, tool_input: dict, namespace: str = "global") -> str:
    """Dispatch a tool call to the correct backend. Namespace-scoped for system tools."""
    if name in _WEB_NAMES:
        return _web_call(name, tool_input)
    if name in _SYS_NAMES:
        return _sys_call(name, tool_input, namespace)
    return f"Unknown tool: {name}"
