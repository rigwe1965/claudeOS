"""Flask application factory."""
import logging
import logging.handlers
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from core.config import get_settings
from core.api.middleware import register_middleware
from core.api.routes.system import system_bp


def create_app() -> Flask:
    settings = get_settings()

    # C3: Fail fast on missing critical config — don't start with broken credentials
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY missing from .env — server cannot start")
    if not settings.CLAUDEOS_SECRET_KEY:
        raise RuntimeError("CLAUDEOS_SECRET_KEY missing from .env — server cannot start")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.CLAUDEOS_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # images are base64 in JSON; reject anything larger

    # CORS — restrict to configured origins (never wildcard in production)
    import os as _os
    _origins = [o.strip() for o in _os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:8501"
    ).split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": _origins}})

    # Logging
    _setup_logging(settings)

    # Rate limiter
    from core.api.limiter import limiter
    limiter.init_app(app)

    # Security response headers
    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # Middleware
    register_middleware(app)

    # Run DB migrations (idempotent — CREATE IF NOT EXISTS)
    _run_migrations()
    # Clean up stuck runs from any previous server crash
    _cleanup_stale_runs()

    # Routes — Phase 1
    app.register_blueprint(system_bp)

    # Auth + Admin blueprints
    from core.api.routes.auth_routes import auth_bp
    from core.api.routes.admin_routes import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # Routes — Phase 2+ (registered lazily when modules exist)
    _register_optional_blueprints(app)

    # Workflow Scheduler — start after blueprints registered
    _start_scheduler(app)

    # Pre-load ChromaDB + sentence-transformers in background.
    # Without this, the first memory request blocks a Flask worker for 30-60s on Windows.
    _warmup_vector_store()

    # H1: Pre-load Whisper model in background so first /transcribe call doesn't block.
    _warmup_whisper()

    # Warn on startup if email notifications are not configured
    try:
        from core.notifications import _is_configured as _smtp_ok
        if not _smtp_ok():
            logging.getLogger("claudeos.api").warning(
                "Email notifications DISABLED — set SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env"
            )
    except Exception:
        pass

    return app


def _cleanup_stale_runs():
    """Reset stuck agent/workflow runs left over from a previous server crash.

    Any run still in 'pending' or 'running' state older than 1 hour is a crash
    artifact — it will never complete. Mark as 'failed' so the UI reflects reality.
    """
    try:
        from core.database import get_db
        with get_db() as conn:
            conn.execute(
                """UPDATE agent_runs SET status='failed', error='Server restarted — run was interrupted'
                   WHERE status IN ('pending','running')
                     AND created_at < datetime('now', '-1 hour')"""
            )
            conn.execute(
                """UPDATE workflow_runs SET status='failed', error='Server restarted — run was interrupted'
                   WHERE status IN ('pending','running')
                     AND created_at < datetime('now', '-1 hour')"""
            )
    except Exception as e:
        logging.getLogger("claudeos.api").warning("Stale run cleanup failed: %s", e)


def _run_migrations():
    """Apply all SQL migrations in order (idempotent)."""
    migrations_dir = Path(__file__).parent.parent.parent / "memory" / "db" / "migrations"
    if not migrations_dir.exists():
        return
    from core.database import run_migration
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        try:
            run_migration(sql_file)
        except Exception as e:
            logging.getLogger("claudeos.api").warning("Migration %s failed: %s", sql_file.name, e)


def _register_optional_blueprints(app: Flask):
    try:
        from core.api.routes.memory import memory_bp
        app.register_blueprint(memory_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.agents import agents_bp
        app.register_blueprint(agents_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.workflows import workflows_bp
        app.register_blueprint(workflows_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.projects import projects_bp
        app.register_blueprint(projects_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.outputs import outputs_bp
        app.register_blueprint(outputs_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.sync import sync_bp
        app.register_blueprint(sync_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.tickets import tickets_bp
        app.register_blueprint(tickets_bp)
    except ImportError:
        pass

    try:
        from core.api.routes.transcribe import transcribe_bp
        app.register_blueprint(transcribe_bp)
    except ImportError:
        pass


def _warmup_whisper():
    """Pre-load Whisper model in background — prevents 10-30s block on first /transcribe call."""
    import threading
    log = logging.getLogger("claudeos.api")
    def _warm():
        try:
            from core.api.routes.transcribe import _get_model
            _get_model()
            log.info("Whisper model pre-loaded.")
        except ImportError:
            pass  # whisper not installed — voice input disabled
        except Exception as e:
            log.warning("Whisper pre-load failed (voice input may be slow on first use): %s", e)
    threading.Thread(target=_warm, daemon=True, name="whisper-warmup").start()


def _warmup_vector_store():
    """Pre-load ChromaDB + sentence-transformers in a background thread.
    Flask starts serving /health immediately; warmup completes in ~5-8s.
    _init() is protected by a lock so concurrent calls are safe."""
    import threading
    log = logging.getLogger("claudeos.api")
    def _warm():
        try:
            log.info("ChromaDB warmup starting (sentence-transformers model load)...")
            from memory.vector_store import _init
            _init()
            log.info("ChromaDB warmup complete.")
        except Exception as e:
            log.warning("ChromaDB warmup failed (semantic search disabled): %s", e)
            try:
                from memory.vector_store import _init_failed
                if _init_failed:
                    log.warning("Semantic search disabled — agents will fall back to FTS context")
            except Exception:
                pass
    threading.Thread(target=_warm, daemon=True, name="vs-warmup").start()


def _start_scheduler(app: Flask):
    try:
        from workflows.scheduler import init_scheduler
        init_scheduler()
        import atexit
        from workflows.scheduler import shutdown_scheduler
        atexit.register(shutdown_scheduler)
    except ImportError:
        pass
    except Exception as e:
        import logging
        logging.getLogger("claudeos.api").warning("Scheduler init failed: %s", e)

    # H4: Graceful shutdown of all ThreadPoolExecutors on process exit.
    import atexit
    atexit.register(_shutdown_thread_pools)


def _shutdown_thread_pools() -> None:
    """H4: Graceful shutdown of all ThreadPoolExecutors — called via atexit.
    No logging here — log streams may already be closed during Python teardown."""
    pools = []
    try:
        from agents.executor import _bg_pool, _ctx_pool
        pools += [_bg_pool, _ctx_pool]
    except Exception:
        pass
    try:
        from agents.evaluator import _eval_pool
        pools.append(_eval_pool)
    except Exception:
        pass
    try:
        from memory.retriever import _RETRIEVER_POOL
        pools.append(_RETRIEVER_POOL)
    except Exception:
        pass
    for pool in pools:
        try:
            pool.shutdown(wait=True, cancel_futures=False)
        except Exception:
            pass


def _setup_logging(settings):
    log_dir = Path(settings.LOG_PATH)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "api.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(ch)
