"""Agent Dispatcher — routes task requests to the correct agent executor.

Called by:
- API routes (user-triggered)
- Workflow pipeline steps (automated)

Returns run_id immediately. Caller polls GET /agents/runs/{run_id} for status.
Execution is synchronous within the process — use threading for non-blocking dispatch.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from agents import registry, executor
from agents.schemas import AgentDispatchRequest, AgentRunCreate
from core.utils import new_id

logger = logging.getLogger("claudeos.agents.dispatcher")


def dispatch(
    agent_name: str,
    request: AgentDispatchRequest,
    block: bool = False,
) -> str:
    """Dispatch an agent run. Returns run_id.

    Args:
        agent_name: registered agent name
        request:    dispatch request (prompt, namespace, context, etc.)
        block:      if True, wait for completion before returning
    """
    agent = registry.get_by_name(agent_name)
    if not agent:
        raise ValueError(f"Agent not found: {agent_name}")
    if not agent.enabled:
        raise ValueError(f"Agent is disabled: {agent_name}")

    # Namespace lock enforcement
    if agent.namespace_lock and request.namespace != agent.namespace_lock:
        raise PermissionError(
            f"Agent {agent_name} is locked to namespace '{agent.namespace_lock}', "
            f"got '{request.namespace}'"
        )

    # Create pending run record
    run_id = executor.create_run_record(
        agent_id=agent.id,
        namespace=request.namespace,
        prompt=request.prompt,
        context=request.context,
        session_id=request.session_id,
        triggered_by=request.triggered_by if hasattr(request, "triggered_by") else "user",
        workflow_run_id=request.workflow_run_id if hasattr(request, "workflow_run_id") else None,
    )

    # Capture correlation ID from Flask request context before leaving the request thread
    try:
        from flask import g as _flask_g
        correlation_id = getattr(_flask_g, "request_id", None)
    except RuntimeError:
        correlation_id = None
    if not correlation_id:
        correlation_id = new_id()

    logger.info("Dispatching %s (run=%s, ns=%s, cid=%s)",
                agent_name, run_id[:8], request.namespace, correlation_id[:8])

    def _run():
        logger.info("Agent thread start: run=%s agent=%s cid=%s", run_id[:8], agent_name, correlation_id[:8])
        try:
            executor.execute(
                run_id=run_id,
                agent_name=agent.name,
                system_prompt=agent.system_prompt,
                prompt=request.prompt,
                namespace=request.namespace,
                model=agent.model,
                max_tokens=agent.max_tokens,
                temperature=agent.temperature,
                context=request.context,
                session_id=request.session_id,
                triggered_by=request.triggered_by,
                workflow_run_id=request.workflow_run_id,
                save_output=request.save_output,
                agent_id=agent.id,
                tools=agent.tools,
            )
        except Exception as exc:
            logger.exception("Agent thread crashed: run=%s agent=%s cid=%s error=%s",
                             run_id[:8], agent_name, correlation_id[:8], exc)
            try:
                executor._update_run_status(run_id, "failed")
            except Exception:
                pass

    if block:
        _run()
    else:
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    return run_id


def get_run(run_id: str) -> Optional[dict]:
    """Fetch a run record by ID."""
    from core.database import get_db
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    import json
    d = dict(row)
    for field in ("input", "output"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


def list_runs(
    agent_id: Optional[str] = None,
    namespace: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    """Returns (runs, total_count). total_count ignores limit/offset."""
    from core.database import get_db
    import json
    conditions = []
    params: list = []
    if not include_deleted:
        conditions.append("r.deleted_at IS NULL")
    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)
    if namespace:
        conditions.append("r.namespace = ?")
        params.append(namespace)
    if status:
        conditions.append("r.status = ?")
        params.append(status)
    if since:
        conditions.append("r.created_at >= ?")
        params.append(since)
    if until:
        conditions.append("r.created_at <= ?")
        params.append(until)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM agent_runs r {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT r.*, a.name AS agent_name, a.display_name AS agent_display_name
                FROM agent_runs r
                LEFT JOIN agents a ON a.id = r.agent_id
                {where} ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for field in ("input", "output"):
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        result.append(d)
    return result, total


def cancel_run(run_id: str) -> bool:
    """Mark a pending/running run as cancelled."""
    from core.database import get_db
    from core.utils import utcnow_str
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE agent_runs SET status='cancelled', completed_at=? WHERE id=? AND status IN ('pending','running')",
            (utcnow_str(), run_id),
        )
    return cursor.rowcount > 0
