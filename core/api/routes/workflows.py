"""Workflow Engine REST API routes.

Phase 12.1: Webhook-triggered workflow activation.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from flask import Blueprint, jsonify, request

from flask import g
from core.auth import require_auth, require_role, effective_namespace, is_scoped
from core.utils import utcnow_str
from core.api.limiter import limiter

workflows_bp = Blueprint("workflows", __name__, url_prefix="/api/v1/workflows")

_WORKFLOW_ROLES = ("admin", "operator", "client", "viewer")  # staff is tickets-only; unknown roles fail closed


def require_api_key(f):
    """Authenticate, then reject roles with no workflow access (webhook trigger doesn't use this)."""
    return require_auth(require_role(*_WORKFLOW_ROLES)(f))


@workflows_bp.get("")
@require_api_key
@require_role("admin", "operator", "client", "viewer")
def list_workflows():
    from workflows.registry import list_workflows as _list
    trigger_type = request.args.get("trigger_type")
    namespace = request.args.get("namespace")
    enabled_only = request.args.get("enabled", "true").lower() == "true"
    workflows = _list(trigger_type=trigger_type, namespace=namespace, enabled_only=enabled_only)
    workflows = [wf for wf in workflows if _wf_visible(wf)]
    return jsonify([_wf_summary(wf) for wf in workflows])


@workflows_bp.get("/<name>")
@require_api_key
@require_role("admin", "operator", "client", "viewer")
def get_workflow(name: str):
    from workflows.registry import get_by_name
    wf = get_by_name(name)
    if not wf or not _wf_visible(wf):
        return jsonify({"error": "Workflow not found"}), 404
    if is_scoped():
        return jsonify(_wf_summary(wf))
    return jsonify(_wf_detail(wf))


@workflows_bp.post("/<name>/run")
@require_api_key
@require_role("admin", "operator")
@limiter.limit("20 per minute")
def trigger_workflow(name: str):
    """Trigger a workflow run immediately. Returns run_id."""
    from workflows.registry import get_by_name
    from workflows import pipeline

    wf = get_by_name(name)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    if not wf.enabled:
        return jsonify({"error": "Workflow is disabled"}), 400

    body = request.get_json(silent=True) or {}
    context = body.get("context", {})
    namespace = body.get("namespace") or wf.namespace
    context["namespace"] = namespace

    run_id = pipeline.create_run_record(wf.id, "user", context)

    def _run():
        pipeline.run(wf, run_id, context, triggered_by="user")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({"run_id": run_id, "status": "running", "workflow": name}), 202


@workflows_bp.get("/<name>/runs")
@require_api_key
@require_role("admin", "operator", "client", "viewer")
def get_workflow_runs(name: str):
    from workflows.registry import get_by_name
    from workflows.pipeline import list_runs
    wf = get_by_name(name)
    if not wf or not _wf_visible(wf):
        return jsonify({"error": "Workflow not found"}), 404
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer"}), 400
    status = request.args.get("status")
    runs = list_runs(workflow_id=wf.id, status=status, limit=limit)
    return jsonify([r for r in runs if _run_visible(r)])


@workflows_bp.get("/runs/all")
@require_api_key
@require_role("admin", "operator", "client", "viewer")
def list_all_runs():
    from workflows.pipeline import list_runs
    try:
        limit = min(int(request.args.get("limit", 30)), 200)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer"}), 400
    status = request.args.get("status")
    if is_scoped():
        runs = [r for r in list_runs(status=status, limit=200) if _run_visible(r)][:limit]
    else:
        runs = list_runs(status=status, limit=limit)
    return jsonify(runs)


@workflows_bp.get("/runs/<run_id>")
@require_api_key
@require_role("admin", "operator", "client", "viewer")
def get_run(run_id: str):
    from workflows.pipeline import get_run as _get_run
    run = _get_run(run_id)
    if not run or not _run_visible(run):
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run)


@workflows_bp.delete("/runs/<run_id>")
@require_api_key
@require_role("admin", "operator")
def delete_run(run_id: str):
    from core.database import get_db
    with get_db() as conn:
        conn.execute("UPDATE outputs SET workflow_run_id=NULL WHERE workflow_run_id=?", (run_id,))
        result = conn.execute("DELETE FROM workflow_runs WHERE id=?", (run_id,))
    if result.rowcount == 0:
        return jsonify({"error": "Run not found"}), 404
    return jsonify({"deleted": run_id})


@workflows_bp.delete("/runs")
@require_api_key
@require_role("admin", "operator")
def bulk_delete_runs():
    body = request.get_json(silent=True) or {}
    ids = body.get("ids", [])
    if not ids:
        return jsonify({"error": "No ids provided"}), 400
    if len(ids) > 200:
        return jsonify({"error": "Maximum 200 ids per bulk delete"}), 422
    from core.database import get_db
    placeholders = ",".join("?" * len(ids))
    with get_db() as conn:
        conn.execute(f"UPDATE outputs SET workflow_run_id=NULL WHERE workflow_run_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM workflow_runs WHERE id IN ({placeholders})", ids)
    return jsonify({"deleted": len(ids)})


@workflows_bp.get("/scheduler/jobs")
@require_api_key
@require_role("admin", "operator")
def list_scheduler_jobs():
    from workflows.scheduler import list_scheduled_jobs
    return jsonify(list_scheduled_jobs())


@workflows_bp.post("/scheduler/reload")
@require_api_key
@require_role("admin", "operator")
def reload_scheduler():
    """Reload scheduled workflows from DB (after enable/disable changes)."""
    from workflows.scheduler import get_scheduler, _load_scheduled_workflows, list_scheduled_jobs
    sched = get_scheduler()
    if not sched:
        return jsonify({"error": "Scheduler not running"}), 503
    # Remove all workflow jobs
    for job in sched.get_jobs():
        if job.id.startswith("wf_"):
            sched.remove_job(job.id)
    _load_scheduled_workflows()
    return jsonify({"status": "reloaded", "jobs": list_scheduled_jobs()})


@workflows_bp.patch("/<name>")
@require_api_key
@require_role("admin", "operator")
def update_workflow(name: str):
    """Enable/disable a workflow."""
    from workflows.registry import get_by_name, upsert
    from workflows.scheduler import schedule_workflow, unschedule_workflow
    wf = get_by_name(name)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        wf.enabled = bool(body["enabled"])
        upsert(wf)
        if wf.trigger_type == "schedule":
            if wf.enabled:
                schedule_workflow(wf.name, wf.trigger_spec)
            else:
                unschedule_workflow(wf.name)
    return jsonify(_wf_summary(wf))


# ── Webhook endpoints — Phase 12.1 ───────────────────────────────────────────

@workflows_bp.post("/<name>/webhook/enable")
@require_api_key
@require_role("admin", "operator")
def enable_webhook(name: str):
    """Generate or regenerate a webhook secret for this workflow."""
    from workflows.registry import get_by_name, upsert
    wf = get_by_name(name)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404

    secret = secrets.token_hex(32)
    from core.database import get_db
    with get_db() as conn:
        conn.execute(
            "UPDATE workflows SET webhook_secret=?, webhook_enabled=1 WHERE id=?",
            (secret, wf.id),
        )
    from core.config import get_settings
    port = get_settings().FLASK_PORT
    return jsonify({
        "webhook_enabled": True,
        "webhook_secret": secret,
        "webhook_url": f"http://localhost:{port}/api/v1/workflows/{name}/trigger",
        "usage": "POST to webhook_url with header X-Webhook-Secret: <secret> and JSON body {context: {}}",
    })


@workflows_bp.post("/<name>/webhook/disable")
@require_api_key
@require_role("admin", "operator")
def disable_webhook(name: str):
    from workflows.registry import get_by_name
    wf = get_by_name(name)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    from core.database import get_db
    with get_db() as conn:
        conn.execute(
            "UPDATE workflows SET webhook_secret=NULL, webhook_enabled=0 WHERE id=?",
            (wf.id,),
        )
    return jsonify({"webhook_enabled": False})


@workflows_bp.post("/<name>/trigger")
@limiter.limit("10 per minute")
def webhook_trigger(name: str):
    """Public webhook endpoint — no JWT required, authenticated via X-Webhook-Secret header.

    External systems (GitHub, Stripe, Supabase, n8n, etc.) POST here to fire a workflow.
    Body: {"context": {"key": "value", ...}}
    Header: X-Webhook-Secret: <secret>
    """
    from workflows.registry import get_by_name
    from workflows import pipeline
    from core.database import get_db

    # Lookup workflow + secret
    with get_db() as conn:
        row = conn.execute(
            "SELECT webhook_secret, webhook_enabled FROM workflows WHERE name=?",
            (name,),
        ).fetchone()

    if not row or not row["webhook_enabled"] or not row["webhook_secret"]:
        return jsonify({"error": "Webhook not enabled for this workflow"}), 403

    # Validate secret — guard against empty-string bypass before compare_digest
    provided = request.headers.get("X-Webhook-Secret", "")
    stored = row["webhook_secret"] or ""
    if not provided or not stored or not hmac.compare_digest(provided, stored):
        return jsonify({"error": "Invalid webhook secret"}), 403

    wf = get_by_name(name)
    if not wf or not wf.enabled:
        return jsonify({"error": "Workflow not found or disabled"}), 404

    if request.content_length and request.content_length > 65_536:
        return jsonify({"error": "Request body too large (max 64 KB)"}), 413

    body = request.get_json(silent=True) or {}
    context = body.get("context", {})
    if not isinstance(context, dict):
        context = {}
    context["namespace"] = context.get("namespace") or wf.namespace
    context["trigger_source"] = "webhook"

    run_id = pipeline.create_run_record(wf.id, "webhook", context)

    def _run():
        pipeline.run(wf, run_id, context, triggered_by="webhook")

    threading.Thread(target=_run, daemon=True).start()

    return jsonify({
        "run_id": run_id,
        "workflow": name,
        "status": "running",
        "triggered_by": "webhook",
    }), 202


# ── helpers ───────────────────────────────────────────────────────────────────

def _wf_visible(wf) -> bool:
    """Scoped users only see workflows bound to their own namespace."""
    return not is_scoped() or (wf.namespace is not None and wf.namespace == g.user_namespace)


def _run_visible(run: dict) -> bool:
    if not is_scoped():
        return True
    ctx = run.get("context")
    return isinstance(ctx, dict) and ctx.get("namespace") == g.user_namespace


def _wf_summary(wf) -> dict:
    return {
        "id": wf.id,
        "name": wf.name,
        "display_name": wf.display_name,
        "description": wf.description,
        "trigger_type": wf.trigger_type,
        "trigger_spec": wf.trigger_spec,
        "namespace": wf.namespace,
        "enabled": wf.enabled,
        "step_count": len(wf.steps),
    }


def _wf_detail(wf) -> dict:
    d = _wf_summary(wf)
    d["steps"] = [s.model_dump() for s in wf.steps]
    return d
