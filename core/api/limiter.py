"""Shared Flask-Limiter instance — import and call init_app(app) in create_app()."""
import logging
from pathlib import Path
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

_logger = logging.getLogger("claudeos.limiter")

# Persistent SQLite storage so rate-limit counters survive server restarts.
# Requires: pip install limits[SQLAlchemy]
# Falls back to in-memory if the package isn't available.
_BASE_DIR = Path(__file__).parent.parent.parent
_STORAGE_URI = f"sqlite:///{_BASE_DIR}/data/rate_limits.db"

try:
    # Verify SQLAlchemy storage backend is available before wiring it up
    from limits.storage import SQLAlchemyStorage as _SA  # noqa: F401
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["500/day", "100/hour"],
        storage_uri=_STORAGE_URI,
    )
    _logger.debug("Rate limiter: SQLite persistent storage at %s", _STORAGE_URI)
except ImportError:
    _logger.warning(
        "Rate limiter: using in-memory storage (counters reset on restart). "
        "For persistence run: pip install 'limits[SQLAlchemy]'"
    )
    limiter = Limiter(key_func=get_remote_address, default_limits=["500/day", "100/hour"])
except Exception as _e:
    import os as _os
    _is_prod = _os.environ.get("FLASK_ENV", "").lower() == "production" or \
               _os.environ.get("CLAUDEOS_ENV", "").lower() == "production"
    if _is_prod:
        # M5: Fail-fast in production — in-memory counters reset on restart = burst attack window
        _logger.critical(
            "Rate limiter: SQLite storage failed in PRODUCTION (%s). "
            "Fix: pip install 'limits[SQLAlchemy]' and ensure data/ is writable. "
            "Server not starting.", _e
        )
        raise
    _logger.warning("Rate limiter: SQLite storage failed (%s) — falling back to in-memory (dev only)", _e)
    limiter = Limiter(key_func=get_remote_address, default_limits=["500/day", "100/hour"])
