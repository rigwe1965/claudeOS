"""System routes: /health, /system/status, /system/stats, /system/events."""
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging
from flask import Blueprint, jsonify, request

from core.config import get_settings
from core.database import get_db
from core.utils import utcnow_str
from core.auth import require_auth, effective_namespace
from core.api.limiter import limiter

_log = logging.getLogger("claudeos.system")
system_bp = Blueprint("system", __name__, url_prefix="/api/v1")

# Record the moment this module is imported — used as server process start time
import time as _time
_SERVER_START: float = _time.time()

# Cache ChromaDB health result — prevents a 200-800ms PersistentClient init on every status poll
_chroma_cache: dict = {}
_CHROMA_CACHE_TTL = 30.0  # seconds


def _chromadb_probe(path: str) -> dict:
    """Probe ChromaDB via the shared singleton — cached 30s to avoid blocking Overview page."""
    import time
    cached = _chroma_cache.get("result")
    if cached and time.monotonic() < _chroma_cache.get("expiry", 0):
        return cached
    try:
        from memory import vector_store
        vector_store._init()
        if vector_store._client is None:
            result = {"status": "error", "path": path, "error": "client not initialized"}
        else:
            vector_store._client.heartbeat()
            result = {"status": "ok", "path": path}
    except Exception:
        result = {"status": "error", "path": path, "error": "unavailable"}
    _chroma_cache["result"] = result
    _chroma_cache["expiry"] = time.monotonic() + _CHROMA_CACHE_TTL
    return result


@system_bp.get("/health")
def health():
    s = get_settings()
    return jsonify({
        "status": "ok",
        "version": s.CLAUDEOS_VERSION,
        "timestamp": utcnow_str(),
    })


@system_bp.get("/system/status")
@require_auth
def status():
    from flask import g as _g
    settings = get_settings()
    db_ok = False
    db_path = str(settings.sqlite_path)
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    is_privileged = getattr(_g, "user_role", "client") in ("admin", "operator")

    base = {
        "status": "ok",
        "version": settings.CLAUDEOS_VERSION,
        "env": settings.CLAUDEOS_ENV,
        "timestamp": utcnow_str(),
    }

    if is_privileged:
        db_size_kb = 0
        if Path(db_path).exists():
            db_size_kb = round(Path(db_path).stat().st_size / 1024, 1)
        base.update({
            "platform": platform.system(),
            "python": platform.python_version(),
            "services": {
                "api": {"status": "ok", "port": settings.FLASK_PORT},
                "database": {"status": "ok" if db_ok else "error", "path": db_path, "size_kb": db_size_kb},
                "chromadb": _chromadb_probe(str(settings.chromadb_path)),
            },
        })
    else:
        base["services"] = {
            "api": {"status": "ok"},
            "database": {"status": "ok" if db_ok else "error"},
            "chromadb": {"status": _chromadb_probe(str(settings.chromadb_path))["status"]},
        }

    return jsonify(base)


@system_bp.get("/system/stats")
@require_auth
def stats():
    ns = effective_namespace(None)
    try:
        with get_db() as conn:
            if ns:
                # Scoped counts — 2 queries instead of 7 sequential round-trips
                rows = conn.execute(
                    """SELECT
                         (SELECT COUNT(*) FROM memory_entries WHERE namespace=?) AS memory_entries,
                         (SELECT COUNT(*) FROM agents WHERE enabled=1)           AS agents,
                         (SELECT COUNT(*) FROM agent_runs WHERE namespace=?)      AS agent_runs,
                         (SELECT COUNT(*) FROM workflows)                         AS workflows,
                         (SELECT COUNT(*) FROM outputs WHERE namespace=?)         AS outputs,
                         (SELECT COUNT(*) FROM projects p
                            JOIN namespaces n ON p.namespace_id=n.id
                            WHERE n.slug=?)                                       AS projects,
                         (SELECT COUNT(*) FROM tickets
                            WHERE namespace=?
                              AND status NOT IN ('resolved','closed','completed')) AS open_tickets""",
                    (ns, ns, ns, ns, ns),
                ).fetchone()
                counts = dict(rows)
            else:
                # Global counts — admin/operator see everything
                tables = ["memory_entries", "agents", "agent_runs", "workflows", "workflow_runs",
                          "outputs", "namespaces", "projects", "system_events"]
                union_sql = " UNION ALL ".join(
                    f"SELECT '{t}' AS tbl, COUNT(*) AS cnt FROM {t}" for t in tables
                )
                rows = conn.execute(union_sql).fetchall()
                counts = {row[0]: row[1] for row in rows}
                counts["open_tickets"] = conn.execute(
                    "SELECT COUNT(*) FROM tickets WHERE status NOT IN ('resolved','closed','completed')"
                ).fetchone()[0]
    except Exception as e:
        _log.exception("system route failed")
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"timestamp": utcnow_str(), "counts": counts, "namespace": ns})


# series name -> (table, timestamp column, has namespace column, has deleted_at column)
_TREND_SERIES = {
    "memory":       ("memory_entries", "created_at", True,  False),
    "runs":         ("agent_runs",     "created_at", True,  True),
    "outputs":      ("outputs",        "created_at", True,  True),
    "open_tickets": ("tickets",        "created_at", True,  False),
    "workflows":    ("workflow_runs",  "started_at", False, False),
}


@system_bp.get("/system/trends")
@require_auth
def trends():
    """Per-day new-record counts for the Overview KPI sparklines (oldest day first)."""
    try:
        days = max(2, min(int(request.args.get("days", 14)), 90))
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400

    ns = effective_namespace(None)
    today = datetime.now(timezone.utc).date()
    day_list = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    since = day_list[0]

    series: dict = {}
    try:
        with get_db() as conn:
            for name, (table, ts_col, has_ns, has_deleted) in _TREND_SERIES.items():
                where, params = [f"date({ts_col}) >= ?"], [since]
                if has_ns and ns:
                    where.append("namespace = ?")
                    params.append(ns)
                if has_deleted:
                    where.append("deleted_at IS NULL")
                rows = conn.execute(
                    f"SELECT date({ts_col}) AS d, COUNT(*) FROM {table} "
                    f"WHERE {' AND '.join(where)} GROUP BY d",
                    params,
                ).fetchall()
                by_day = {r[0]: r[1] for r in rows}
                series[name] = [by_day.get(d, 0) for d in day_list]
    except Exception:
        _log.exception("system trends failed")
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"days": day_list, "series": series, "namespace": ns})


@system_bp.get("/system/namespace-stats")
@require_auth
def namespace_stats():
    """Per-namespace usage metrics for the Client Usage Dashboard.
    Clients can only query their own namespace; admins can pass ?namespace=slug."""
    requested = request.args.get("namespace")
    ns = effective_namespace(requested)
    if not ns:
        return jsonify({"error": "namespace required"}), 400

    # 30-day window for cost/runs
    from datetime import datetime, timedelta
    month_ago = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    week_ago  = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

    try:
        with get_db() as conn:
            # Compound query — collapses 7 round-trips into 1
            row = conn.execute(
                """SELECT
                     COALESCE(SUM(CASE WHEN ar.status='done' AND ar.created_at>=? THEN ar.tokens_in  ELSE 0 END), 0) AS tokens_in,
                     COALESCE(SUM(CASE WHEN ar.status='done' AND ar.created_at>=? THEN ar.tokens_out ELSE 0 END), 0) AS tokens_out,
                     COUNT(CASE WHEN ar.status='done' AND ar.created_at>=? THEN 1 END)                               AS run_count,
                     COALESCE(AVG(CASE WHEN ar.status='done' AND ar.created_at>=? THEN ar.eval_score END), 0)        AS eval_avg,
                     (SELECT COUNT(*) FROM tickets   WHERE namespace=? AND created_at>=?)                            AS t_total,
                     (SELECT COUNT(*) FROM tickets   WHERE namespace=? AND created_at>=?
                        AND status IN ('completed','closed','resolved'))                                              AS t_closed,
                     (SELECT COUNT(*) FROM memory_entries WHERE namespace=? AND archived=0)                          AS m_total,
                     (SELECT COUNT(*) FROM memory_entries WHERE namespace=? AND archived=0 AND updated_at>=?)        AS m_fresh,
                     (SELECT MAX(updated_at) FROM memory_entries WHERE namespace=? AND is_consolidated=1)            AS last_cons,
                     (SELECT COUNT(*) FROM outputs   WHERE namespace=?)                                              AS out_count
                   FROM agent_runs ar WHERE ar.namespace=?""",
                (month_ago, month_ago, month_ago, month_ago,  # agent_runs aggregates
                 ns, month_ago,                                # t_total
                 ns, month_ago,                                # t_closed
                 ns,                                           # m_total
                 ns, week_ago,                                 # m_fresh
                 ns,                                           # last_cons
                 ns,                                           # out_count
                 ns),                                          # WHERE ar.namespace
            ).fetchone()

            tokens_in  = row["tokens_in"]
            tokens_out = row["tokens_out"]
            run_count  = row["run_count"]
            eval_avg   = row["eval_avg"] or 0
            t_total    = row["t_total"]
            t_closed   = row["t_closed"]
            m_total    = row["m_total"]
            m_fresh    = row["m_fresh"]
            last_cons  = row["last_cons"]
            out_count  = row["out_count"]

            # Cost estimate (Claude Sonnet 4.6 pricing)
            cost_usd = round((tokens_in / 1_000_000 * 3.0) + (tokens_out / 1_000_000 * 15.0), 4)

            # Workflow success rate — separate query (JOIN makes it awkward in compound)
            wf_total, wf_ok = 0, 0
            try:
                wf_row = conn.execute(
                    """SELECT COUNT(*), SUM(CASE WHEN wr.status='done' THEN 1 ELSE 0 END)
                       FROM workflow_runs wr
                       JOIN workflows w ON wr.workflow_id=w.id
                       WHERE w.namespace=? AND wr.created_at>=?""",
                    (ns, month_ago),
                ).fetchone()
                wf_total, wf_ok = wf_row[0], (wf_row[1] or 0)
            except Exception:
                pass

            # Recent runs (last 10 for activity feed)
            recent_rows = conn.execute(
                """SELECT id, agent_id, status, eval_score, created_at, duration_ms
                   FROM agent_runs WHERE namespace=? ORDER BY created_at DESC LIMIT 10""",
                (ns,),
            ).fetchall()
            recent_runs = [dict(r) for r in recent_rows]

    except Exception as e:
        _log.exception("system route failed")
        return jsonify({"error": "Internal error"}), 500

    # Namespace Pulse Score (0–100 composite)
    q_score  = min((eval_avg / 5.0) * 100, 100) if eval_avg else 50
    t_score  = (t_closed / t_total * 100) if t_total else 100
    m_score  = (m_fresh / m_total * 100) if m_total else 100
    wf_score = (wf_ok / wf_total * 100) if wf_total else 100
    pulse    = round(q_score * 0.40 + t_score * 0.30 + m_score * 0.20 + wf_score * 0.10, 1)

    return jsonify({
        "namespace":      ns,
        "period_days":    30,
        "tokens_in":      tokens_in,
        "tokens_out":     tokens_out,
        "cost_usd":       cost_usd,
        "run_count":      run_count,
        "eval_avg":       round(eval_avg, 2),
        "ticket_total":   t_total,
        "tickets_closed": t_closed,
        "memory_count":   m_total,
        "memory_fresh":   m_fresh,
        "last_consolidated": last_cons,
        "workflow_total": wf_total,
        "workflow_ok":    wf_ok,
        "output_count":   out_count,
        "pulse_score":    pulse,
        "recent_runs":    recent_runs,
        "timestamp":      utcnow_str(),
    })


@system_bp.get("/system/hardware")
@require_auth
@limiter.limit("1000/hour")
def hardware():
    """Real-time host metrics for the admin system health bar.
    Admin/operator only — returns CPU%, RAM, disk, and uptime.
    """
    from flask import g as _g
    if getattr(_g, "user_role", "client") not in ("admin", "operator"):
        return jsonify({"error": "forbidden"}), 403

    try:
        import psutil, time
    except ImportError:
        return jsonify({"error": "psutil not installed"}), 503

    def _fmt_duration(seconds: int) -> str:
        days, rem  = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        mins       = rem // 60
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    try:
        cpu_pct   = psutil.cpu_percent(interval=0.1)
        vm        = psutil.virtual_memory()
        try:
            disk = psutil.disk_usage("C:\\")
        except Exception:
            disk = psutil.disk_usage("/")

        # Server uptime = time since this module was imported (Flask startup)
        server_uptime_str = _fmt_duration(int(_time.time() - _SERVER_START))
        # OS uptime = time since Windows last booted
        os_uptime_str = _fmt_duration(int(_time.time() - psutil.boot_time()))

        return jsonify({
            "cpu_pct":        round(cpu_pct, 1),
            "ram_used_gb":    round(vm.used  / 1024**3, 1),
            "ram_total_gb":   round(vm.total / 1024**3, 1),
            "ram_pct":        round(vm.percent, 1),
            "disk_used_gb":   round(disk.used  / 1024**3, 1),
            "disk_total_gb":  round(disk.total / 1024**3, 1),
            "disk_pct":       round(disk.percent, 1),
            "server_uptime":  server_uptime_str,
            "os_uptime":      os_uptime_str,
            "timestamp":      utcnow_str(),
        })
    except Exception as e:
        _log.exception("system route failed")
        return jsonify({"error": "Internal error"}), 500


@system_bp.get("/system/queues")
@require_auth
def queue_depths():
    """Return current thread pool queue depths and worker counts for operational visibility."""
    from core.auth import require_role as _rr
    from flask import g as _g
    if getattr(_g, "user_role", "client") not in ("admin", "operator"):
        return jsonify({"error": "Insufficient permissions"}), 403

    def _pool_info(pool):
        try:
            return {"queued": pool._work_queue.qsize(), "max_workers": pool._max_workers}
        except AttributeError:
            return {"queued": -1, "max_workers": -1}

    result = {}
    try:
        from agents.executor import _bg_pool, _ctx_pool
        result["executor_bg"] = _pool_info(_bg_pool)
        result["executor_ctx"] = _pool_info(_ctx_pool)
    except Exception:
        pass
    try:
        from agents.evaluator import _eval_pool
        result["evaluator"] = _pool_info(_eval_pool)
    except Exception:
        pass
    try:
        from memory.retriever import _RETRIEVER_POOL
        result["retriever"] = _pool_info(_RETRIEVER_POOL)
    except Exception:
        pass
    try:
        from workflows.scheduler import _pool as _wf_pool
        result["workflow"] = _pool_info(_wf_pool)
    except Exception:
        pass

    return jsonify(result)


@system_bp.get("/system/events")
@require_auth
def events():
    limit = min(int(request.args.get("limit", 50)), 200)
    severity = request.args.get("severity")
    # effective_namespace forces client/viewer to their own namespace
    namespace = effective_namespace(request.args.get("namespace"))

    conditions, params = [], []
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if namespace:
        conditions.append("namespace = ?")
        params.append(namespace)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM system_events {where} ORDER BY created_at DESC LIMIT ?", params
        ).fetchall()

    return jsonify({
        "events": [dict(r) for r in rows],
        "count": len(rows),
    })
