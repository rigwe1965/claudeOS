"""Claude API executor — the core of the agent system.

Every agent call goes through here. Responsibilities:
1. Inject namespace memory context (tiered: summary + recent + relevant)
2. Call Claude API — streaming or blocking
3. LLM-as-Judge async quality scoring
4. Log token usage to agent_runs table
5. Auto-save output to Output Manager if save_output=True
6. Support multi-turn conversations (messages list)
7. Support multimodal content (images as base64 blocks)
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Generator, Optional

from core.config import get_settings
from core.database import get_db
from core.utils import new_id, utcnow_str
from memory import engine as memory_engine

logger = logging.getLogger("claudeos.agents.executor")

_client = None  # anthropic.Anthropic — lazy, avoids 4s import at startup


def _sanitize_error(msg: str) -> str:
    """Redact potential API keys / secrets from error strings before logging or returning."""
    import re
    msg = str(msg)[:500]  # hard cap
    # Redact Anthropic key pattern sk-ant-...
    msg = re.sub(r"sk-ant-[A-Za-z0-9\-_]{10,}", "sk-ant-***REDACTED***", msg)
    # Redact any bearer token pattern
    msg = re.sub(r"Bearer\s+[A-Za-z0-9\-_.]{20,}", "Bearer ***REDACTED***", msg)
    return msg
_client_lock = threading.Lock()

# Background pool for fire-and-forget IO: activity log, event log, failure log, eval trigger.
_bg_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="exec-bg")

# Dedicated pool for context building — 4 workers so concurrent agent calls
# never queue behind each other and hit the timeout before work even starts.
_ctx_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="exec-ctx")


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # double-checked locking
                import anthropic
                _client = anthropic.Anthropic(api_key=get_settings().ANTHROPIC_API_KEY)
    return _client


def execute(
    run_id: str,
    agent_name: str,
    system_prompt: str,
    prompt: str,
    namespace: str,
    model: str,
    max_tokens: int,
    temperature: float,
    context: dict,
    session_id: Optional[str],
    triggered_by: str,
    workflow_run_id: Optional[str],
    save_output: bool,
    agent_id: str,
    messages: Optional[list] = None,
    images: Optional[list[dict]] = None,
    tools: Optional[list[str]] = None,
) -> dict:
    """Execute an agent run. Returns result dict with output, tokens, status.

    Args:
        messages: optional list of prior turns [{role, content}] for multi-turn
        images:   optional list of {data: base64_str, media_type: str}
    """
    # Build tiered context injection
    mem_context = _build_memory_context(namespace, prompt)
    system = _build_system_blocks(system_prompt, mem_context, namespace, context)

    # Build messages list (multi-turn support)
    api_messages = _build_messages(prompt, messages, images)

    # Resolve Claude tool definitions from tool name list
    tool_defs = _get_tool_definitions(tools or [])

    # Mark as running
    _update_run_status(run_id, "running")
    start = time.monotonic()

    try:
        import anthropic
        client = _get_client()
        last_exc: Exception = RuntimeError("no attempts made")
        response = None

        import random as _random
        for attempt in range(3):
            try:
                if tool_defs:
                    response, api_messages = _run_with_tools(
                        client, model, max_tokens, temperature, system, api_messages, tool_defs,
                        namespace=namespace, max_loops=5,
                    )
                else:
                    response = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system,
                        messages=api_messages,
                        timeout=120.0,
                    )
                break
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code == 529 and attempt < 2:
                    time.sleep(2 ** attempt + _random.uniform(0, 1))
                    continue
                raise
            except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 ** attempt + _random.uniform(0, 1))
                    continue
                raise
        else:
            raise last_exc

        duration_ms = int((time.monotonic() - start) * 1000)
        # Extract final text (may be in any content block)
        output_text = ""
        for block in (response.content or []):
            if getattr(block, "type", None) == "text":
                output_text = block.text
                break
        if not output_text and response.content:
            output_text = getattr(response.content[0], "text", "")
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        cache_created = getattr(response.usage, "cache_creation_input_tokens", 0) or 0

        output = {
            "text": output_text,
            "model": response.model,
            "stop_reason": response.stop_reason,
        }

        # Save to agent_runs — build input JSON directly (no SELECT round-trip needed)
        import re as _re
        _ctx_sources = _re.findall(r'^##\s+(.+?)$', mem_context or "", _re.MULTILINE)[:5]
        with get_db() as conn:
            updated_input = json.dumps({
                "prompt": prompt,
                "context": context,
                "mem_context": mem_context[:3000] if mem_context else "",
                "context_sources": _ctx_sources,
            })
            conn.execute(
                """UPDATE agent_runs SET
                   input=?, output=?, status='done', tokens_in=?, tokens_out=?,
                   duration_ms=?, completed_at=?
                   WHERE id=?""",
                (updated_input, json.dumps(output), tokens_in, tokens_out, duration_ms, utcnow_str(), run_id),
            )

        # Auto-save to Output Manager
        if save_output and output_text.strip():
            _save_output(
                namespace=namespace,
                agent_run_id=run_id,
                workflow_run_id=workflow_run_id,
                title=f"{agent_name} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                content=output_text,
                agent_name=agent_name,
            )

        # Async LLM-as-Judge evaluation
        _bg_pool.submit(_trigger_eval, run_id, prompt, output_text, mem_context)

        # Auto-activity memory — builds a searchable trail for all agents
        if tokens_out > 100:  # skip trivial/empty runs
            _bg_pool.submit(
                _write_activity_log,
                namespace, agent_name, prompt, output_text,
                tokens_in, tokens_out, duration_ms,
            )

        _log_event("agent_run_complete", namespace, {
            "agent": agent_name,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cache_read": cache_read,
            "cache_created": cache_created,
            "duration_ms": duration_ms,
        })

        logger.info(
            "Agent %s completed in %dms (%d+%d tokens, cache_read=%d cache_created=%d)",
            agent_name, duration_ms, tokens_in, tokens_out, cache_read, cache_created,
        )
        return {
            "status": "done", "output": output,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cache_read": cache_read, "cache_created": cache_created,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        error_msg = _sanitize_error(e)
        logger.error("Agent %s failed: %s", agent_name, error_msg)
        with get_db() as conn:
            conn.execute(
                "UPDATE agent_runs SET status='failed', error=?, duration_ms=?, completed_at=? WHERE id=?",
                (error_msg, duration_ms, utcnow_str(), run_id),
            )
        # Log failure to error_log memory entry for audit trail
        _bg_pool.submit(_log_failure_to_memory, agent_name, namespace, error_msg, run_id)
        return {"status": "failed", "error": error_msg, "duration_ms": duration_ms}


def execute_stream(
    agent_name: str,
    system_prompt: str,
    prompt: str,
    namespace: str,
    model: str,
    max_tokens: int,
    temperature: float,
    context: dict,
    messages: Optional[list] = None,
    images: Optional[list[dict]] = None,
    tools: Optional[list[str]] = None,
) -> Generator[str, None, None]:
    """Streaming version — yields text chunks as they arrive from Claude API.

    If the agent has tools, runs a blocking tool-use pre-search pass first,
    then streams the final synthesis. Yields status markers during pre-search
    so the UI can show a loading indicator.

    Does NOT write to agent_runs (caller manages run_id separately via execute()).
    """
    mem_context = _build_memory_context(namespace, prompt)
    _ctx_degraded = mem_context.startswith(_CTX_DEG_PREFIX)
    if _ctx_degraded:
        mem_context = mem_context[len(_CTX_DEG_PREFIX):]
        yield {"_context_degraded": True}
    system = _build_system_blocks(system_prompt, mem_context, namespace, context)
    api_messages = _build_messages(prompt, messages, images)

    tool_defs = _get_tool_definitions(tools or [])

    # Pre-search phase: run tool loop in background thread, yield keep-alive pings
    # so the SSE connection stays alive during long tool sequences.
    if tool_defs:
        import queue as _queue
        import threading as _threading

        yield "\n\n*Gathering data — this may take up to a minute...*\n\n"

        _done_q: _queue.Queue = _queue.Queue()

        def _run_tools_bg():
            try:
                c = _get_client()
                r, msgs = _run_with_tools(
                    c, model, max_tokens, temperature, system,
                    list(api_messages), tool_defs,
                    namespace=namespace, max_loops=5,
                )
                _done_q.put(("ok", r, msgs))
            except Exception as exc:
                _done_q.put(("err", exc, None))

        _threading.Thread(target=_run_tools_bg, daemon=True).start()

        # Yield a keep-alive ping every 2 s so the HTTP connection never starves
        elapsed = 0
        while True:
            try:
                outcome = _done_q.get(timeout=2)
                break
            except _queue.Empty:
                elapsed += 2
                yield f"*...still working ({elapsed}s)...*\n"

        if outcome[0] == "err":
            logger.warning("Tool pass failed, falling back to direct stream: %s", outcome[1])
            api_messages = _build_messages(prompt, messages, images)
        else:
            _, _response, api_messages = outcome
            api_messages.append({
                "role": "user",
                "content": "Based on everything gathered above, provide your complete, detailed response.",
            })
            yield "\n\n*Synthesising...*\n\n"

    import anthropic
    client = _get_client()

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=api_messages,
        timeout=120.0,
    ) as stream:
        for text_chunk in stream.text_stream:
            yield text_chunk
        final = stream.get_final_message()
    yield {
        "_done": True,
        "tokens_in": final.usage.input_tokens,
        "tokens_out": final.usage.output_tokens,
    }


def create_run_record(
    agent_id: str,
    namespace: str,
    prompt: str,
    context: dict,
    session_id: Optional[str],
    triggered_by: str,
    workflow_run_id: Optional[str],
    status: str = "pending",
) -> str:
    """Insert an agent_run record. Returns run_id.

    Pass status='running' from the streaming path to skip the separate
    _update_run_status('running') call — saves one DB round-trip.
    """
    run_id = new_id()
    input_data = json.dumps({"prompt": prompt, "context": context})
    with get_db() as conn:
        conn.execute(
            """INSERT INTO agent_runs
               (id, agent_id, session_id, namespace, input, status, triggered_by, workflow_run_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, agent_id, session_id, namespace, input_data, status, triggered_by, workflow_run_id, utcnow_str()),
        )
    return run_id


def save_conversation_turn(
    conversation_id: str,
    turn_index: int,
    role: str,
    content: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: Optional[int] = None,
    run_id: Optional[str] = None,
) -> None:
    """Persist a single conversation turn to the DB."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO agent_conversation_turns
               (id, conversation_id, turn_index, role, content, tokens_in, tokens_out, duration_ms, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id(), conversation_id, turn_index, role, content,
             tokens_in, tokens_out, duration_ms, run_id),
        )
        conn.execute(
            "UPDATE agent_conversations SET updated_at=? WHERE id=?",
            (utcnow_str(), conversation_id),
        )


def get_or_create_conversation(
    session_id: str,
    agent_name: str,
    namespace: str,
    username: str = "",
) -> str:
    """Return existing conversation_id for this session+agent, or create new one."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM agent_conversations WHERE session_id=? AND agent_name=?",
            (session_id, agent_name),
        ).fetchone()
        if row:
            return row["id"]
        conv_id = new_id()
        conn.execute(
            """INSERT INTO agent_conversations(id, session_id, agent_name, namespace, username)
               VALUES (?, ?, ?, ?, ?)""",
            (conv_id, session_id, agent_name, namespace, username),
        )
        return conv_id


def get_conversation_turns(conversation_id: str) -> list[dict]:
    """Return all turns for a conversation ordered by turn_index."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT role, content, tokens_in, tokens_out, duration_ms, run_id, created_at
               FROM agent_conversation_turns
               WHERE conversation_id = ?
               ORDER BY turn_index ASC""",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Internal helpers ──────────────────────────────────────────────────────────

_CTX_DEG_PREFIX = "\x00CTX_DEG\x00"


def _build_memory_context(namespace: str, query: str) -> str:
    """Build tiered context with 8s timeout — falls back to flat FTS context if slow/unavailable."""
    try:
        from memory.context_builder import build_context
        fut = _ctx_pool.submit(build_context, namespace, query, 1500)
        return fut.result(timeout=4.0)
    except Exception:
        return _CTX_DEG_PREFIX + memory_engine.get_agent_context(namespace, min_confidence=0.8)


def _build_messages(
    prompt: str,
    prior_messages: Optional[list],
    images: Optional[list[dict]],
) -> list[dict]:
    """Build the messages array for the Claude API call."""
    if prior_messages:
        # Multi-turn: append new user message to history
        messages = list(prior_messages)
    else:
        messages = []

    # Build current user message content
    content: list = []
    if images:
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("media_type", "image/png"),
                    "data": img["data"],
                },
            })
    content.append({"type": "text", "text": prompt})

    messages.append({"role": "user", "content": content if len(content) > 1 else prompt})
    return messages


def _build_system_blocks(base_prompt: str, mem_context: str, namespace: str, extra_context: dict) -> list:
    """Return system prompt as content blocks with cache_control on the stable prefix.

    Block 0 (cached): base agent system prompt — stable across all runs for this agent.
    Block 1 (dynamic): memory context + extra context + namespace/date — changes per call.
    """
    blocks = [
        {
            "type": "text",
            "text": base_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    dynamic_parts = []
    if mem_context:
        dynamic_parts.append(mem_context)
    if extra_context:
        ctx_lines = ["## Additional Context"]
        for k, v in extra_context.items():
            ctx_lines.append(f"- {k}: {v}")
        dynamic_parts.append("\n".join(ctx_lines))
    dynamic_parts.append(f"\n## Operating Context\nNamespace: {namespace}\nDate: {utcnow_str()[:10]}")

    blocks.append({"type": "text", "text": "\n\n".join(dynamic_parts)})
    return blocks


def _write_activity_log(
    namespace: str, agent_name: str, prompt: str,
    output_text: str, tokens_in: int, tokens_out: int, duration_ms: int,
) -> None:
    """Write one activity-log memory entry per completed run.

    Gives all agents a searchable trail of what ran, when, and what was asked.
    Key-based upsert ensures duplicates never accumulate for the same run.
    """
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        prompt_snippet = (prompt or "").strip()[:200]
        output_snippet = (output_text or "").strip()[:300]
        value = (
            f"[ACTIVITY] {agent_name} completed at {ts}\n"
            f"User asked: \"{prompt_snippet}{'...' if len(prompt or '') > 200 else ''}\"\n"
            f"Output summary: {output_snippet}{'...' if len(output_text or '') > 300 else ''}\n"
            f"Tokens: {tokens_in}in + {tokens_out}out | Duration: {duration_ms}ms"
        )
        # Key = agent + minute-level timestamp — prevents duplicates, allows one entry per run
        key = f"activity_log:{agent_name}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        memory_engine.write(
            namespace=namespace,
            category="activity_log",
            key=key,
            value=value,
            source="system",
            tags=["activity_log", agent_name, "auto"],
        )
    except Exception as e:
        logger.warning("Activity log write failed: %s", e)


def _trigger_eval(run_id: str, prompt: str, output_text: str, context: str) -> None:
    """Fire LLM-as-Judge evaluation in background."""
    try:
        from agents.evaluator import evaluate_async
        evaluate_async(run_id, prompt, output_text, context)
    except Exception as e:
        logger.debug("Eval trigger failed: %s", e)


def _log_failure_to_memory(agent_name: str, namespace: str, error_msg: str, run_id: str) -> None:
    """Append agent failure to global error_log memory entry for audit trail."""
    try:
        from core.utils import new_id, utcnow_str
        from core.database import get_db
        ts = utcnow_str()[:16]
        entry = f"[{ts}] {agent_name} (ns={namespace}, run={run_id[:8]}): {error_msg[:200]}"
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, value FROM memory_entries WHERE key='error_log' AND namespace='global' AND archived=0"
            ).fetchone()
            if row:
                combined = row["value"] + f"\n{entry}"
                # Cap at 50,000 chars — trim oldest lines from head to prevent unbounded growth
                if len(combined) > 50000:
                    lines = combined.splitlines()
                    while len("\n".join(lines)) > 50000 and len(lines) > 1:
                        lines.pop(0)
                    combined = "\n".join(lines)
                conn.execute(
                    "UPDATE memory_entries SET value=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (combined, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO memory_entries (id, namespace, category, key, value, confidence, tags, archived, is_consolidated) VALUES (?,?,?,?,?,?,?,0,0)",
                    (new_id(), "global", "context", "error_log", entry, 0.9, "errors,audit"),
                )
    except Exception as ex:
        logger.debug("Failed to log failure to memory: %s", ex)


def _get_tool_definitions(tool_names: list[str]) -> list[dict]:
    """Map agent tool name strings to Claude API tool definitions (web + system tools)."""
    if not tool_names:
        return []
    try:
        from core.tools import get_definitions
        return get_definitions(tool_names)
    except Exception as e:
        logger.warning("Could not load tool definitions: %s", e)
        return []


def _run_with_tools(
    client,
    model: str,
    max_tokens: int,
    temperature: float,
    system: list,
    messages: list,
    tool_defs: list[dict],
    namespace: str = "global",
    max_loops: int = 5,
) -> tuple:
    """Run Claude with tool_use loop. Returns (final_response, updated_messages).

    Loops until stop_reason is 'end_turn' or max_loops reached.
    Each tool_use block is executed and fed back as tool_result.
    Namespace is passed to system tools so they query the correct workspace.
    """
    from core.tools import call_tool

    loop_messages = list(messages)

    for loop_num in range(max_loops):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=loop_messages,
            tools=tool_defs,
            timeout=90.0,
        )

        if response.stop_reason == "end_turn":
            return response, loop_messages

        if response.stop_reason == "tool_use":
            # Convert response content to serialisable dicts for next API call
            assistant_content = []
            tool_results = []

            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif btype == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    logger.info("Tool call: %s(%s)", block.name, list(block.input.keys()))
                    result_text = call_tool(block.name, block.input, namespace=namespace)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            loop_messages.append({"role": "assistant", "content": assistant_content})
            loop_messages.append({"role": "user", "content": tool_results})
        else:
            # Unknown stop reason — return what we have
            return response, loop_messages

    # Max loops reached — if last response was tool_use (no text), force a final
    # text-only call so output_text is never empty and the run can be saved.
    if getattr(response, "stop_reason", None) == "tool_use":
        try:
            final_response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=loop_messages,
                timeout=90.0,
            )
            return final_response, loop_messages
        except Exception as e:
            logger.warning("Tool loop fallback final call failed: %s", e)
    return response, loop_messages


def _update_run_status(run_id: str, status: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE agent_runs SET status=? WHERE id=?", (status, run_id))


def _save_output(
    namespace: str,
    agent_run_id: str,
    workflow_run_id: Optional[str],
    title: str,
    content: str,
    agent_name: str,
) -> None:
    try:
        from outputs.manager import save as save_output
        save_output(
            namespace=namespace,
            title=title,
            content=content,
            output_type="report",
            agent_run_id=agent_run_id,
            workflow_run_id=workflow_run_id,
            tags=[agent_name, namespace],
        )
    except ImportError:
        _save_output_inline(namespace, agent_run_id, title, content, agent_name)
    except Exception as e:
        logger.warning("Failed to save output: %s", e)


def _save_output_inline(namespace: str, agent_run_id: str, title: str, content: str, agent_name: str) -> None:
    output_id = new_id()
    now = utcnow_str()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO outputs
               (id, namespace, agent_run_id, type, title, content, format, tags, size_bytes, created_at, updated_at)
               VALUES (?, ?, ?, 'report', ?, ?, 'markdown', ?, ?, ?, ?)""",
            (
                output_id, namespace, agent_run_id, title, content,
                json.dumps([agent_name, namespace]),
                len(content.encode("utf-8")), now, now,
            ),
        )


def _log_event(event_type: str, namespace: str, payload: dict) -> None:
    _bg_pool.submit(_do_log_event, event_type, namespace, payload)


def _do_log_event(event_type: str, namespace: str, payload: dict) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO system_events(id, event_type, namespace, payload) VALUES (?, ?, ?, ?)",
                (new_id(), event_type, namespace, json.dumps(payload)),
            )
    except Exception as e:
        logger.warning("_log_event failed (%s): %s", event_type, e)
