"""Agent API routes — /api/v1/agents/*

Phase 10.1: SSE streaming endpoint
Phase 12.3: A2A Agent Cards per agent
"""
import json
from flask import Blueprint, Response, jsonify, request, g, stream_with_context

from agents import registry, dispatcher
from agents.schemas import AgentDispatchRequest
from core.auth import require_auth, require_write, effective_namespace, can_access_namespace, is_scoped
from core.utils import utcnow_str
from core.api.limiter import limiter

agents_bp = Blueprint("agents", __name__, url_prefix="/api/v1/agents")


def _agent_dict(a) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "display_name": a.display_name,
        "description": a.description,
        "category": a.category,
        "model": a.model,
        "max_tokens": a.max_tokens,
        "temperature": a.temperature,
        "tools": a.tools,
        "namespace_lock": a.namespace_lock,
        "tags": a.tags,
        "enabled": a.enabled,
        "version": a.version,
    }


@agents_bp.get("")
@require_auth
def list_agents():
    category = request.args.get("category")
    enabled_only = request.args.get("enabled_only", "true").lower() == "true"
    agents = registry.list_agents(category=category, enabled_only=enabled_only)
    return jsonify({"agents": [_agent_dict(a) for a in agents], "count": len(agents)})


@agents_bp.get("/<agent_id>")
@require_auth
def get_agent(agent_id: str):
    agent = registry.get_by_id(agent_id) or registry.get_by_name(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(_agent_dict(agent))


@agents_bp.get("/<agent_name>/.well-known/agent.json")
@require_auth
def agent_card(agent_name: str):
    """A2A Agent Card — Phase 12.3.
    Returns a machine-readable Agent Card per the Agent-to-Agent protocol spec.
    External orchestrators can discover and delegate to ClaudeOS agents via this endpoint.
    """
    agent = registry.get_by_name(agent_name)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    from core.config import get_settings
    settings = get_settings()
    base_url = f"http://127.0.0.1:{settings.FLASK_PORT}/api/v1"

    card = {
        "name": agent.name,
        "displayName": agent.display_name,
        "description": agent.description,
        "version": agent.version,
        "category": agent.category,
        "tags": agent.tags,
        "capabilities": {
            "streaming": True,
            "multiTurn": True,
            "multiModal": True,
        },
        "input": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The task or question for the agent"},
                "namespace": {"type": "string", "description": "Target namespace context"},
                "context": {"type": "object", "description": "Optional key-value context dict"},
                "messages": {"type": "array", "description": "Prior conversation turns for multi-turn"},
            },
            "required": ["prompt"],
        },
        "output": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "model": {"type": "string"},
                "stop_reason": {"type": "string"},
            },
        },
        "endpoints": {
            "run": f"{base_url}/agents/{agent.name}/run",
            "stream": f"{base_url}/agents/{agent.name}/stream",
            "agentCard": f"{base_url}/agents/{agent.name}/.well-known/agent.json",
        },
        "auth": {
            "type": "bearer",
            "description": "JWT Bearer token or X-API-Key header",
        },
        "model": agent.model,
        "namespaceLock": agent.namespace_lock,
        "enabled": agent.enabled,
    }
    return jsonify(card)


@agents_bp.post("/<agent_name>/run")
@require_auth
@require_write
@limiter.limit("30 per minute")
def run_agent(agent_name: str):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    if is_scoped():
        data["namespace"] = effective_namespace(data.get("namespace"))

    try:
        req = AgentDispatchRequest(**data)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    try:
        run_id = dispatcher.dispatch(agent_name, req, block=False)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    return jsonify({
        "run_id": run_id,
        "agent": agent_name,
        "namespace": req.namespace,
        "status": "pending",
        "poll_url": f"/api/v1/agents/runs/{run_id}",
    }), 202


def _parse_stream_inputs():
    """Parse prompt/namespace/context/messages/images/save_output from GET params or POST JSON body."""
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        prompt = (body.get("prompt") or "").strip()
        namespace = body.get("namespace", "global")
        context = body.get("context") or {}
        messages = body.get("messages") or None
        images = body.get("images") or None
        save_output = bool(body.get("save_output", False))
    else:
        prompt = request.args.get("prompt", "").strip()
        namespace = request.args.get("namespace", "global")
        try:
            context = json.loads(request.args.get("context", "{}"))
        except Exception:
            context = {}
        messages_raw = request.args.get("messages")
        try:
            messages = json.loads(messages_raw) if messages_raw else None
        except Exception:
            messages = None
        images = None
        save_output = request.args.get("save_output", "false").lower() == "true"
    if is_scoped():
        namespace = effective_namespace(namespace)
    if not isinstance(context, dict):
        context = {}
    if len(json.dumps(context)) > 10_240:
        from flask import abort
        abort(422, description="context exceeds 10KB limit")
    return prompt, namespace, context, messages, images, save_output


@agents_bp.route("/<agent_name>/stream", methods=["GET", "POST"])
@require_auth
@require_write
@limiter.limit("20 per minute")
def stream_agent(agent_name: str):
    """SSE streaming endpoint — Phase 10.1 + 13.2 (image support via POST).

    GET:  query params (prompt, namespace, context, messages)
    POST: JSON body (prompt, namespace, context, messages, images)

    SSE event format:
        data: {"type": "token", "text": "..."}
        data: {"type": "done", "tokens_in": N, "tokens_out": N}
        data: {"type": "error", "message": "..."}
    """
    prompt, namespace, context, messages, images, save_output = _parse_stream_inputs()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    agent = registry.get_by_name(agent_name)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    if not agent.enabled:
        return jsonify({"error": "Agent is disabled"}), 400

    # H3: Enforce namespace lock — same guard as run_agent via dispatcher
    if agent.namespace_lock and namespace != agent.namespace_lock:
        return jsonify({"error": f"Agent locked to namespace '{agent.namespace_lock}'"}), 403

    # Create run record so streaming runs appear in history + observability
    # status='running' directly — skips a separate UPDATE round-trip
    import time as _time
    from agents.executor import create_run_record, _trigger_eval, _bg_pool
    from core.database import get_db
    run_id = create_run_record(
        agent_id=agent.id,
        namespace=namespace,
        prompt=prompt,
        context=context,
        session_id=None,
        triggered_by="user",
        workflow_run_id=None,
        status="running",
    )

    def _generate():
        full_text = []
        start = _time.monotonic()
        _run_completed = False
        try:
            from agents.executor import execute_stream
            for chunk in execute_stream(
                agent_name=agent.name,
                system_prompt=agent.system_prompt,
                prompt=prompt,
                namespace=namespace,
                model=agent.model,
                max_tokens=agent.max_tokens,
                temperature=agent.temperature,
                context=context,
                messages=messages,
                images=images,
                tools=agent.tools,
            ):
                if isinstance(chunk, dict) and chunk.get("_done"):
                    tokens_in = chunk["tokens_in"]
                    tokens_out = chunk["tokens_out"]
                    duration_ms = int((_time.monotonic() - start) * 1000)
                    text = "".join(full_text)
                    import re as _re
                    _clean_text = _re.sub(
                        r'\*\.\.\.still working \(\d+s\)\.\.\.\*\n?'
                        r'|\n*\*Gathering data[^\n*]*\*\n*'
                        r'|\n*\*Synthesising\.\.\.\*\n*',
                        '', text
                    ).strip()
                    output = {"text": _clean_text, "model": agent.model, "stop_reason": "end_turn"}
                    with get_db() as conn:
                        conn.execute(
                            """UPDATE agent_runs SET output=?, status='done', tokens_in=?,
                               tokens_out=?, duration_ms=?, completed_at=? WHERE id=?""",
                            (json.dumps(output), tokens_in, tokens_out,
                             duration_ms, utcnow_str(), run_id),
                        )
                    _run_completed = True
                    _bg_pool.submit(_trigger_eval, run_id, prompt, _clean_text, "")
                    if save_output and _clean_text.strip():
                        from agents.executor import _save_output as _do_save
                        from datetime import datetime, timezone
                        import threading as _threading
                        _threading.Thread(
                            target=_do_save,
                            args=(
                                namespace, run_id, None,
                                f"{agent.name} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                                _clean_text, agent.name,
                            ),
                            daemon=True,
                        ).start()
                    yield f"data: {json.dumps({'type': 'done', 'run_id': run_id, 'tokens_in': tokens_in, 'tokens_out': tokens_out})}\n\n".encode("utf-8")
                elif isinstance(chunk, dict) and chunk.get("_context_degraded"):
                    yield f"data: {json.dumps({'type': 'context_degraded'})}\n\n".encode("utf-8")
                else:
                    full_text.append(chunk)
                    payload = json.dumps({"type": "token", "text": chunk})
                    yield f"data: {payload}\n\n".encode("utf-8")
        except Exception as e:
            duration_ms = int((_time.monotonic() - start) * 1000)
            from agents.executor import _sanitize_error
            _safe_err = _sanitize_error(e)
            with get_db() as conn:
                conn.execute(
                    "UPDATE agent_runs SET status='failed', error=?, duration_ms=?, completed_at=? WHERE id=?",
                    (_safe_err, duration_ms, utcnow_str(), run_id),
                )
            _run_completed = True
            yield f"data: {json.dumps({'type': 'error', 'message': _safe_err})}\n\n".encode("utf-8")
        finally:
            # Guard: if generator exits without completing (client disconnect, unhandled raise),
            # ensure the run is never left stuck in 'running' state.
            if not _run_completed:
                duration_ms = int((_time.monotonic() - start) * 1000)
                with get_db() as conn:
                    conn.execute(
                        "UPDATE agent_runs SET status='failed', error='Stream ended unexpectedly', "
                        "duration_ms=?, completed_at=? WHERE id=? AND status='running'",
                        (duration_ms, utcnow_str(), run_id),
                    )

    return Response(
        stream_with_context(_generate()),
        status=200,
        content_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        direct_passthrough=True,
    )


@agents_bp.get("/runs/<run_id>")
@require_auth
def get_run(run_id: str):
    run = dispatcher.get_run(run_id)
    if not run or not can_access_namespace(run.get("namespace")):
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run)


@agents_bp.get("/<agent_id>/runs")
@require_auth
def list_agent_runs(agent_id: str):
    agent = registry.get_by_id(agent_id) or registry.get_by_name(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer"}), 400
    runs, total = dispatcher.list_runs(
        agent_id=agent.id, namespace=effective_namespace(None), limit=limit
    )
    return jsonify({"runs": runs, "count": len(runs), "total": total})


@agents_bp.post("/runs/<run_id>/cancel")
@require_auth
@require_write
def cancel_run(run_id: str):
    run = dispatcher.get_run(run_id)
    if not run or not can_access_namespace(run.get("namespace")):
        return jsonify({"error": "Run not found or already complete"}), 404
    cancelled = dispatcher.cancel_run(run_id)
    if not cancelled:
        return jsonify({"error": "Run not found or already complete"}), 404
    return jsonify({"cancelled": run_id})


@agents_bp.delete("/runs/<run_id>")
@require_auth
@require_write
def delete_run(run_id: str):
    from core.database import get_db
    run = dispatcher.get_run(run_id)
    if not run or not can_access_namespace(run.get("namespace")):
        return jsonify({"error": "Run not found"}), 404
    from core.utils import utcnow_str
    with get_db() as conn:
        conn.execute(
            "UPDATE agent_runs SET deleted_at = ? WHERE id = ?",
            (utcnow_str(), run_id),
        )
    return jsonify({"deleted": run_id})


@agents_bp.get("/runs")
@require_auth
def list_runs():
    namespace = effective_namespace(request.args.get("namespace"))
    status = request.args.get("status")
    since  = request.args.get("since")   # ISO datetime string e.g. "2026-01-01T00:00:00"
    until  = request.args.get("until")
    limit  = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    runs, total = dispatcher.list_runs(
        namespace=namespace, status=status,
        since=since, until=until, limit=limit, offset=offset,
    )
    return jsonify({"runs": runs, "count": len(runs), "total": total, "offset": offset, "limit": limit})


@agents_bp.get("/<agent_name>/conversations")
@require_auth
def list_conversations(agent_name: str):
    """List multi-turn conversations for an agent — Phase 13.4."""
    namespace = effective_namespace(request.args.get("namespace"))
    limit = min(int(request.args.get("limit", 20)), 100)
    from core.database import get_db
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, session_id, namespace, username, created_at, updated_at
               FROM agent_conversations
               WHERE agent_name=? AND namespace=?
               ORDER BY updated_at DESC LIMIT ?""",
            (agent_name, namespace or "global", limit),
        ).fetchall()
    return jsonify({"conversations": [dict(r) for r in rows], "count": len(rows)})


@agents_bp.get("/<agent_name>/conversations/turns")
@require_auth
def get_latest_conversation_turns(agent_name: str):
    """Return turns from the most recent conversation for (agent, namespace).

    Used by the dashboard to restore chat history after page refresh.
    """
    namespace = effective_namespace(request.args.get("namespace"))
    limit = min(int(request.args.get("limit", 40)), 200)
    from core.database import get_db
    from agents.executor import get_conversation_turns
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM agent_conversations
               WHERE agent_name=? AND namespace=?
               ORDER BY updated_at DESC LIMIT 1""",
            (agent_name, namespace or "global"),
        ).fetchone()
    if not row:
        return jsonify({"turns": [], "conversation_id": None, "count": 0})
    turns = get_conversation_turns(row["id"])
    turns = turns[-limit:]
    return jsonify({"turns": turns, "conversation_id": row["id"], "count": len(turns)})
