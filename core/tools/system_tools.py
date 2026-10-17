"""System tools — give agents access to internal ClaudeOS data.

These tools let agents read outputs produced by other agents, search memory,
and query workspace data. This enables cross-agent workflows where one agent's
output becomes another agent's input.

Tools exposed to Claude:
  search_outputs     — find saved outputs by keyword/topic/agent
  get_output         — fetch full content of a specific output by ID
  get_recent_outputs — list the most recent outputs in this workspace
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger("claudeos.tools.system_tools")

# ── Claude API tool definitions ───────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_outputs",
        "description": (
            "Search saved outputs from any agent in this workspace. "
            "Use this to find reports, research, analyses, or any content "
            "produced by other agents. Search by keyword, topic, or title. "
            "Returns output IDs — use get_output to retrieve full content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword, topic, or phrase to search for in saved outputs.",
                },
                "agent_name": {
                    "type": "string",
                    "description": (
                        "Optional: filter by which agent produced the output. "
                        "E.g. 'research-agent', 'briefing-agent'."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1–10). Default 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_output",
        "description": (
            "Fetch the complete content of a saved output by its ID. "
            "Use after search_outputs or get_recent_outputs to read the full text "
            "of a report, research output, or any saved agent result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "output_id": {
                    "type": "string",
                    "description": "The output ID returned by search_outputs or get_recent_outputs.",
                },
            },
            "required": ["output_id"],
        },
    },
    {
        "name": "get_recent_outputs",
        "description": (
            "List the most recent outputs saved in this workspace. "
            "Use when you need to find what was recently produced without "
            "knowing the exact title. Optionally filter by agent name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent outputs to list (1–10). Default 5.",
                    "default": 5,
                },
                "agent_name": {
                    "type": "string",
                    "description": "Optional: only show outputs from this agent.",
                },
            },
        },
    },
    {
        "name": "get_agent_runs",
        "description": (
            "Return a log of recent agent runs in this workspace — who ran what, when, "
            "what the user asked, token cost, and status. Use this to answer questions "
            "like 'what happened today', 'what agents ran this morning', or "
            "'what did the user ask recently'. Always call this before summarising "
            "workspace activity. Returns only completed runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Look back this many hours (1–168). Default 24.",
                    "default": 24,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max runs to return (1–50). Default 20.",
                    "default": 20,
                },
                "agent_name": {
                    "type": "string",
                    "description": "Optional: filter to one specific agent.",
                },
            },
        },
    },
    {
        "name": "get_git_log",
        "description": (
            "Return recent git commits to the ClaudeOS codebase — what code changes "
            "were made, when, and by whom. Use this to answer 'what changed in the "
            "system', 'what was updated today', or 'what technical work was done'. "
            "Each entry shows the commit hash, message, author, and timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Look back this many hours (1–168). Default 24.",
                    "default": 24,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max commits to return (1–50). Default 20.",
                    "default": 20,
                },
            },
        },
    },
]

_TOOL_MAP = {t["name"]: t for t in TOOL_DEFINITIONS}


def get_definitions(tool_names: list[str]) -> list[dict]:
    return [_TOOL_MAP[n] for n in tool_names if n in _TOOL_MAP]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def call_tool(name: str, tool_input: dict, namespace: str = "global") -> str:
    """Execute a system tool. Namespace-scoped — agents only see their own workspace data."""
    try:
        if name == "search_outputs":
            return _search_outputs(
                query=tool_input.get("query", ""),
                namespace=namespace,
                agent_name=tool_input.get("agent_name", ""),
                limit=min(int(tool_input.get("limit", 5)), 10),
            )
        elif name == "get_output":
            return _get_output(
                output_id=tool_input.get("output_id", ""),
                namespace=namespace,
            )
        elif name == "get_recent_outputs":
            return _get_recent_outputs(
                namespace=namespace,
                limit=min(int(tool_input.get("limit", 5)), 10),
                agent_name=tool_input.get("agent_name", ""),
            )
        elif name == "get_agent_runs":
            return _get_agent_runs(
                namespace=namespace,
                hours=min(int(tool_input.get("hours", 24)), 168),
                limit=min(int(tool_input.get("limit", 20)), 50),
                agent_name=tool_input.get("agent_name", ""),
            )
        elif name == "get_git_log":
            return _get_git_log(
                hours=min(int(tool_input.get("hours", 24)), 168),
                limit=min(int(tool_input.get("limit", 20)), 50),
            )
        else:
            return f"Unknown system tool: {name}"
    except Exception as e:
        logger.warning("System tool %s failed: %s", name, e)
        return f"System tool error ({name}): {e}"


# ── Implementations ───────────────────────────────────────────────────────────

def _search_outputs(query: str, namespace: str, agent_name: str = "", limit: int = 5) -> str:
    from core.database import get_db

    if not query:
        return "Query is required for search_outputs."

    pattern = f"%{query}%"
    with get_db() as conn:
        if agent_name:
            rows = conn.execute(
                """SELECT o.id, o.title, o.content, o.created_at,
                          COALESCE(a.name, o.tags) as src_agent
                   FROM outputs o
                   LEFT JOIN agent_runs r ON r.id = o.agent_run_id
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE o.namespace = ? AND o.deleted_at IS NULL
                     AND LOWER(COALESCE(a.name,'')) LIKE LOWER(?)
                     AND (LOWER(o.title) LIKE LOWER(?) OR LOWER(o.content) LIKE LOWER(?))
                   ORDER BY o.created_at DESC LIMIT ?""",
                (namespace, f"%{agent_name}%", pattern, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT o.id, o.title, o.content, o.created_at,
                          COALESCE(a.name, '') as src_agent
                   FROM outputs o
                   LEFT JOIN agent_runs r ON r.id = o.agent_run_id
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE o.namespace = ? AND o.deleted_at IS NULL
                     AND (LOWER(o.title) LIKE LOWER(?) OR LOWER(o.content) LIKE LOWER(?))
                   ORDER BY o.created_at DESC LIMIT ?""",
                (namespace, pattern, pattern, limit),
            ).fetchall()

    if not rows:
        # Try broader match — maybe query terms are too specific
        with get_db() as conn:
            rows = conn.execute(
                """SELECT o.id, o.title, o.content, o.created_at,
                          COALESCE(a.name, '') as src_agent
                   FROM outputs o
                   LEFT JOIN agent_runs r ON r.id = o.agent_run_id
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE o.namespace = ? AND o.deleted_at IS NULL
                   ORDER BY o.created_at DESC LIMIT ?""",
                (namespace, limit),
            ).fetchall()
        if not rows:
            return (
                f"No outputs found in workspace '{namespace}'. "
                "No agent outputs have been saved yet — run an agent with save_output=true first."
            )
        # Return recent ones with a note
        note = f"No outputs matched '{query}'. Showing {len(rows)} most recent outputs instead:\n\n"
        return note + _format_output_list(rows)

    return f"Found {len(rows)} output(s) matching '{query}':\n\n" + _format_output_list(rows)


def _get_output(output_id: str, namespace: str) -> str:
    from core.database import get_db

    if not output_id:
        return "output_id is required."

    with get_db() as conn:
        row = conn.execute(
            """SELECT o.id, o.title, o.content, o.created_at, o.tags,
                      COALESCE(a.name, '') as src_agent
               FROM outputs o
               LEFT JOIN agent_runs r ON r.id = o.agent_run_id
               LEFT JOIN agents a ON a.id = r.agent_id
               WHERE o.id = ? AND o.namespace = ? AND o.deleted_at IS NULL""",
            (output_id, namespace),
        ).fetchone()

    if not row:
        # Try without namespace scoping to give a useful error
        with get_db() as conn:
            exists = conn.execute(
                "SELECT id, namespace FROM outputs WHERE id = ? AND deleted_at IS NULL",
                (output_id,),
            ).fetchone()
        if exists:
            return (
                f"Output '{output_id}' exists but belongs to namespace '{exists['namespace']}', "
                f"not '{namespace}'. You can only access outputs in your own workspace."
            )
        return f"Output '{output_id}' not found. Use search_outputs or get_recent_outputs to find valid IDs."

    tags = []
    if row["tags"]:
        try:
            tags = json.loads(row["tags"])
        except Exception:
            pass

    return "\n".join([
        f"# {row['title']}",
        f"**Produced by:** {row['src_agent'] or 'unknown agent'}",
        f"**Saved:** {(row['created_at'] or '')[:16]}",
        f"**ID:** {row['id']}",
        "---",
        row["content"] or "(empty content)",
    ])


def _get_recent_outputs(namespace: str, limit: int = 5, agent_name: str = "") -> str:
    from core.database import get_db

    with get_db() as conn:
        if agent_name:
            rows = conn.execute(
                """SELECT o.id, o.title, o.content, o.created_at,
                          COALESCE(a.name, '') as src_agent
                   FROM outputs o
                   LEFT JOIN agent_runs r ON r.id = o.agent_run_id
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE o.namespace = ? AND o.deleted_at IS NULL
                     AND LOWER(COALESCE(a.name,'')) LIKE LOWER(?)
                   ORDER BY o.created_at DESC LIMIT ?""",
                (namespace, f"%{agent_name}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT o.id, o.title, o.content, o.created_at,
                          COALESCE(a.name, '') as src_agent
                   FROM outputs o
                   LEFT JOIN agent_runs r ON r.id = o.agent_run_id
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE o.namespace = ? AND o.deleted_at IS NULL
                   ORDER BY o.created_at DESC LIMIT ?""",
                (namespace, limit),
            ).fetchall()

    if not rows:
        return (
            f"No outputs found in workspace '{namespace}'. "
            "Run an agent first and save_output will store results here."
        )

    return f"{len(rows)} most recent output(s) in this workspace:\n\n" + _format_output_list(rows)


def _get_agent_runs(namespace: str, hours: int = 24, limit: int = 20, agent_name: str = "") -> str:
    from core.database import get_db

    with get_db() as conn:
        if agent_name:
            rows = conn.execute(
                """SELECT r.id, a.display_name, a.name, r.status,
                          r.tokens_in, r.tokens_out, r.duration_ms,
                          r.created_at, r.completed_at, r.input, r.error
                   FROM agent_runs r
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE r.namespace = ?
                     AND LOWER(COALESCE(a.name,'')) LIKE LOWER(?)
                     AND r.deleted_at IS NULL
                     AND r.created_at >= datetime('now', ? || ' hours')
                   ORDER BY r.created_at DESC LIMIT ?""",
                (namespace, f"%{agent_name}%", f"-{hours}", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.id, a.display_name, a.name, r.status,
                          r.tokens_in, r.tokens_out, r.duration_ms,
                          r.created_at, r.completed_at, r.input, r.error
                   FROM agent_runs r
                   LEFT JOIN agents a ON a.id = r.agent_id
                   WHERE r.namespace = ?
                     AND r.deleted_at IS NULL
                     AND r.created_at >= datetime('now', ? || ' hours')
                   ORDER BY r.created_at DESC LIMIT ?""",
                (namespace, f"-{hours}", limit),
            ).fetchall()

    if not rows:
        return f"No agent runs found in the last {hours}h for workspace '{namespace}'."

    lines = [f"## Agent runs — last {hours}h ({len(rows)} found)\n"]
    for r in rows:
        # Extract user prompt from input JSON
        prompt_preview = ""
        try:
            inp = json.loads(r["input"] or "{}")
            prompt_preview = (inp.get("prompt") or "")[:120]
        except Exception:
            pass

        agent_label = r["display_name"] or r["name"] or "unknown-agent"
        ts = (r["created_at"] or "")[:16]
        duration = f"{r['duration_ms']}ms" if r["duration_ms"] else "—"
        tokens = f"{r['tokens_in'] or 0}in + {r['tokens_out'] or 0}out"
        status = r["status"] or "unknown"

        lines.append(f"**[{ts}] {agent_label}** — {status} ({duration}, {tokens})")
        if prompt_preview:
            lines.append(f"  User asked: \"{prompt_preview}{'...' if len(prompt_preview)==120 else ''}\"")
        if status == "failed" and r["error"]:
            lines.append(f"  Error: {r['error'][:100]}")
        lines.append("")

    return "\n".join(lines)


def _get_git_log(hours: int = 24, limit: int = 20) -> str:
    import subprocess, shutil
    from pathlib import Path

    # Find repo root — walk up from this file
    repo_root = Path(__file__).resolve()
    for _ in range(6):
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    else:
        return "Git repository not found — cannot retrieve commit history."

    if not shutil.which("git"):
        return "git not found on PATH — cannot retrieve commit history."

    try:
        since = f"{hours} hours ago"
        result = subprocess.run(
            ["git", "log", f"--since={since}", f"--max-count={limit}",
             "--pretty=format:%h|%ai|%an|%s"],
            cwd=str(repo_root),
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return f"No git commits in the last {hours}h."

        lines = [f"## Git commits — last {hours}h\n"]
        for line in raw.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                sha, ts, author, msg = parts
                lines.append(f"**{ts[:16]}** `{sha}` — {msg} _(by {author})_")
            else:
                lines.append(line)

        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "git log timed out."
    except Exception as e:
        return f"git log error: {e}"


def _format_output_list(rows) -> str:
    lines = []
    for r in rows:
        content_preview = (r["content"] or "").replace("\n", " ")[:250]
        lines.append(f"**ID:** `{r['id']}`")
        lines.append(f"**Title:** {r['title']}")
        lines.append(f"**Agent:** {r['src_agent'] or 'unknown'}")
        lines.append(f"**Date:** {(r['created_at'] or '')[:16]}")
        lines.append(f"**Preview:** {content_preview}...")
        lines.append("")
    lines.append("Call `get_output(output_id)` with the ID above to retrieve full content.")
    return "\n".join(lines)
