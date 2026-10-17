"""APScheduler wrapper — manages cron/interval jobs for all enabled workflows.

Start: call init_scheduler() at Flask app startup.
Stop:  call shutdown_scheduler() at teardown.

Scheduled workflows with trigger_type='schedule' are auto-loaded from DB.
Manual workflows are only run via API dispatch.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("claudeos.workflows.scheduler")

_scheduler: Optional[BackgroundScheduler] = None
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wf-worker")


def _get_tz() -> str:
    try:
        from core.config import get_settings
        return get_settings().SCHEDULER_TIMEZONE
    except Exception:
        return "Africa/Lagos"


def init_scheduler() -> BackgroundScheduler:
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.running:
            return _scheduler
        from core.config import get_settings
        tz = get_settings().SCHEDULER_TIMEZONE
        _scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
            timezone=tz,
        )
        _scheduler.start()
        logger.info("APScheduler started")
        _load_scheduled_workflows()
        _register_reminder_job(_scheduler)
        _register_sync_job(_scheduler)
        _register_consolidation_job(_scheduler)
        _register_backup_job(_scheduler)
        _register_cleanup_job(_scheduler)
        return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            # Silence APScheduler's internal logger before shutdown to avoid
            # "I/O operation on closed file" stderr noise during test teardown
            import logging as _logging
            aps_log = _logging.getLogger("apscheduler")
            prev_level = aps_log.level
            aps_log.setLevel(_logging.CRITICAL + 1)
            try:
                _scheduler.shutdown(wait=False)
            finally:
                aps_log.setLevel(prev_level)
        _scheduler = None


def get_scheduler() -> Optional[BackgroundScheduler]:
    return _scheduler


def schedule_workflow(workflow_name: str, trigger_spec: dict) -> bool:
    """Add or replace a scheduled job for a workflow."""
    sched = get_scheduler()
    if not sched:
        logger.warning("Scheduler not running — cannot schedule %s", workflow_name)
        return False

    trigger = _build_trigger(trigger_spec)
    if not trigger:
        logger.warning("Unknown trigger spec for %s: %s", workflow_name, trigger_spec)
        return False

    job_id = f"wf_{workflow_name}"
    # Remove existing job if present
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    sched.add_job(
        _run_workflow_job,
        trigger=trigger,
        id=job_id,
        name=workflow_name,
        args=[workflow_name],
        replace_existing=True,
    )
    logger.info("Scheduled %s → %s", workflow_name, trigger_spec)
    return True


def unschedule_workflow(workflow_name: str) -> bool:
    sched = get_scheduler()
    if not sched:
        return False
    job_id = f"wf_{workflow_name}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        logger.info("Unscheduled %s", workflow_name)
        return True
    return False


def list_scheduled_jobs() -> list[dict]:
    sched = get_scheduler()
    if not sched:
        return []
    jobs = []
    for job in sched.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "job_id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })
    return jobs


def trigger_now(workflow_name: str, context: dict = None) -> Optional[str]:
    """Fire a workflow immediately outside its schedule. Returns run_id."""
    return _run_workflow_job(workflow_name, context=context or {})


# ── internals ────────────────────────────────────────────────────────────────

def _load_scheduled_workflows() -> None:
    """Load all enabled scheduled workflows from DB and register them."""
    try:
        from workflows.registry import list_workflows
        workflows = list_workflows(trigger_type="schedule", enabled_only=True)
        for wf in workflows:
            schedule_workflow(wf.name, wf.trigger_spec)
        logger.info("Loaded %d scheduled workflows", len(workflows))
    except Exception as e:
        logger.error("Failed to load scheduled workflows: %s", e)


def _build_trigger(spec: dict):
    """Build APScheduler trigger from spec dict."""
    t = spec.get("type", "")
    if t == "cron":
        return CronTrigger(
            day_of_week=spec.get("day_of_week", "*"),
            hour=spec.get("hour", 0),
            minute=spec.get("minute", 0),
            timezone=spec.get("timezone") or _get_tz(),
        )
    if t == "interval":
        return IntervalTrigger(
            hours=spec.get("hours", 0),
            minutes=spec.get("minutes", 0),
            seconds=spec.get("seconds", 0),
        )
    return None


def _register_reminder_job(sched: BackgroundScheduler) -> None:
    """Register the email reminder polling job (every 2 minutes)."""
    sched.add_job(
        _run_reminder_job,
        trigger=IntervalTrigger(minutes=2),
        id="claudeos_reminder_notifications",
        name="Reminder Email Notifications",
        replace_existing=True,
    )
    logger.info("Reminder notification job registered (every 2 min)")


def _run_reminder_job() -> None:
    try:
        from notifications.reminder_job import run
        sent = run()
        if sent:
            logger.info("Reminder job: sent %d notification(s)", sent)
    except Exception as e:
        logger.error("Reminder job error: %s", e)


def _register_sync_job(sched: BackgroundScheduler) -> None:
    """Register the Supabase auto-sync job if credentials are configured."""
    try:
        from core.config import get_settings
        settings = get_settings()
        if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY):
            logger.info("Supabase not configured — auto-sync job skipped")
            return
        interval_min = getattr(settings, "SYNC_INTERVAL_MIN", 15)
        sched.add_job(
            _run_sync_job,
            trigger=IntervalTrigger(minutes=interval_min),
            id="claudeos_supabase_sync",
            name="Supabase Auto-Sync",
            replace_existing=True,
        )
        logger.info("Auto-sync job registered (every %d min)", interval_min)
    except Exception as e:
        logger.warning("Could not register sync job: %s", e)


def _run_sync_job() -> None:
    """Background sync job entry point."""
    try:
        from sync.engine import push_all
        result = push_all()
        logger.info(
            "Auto-sync complete: pushed=%d failed=%d (%dms)",
            result.total_pushed, result.total_failed, result.duration_ms,
        )
    except Exception as e:
        logger.error("Auto-sync job error: %s", e)


def _register_consolidation_job(sched: BackgroundScheduler) -> None:
    """Register memory consolidation job — runs every 4 hours."""
    sched.add_job(
        _run_consolidation_job,
        trigger=IntervalTrigger(hours=4),
        id="claudeos_memory_consolidation",
        name="Memory Consolidation",
        replace_existing=True,
    )
    logger.info("Memory consolidation job registered (every 4h)")


def _run_consolidation_job() -> None:
    try:
        from memory.consolidator import run_consolidation
        stats = run_consolidation()
        logger.info(
            "Memory consolidation: %d namespaces, %d clusters, %d archived → %d created",
            stats.get("namespaces_processed", 0), stats.get("clusters_found", 0),
            stats.get("entries_archived", 0), stats.get("entries_created", 0),
        )
    except Exception as e:
        logger.error("Memory consolidation job error: %s", e)


def _register_backup_job(sched: BackgroundScheduler) -> None:
    """Register daily SQLite backup job — runs at 02:00 local time."""
    sched.add_job(
        _run_backup_job,
        trigger=CronTrigger(hour=2, minute=0, timezone=_get_tz()),
        id="claudeos_db_backup",
        name="Daily DB Backup",
        replace_existing=True,
    )
    logger.info("Daily DB backup job registered (02:00 %s)", _get_tz())


def _run_backup_job() -> None:
    try:
        from core.backup import create_backup
        result = create_backup()
        if result["ok"]:
            logger.info(
                "DB backup complete: %s (%d bytes), pruned=%d",
                result["file"], result["size_bytes"], result["pruned"],
            )
        else:
            logger.error("DB backup failed: %s", result.get("error"))
    except Exception as e:
        logger.error("Backup job error: %s", e)


def _register_cleanup_job(sched: BackgroundScheduler) -> None:
    """M2: Weekly DB cleanup — removes old runs/audit rows, reclaims disk space."""
    sched.add_job(
        _run_cleanup_job,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=_get_tz()),
        id="claudeos_db_cleanup",
        name="Weekly DB Cleanup",
        replace_existing=True,
    )
    logger.info("Weekly DB cleanup job registered (Sun 03:00 %s)", _get_tz())


def _run_cleanup_job() -> None:
    """Delete records older than 90 days, then incrementally reclaim disk space."""
    try:
        from core.database import get_db
        with get_db() as conn:
            r1 = conn.execute(
                "DELETE FROM agent_runs WHERE created_at < datetime('now', '-90 days') AND deleted_at IS NOT NULL"
            )
            r2 = conn.execute(
                "DELETE FROM auth_events WHERE created_at < datetime('now', '-90 days')"
            )
            r3 = conn.execute(
                "DELETE FROM workflow_runs WHERE created_at < datetime('now', '-90 days')"
            )
            logger.info(
                "DB cleanup: agent_runs=%d auth_events=%d workflow_runs=%d deleted",
                r1.rowcount, r2.rowcount, r3.rowcount,
            )
            # Incremental vacuum — releases up to 200 pages without exclusive lock
            conn.execute("PRAGMA incremental_vacuum(200)")
    except Exception as e:
        logger.error("DB cleanup job error: %s", e)


def _run_workflow_job(workflow_name: str, context: dict = None) -> Optional[str]:
    """APScheduler job entry point. Runs pipeline in caller thread."""
    from workflows import registry, pipeline

    context = context or {}
    wf = registry.get_by_name(workflow_name)
    if not wf:
        logger.error("Scheduled workflow not found: %s", workflow_name)
        return None
    if not wf.enabled:
        logger.info("Skipping disabled workflow: %s", workflow_name)
        return None

    run_id = pipeline.create_run_record(wf.id, "scheduler", context)
    from core.utils import new_id as _new_id
    correlation_id = _new_id()
    logger.info("Dispatching scheduled workflow %s (run=%s, cid=%s) to thread pool",
                workflow_name, run_id[:8], correlation_id[:8])

    def _execute():
        logger.info("Workflow thread start: run=%s wf=%s cid=%s", run_id[:8], workflow_name, correlation_id[:8])
        try:
            pipeline.run(wf, run_id, context, triggered_by="scheduler")
            logger.info("Workflow thread done: run=%s wf=%s cid=%s", run_id[:8], workflow_name, correlation_id[:8])
        except Exception as e:
            logger.exception("Scheduled workflow %s run=%s cid=%s failed: %s",
                             workflow_name, run_id[:8], correlation_id[:8], e)

    _pool.submit(_execute)
    return run_id
