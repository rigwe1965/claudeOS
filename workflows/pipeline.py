"""Workflow Pipeline — executes a workflow definition step by step.

Each step:
1. Resolves prompt template (injects prior step outputs + context)
2. Dispatches to agent via dispatcher
3. Waits for completion (block=True)
4. Logs step result
5. On failure: marks run failed, stops pipeline

Called by scheduler (automated) or API (manual trigger).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from core.database import get_db
from core.utils import new_id, utcnow_str
from workflows.schemas import WorkflowDefinition, WorkflowStepLog

logger = logging.getLogger("claudeos.workflows.pipeline")


def run(
    workflow: WorkflowDefinition,
    run_id: str,
    context: dict,
    triggered_by: str = "scheduler",
) -> dict:
    """Execute all steps of a workflow. Returns result summary."""
    from agents.dispatcher import dispatch
    from agents.schemas import AgentDispatchRequest

    started = time.monotonic()
    namespace = context.get("namespace") or workflow.namespace
    step_logs: list[dict] = []
    step_outputs: dict[str, str] = {}   # step_id → output text

    # Write initial "running" status without steps_log (buffered until done/fail)
    _update_run(run_id, "running")
    logger.info("Workflow %s starting (run=%s, ns=%s)", workflow.name, run_id[:8], namespace)

    for step in workflow.steps:
        # Check dependencies
        for dep in step.depends_on:
            dep_log = next((s for s in step_logs if s["step_id"] == dep), None)
            if dep_log and dep_log["status"] == "failed":
                log = WorkflowStepLog(
                    step_id=step.step_id,
                    agent_name=step.agent_name,
                    status="skipped",
                    error=f"Dependency {dep} failed",
                )
                step_logs.append(log.model_dump())
                # Buffered — do not write to DB yet
                continue

        # Resolve prompt template
        prompt = _resolve_template(step.prompt_template, context, step_outputs)

        # Build dispatch request
        req = AgentDispatchRequest(
            prompt=prompt,
            namespace=namespace,
            context={**step.context, **context, "workflow_run_id": run_id},
            save_output=step.save_output,
            workflow_run_id=run_id,
        )

        step_start = time.monotonic()
        log = WorkflowStepLog(
            step_id=step.step_id,
            agent_name=step.agent_name,
            status="running",
        )
        step_logs.append(log.model_dump())
        # Buffered — do not write to DB mid-step

        try:
            agent_run_id = dispatch(step.agent_name, req, block=True)
            step_duration = int((time.monotonic() - step_start) * 1000)

            # Fetch result
            run_record = _fetch_run_record(agent_run_id)
            status = run_record.get("status", "failed")
            output_text = ""
            tokens_in = run_record.get("tokens_in", 0) or 0
            tokens_out = run_record.get("tokens_out", 0) or 0

            if status == "done":
                out_data = run_record.get("output") or {}
                if isinstance(out_data, str):
                    try:
                        out_data = json.loads(out_data)
                    except Exception:
                        out_data = {"text": out_data}
                output_text = out_data.get("text", "") if isinstance(out_data, dict) else str(out_data)
                step_outputs[step.step_id] = output_text
                log.status = "done"
                log.output_preview = output_text[:300]
                log.tokens_in = tokens_in
                log.tokens_out = tokens_out
                log.duration_ms = step_duration
                log.run_id = agent_run_id
            else:
                error = run_record.get("error", "Agent run failed")
                log.status = "failed"
                log.error = error
                log.duration_ms = step_duration
                _sync_log(step_logs, log)
                if getattr(step, "on_failure", "stop") == "continue":
                    logger.warning("Workflow %s step %s failed (on_failure=continue): %s", workflow.name, step.step_id, error)
                    step_outputs[step.step_id] = ""
                    continue
                _update_run(run_id, "failed", steps_log=step_logs, error=f"Step {step.step_id} failed: {error}")
                logger.error("Workflow %s failed at step %s: %s", workflow.name, step.step_id, error)
                return _result(run_id, "failed", step_logs, started)

        except Exception as e:
            step_duration = int((time.monotonic() - step_start) * 1000)
            log.status = "failed"
            log.error = str(e)
            log.duration_ms = step_duration
            _sync_log(step_logs, log)
            if getattr(step, "on_failure", "stop") == "continue":
                logger.warning("Workflow %s step %s exception (on_failure=continue): %s", workflow.name, step.step_id, e)
                step_outputs[step.step_id] = ""
                continue
            _update_run(run_id, "failed", steps_log=step_logs, error=str(e))
            logger.exception("Workflow %s step %s exception", workflow.name, step.step_id)
            return _result(run_id, "failed", step_logs, started)

        _sync_log(step_logs, log)
        # Buffered — do not write to DB after every successful step
        logger.info(
            "Workflow %s step %s done (%dms, %d+%d tokens)",
            workflow.name, step.step_id, log.duration_ms, log.tokens_in, log.tokens_out,
        )

    # All steps complete — single flush of the full steps_log
    final_output = _compile_output(step_logs, step_outputs)
    _update_run(run_id, "done", steps_log=step_logs, output=final_output)
    _increment_run_count(workflow.name)
    logger.info("Workflow %s complete (run=%s)", workflow.name, run_id[:8])
    return _result(run_id, "done", step_logs, started)


def create_run_record(workflow_id: str, triggered_by: str, context: dict) -> str:
    run_id = new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO workflow_runs (id, workflow_id, status, triggered_by, context, started_at)
               VALUES (?, ?, 'pending', ?, ?, ?)""",
            (run_id, workflow_id, triggered_by, json.dumps(context), utcnow_str()),
        )
    return run_id


def get_run(run_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("context", "steps_log"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


def list_runs(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    conditions = []
    params: list = []
    if workflow_id:
        conditions.append("workflow_id = ?")
        params.append(workflow_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM workflow_runs {where} ORDER BY started_at DESC LIMIT ?", params
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for field in ("context", "steps_log"):
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        result.append(d)
    return result


# ── helpers ──────────────────────────────────────────────────────────────────

def _resolve_template(template: str, context: dict, step_outputs: dict) -> str:
    """Replace {key} placeholders from context and prior step outputs."""
    from datetime import datetime
    merged = {
        "date": datetime.now().strftime("%A, %d %B %Y"),
        **context,
    }
    for step_id, text in step_outputs.items():
        merged[f"output_{step_id}"] = text
        merged["previous_output"] = text   # convenience: always the latest
    try:
        return template.format_map(_SafeDict(merged))
    except Exception:
        return template


class _SafeDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"


def _update_run(
    run_id: str,
    status: str,
    steps_log: Optional[list] = None,
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    now = utcnow_str()
    parts = ["status=?"]
    params: list = [status]
    if steps_log is not None:
        parts.append("steps_log=?")
        params.append(json.dumps(steps_log))
    if output is not None:
        parts.append("output=?")
        params.append(output)
    if error is not None:
        parts.append("error=?")
        params.append(error)
    if status in ("done", "failed"):
        parts.append("completed_at=?")
        params.append(now)
    params.append(run_id)
    with get_db() as conn:
        conn.execute(f"UPDATE workflow_runs SET {', '.join(parts)} WHERE id=?", params)


def _sync_log(step_logs: list[dict], log: WorkflowStepLog) -> None:
    for i, entry in enumerate(step_logs):
        if entry["step_id"] == log.step_id:
            step_logs[i] = log.model_dump()
            return
    step_logs.append(log.model_dump())


def _fetch_run_record(agent_run_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (agent_run_id,)).fetchone()
    if not row:
        return {"status": "failed", "error": "run record not found"}
    d = dict(row)
    for field in ("input", "output"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


def _compile_output(step_logs: list[dict], step_outputs: dict) -> str:
    parts = []
    for log in step_logs:
        if log["status"] == "done" and log.get("step_id") in step_outputs:
            parts.append(f"## {log['agent_name']}\n\n{step_outputs[log['step_id']]}")
    return "\n\n---\n\n".join(parts)


def _increment_run_count(workflow_name: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE workflows SET run_count = run_count + 1, last_run_at = ? WHERE name = ?",
            (utcnow_str(), workflow_name),
        )


def _result(run_id: str, status: str, step_logs: list[dict], started: float) -> dict:
    duration = int((time.monotonic() - started) * 1000)
    with get_db() as conn:
        conn.execute(
            "UPDATE workflow_runs SET duration_ms=? WHERE id=?", (duration, run_id)
        )
    return {"run_id": run_id, "status": status, "steps": step_logs, "duration_ms": duration}
