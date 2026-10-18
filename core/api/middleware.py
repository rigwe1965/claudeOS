"""Request logging and CORS middleware."""
import re
import time
import logging
from flask import request, g

from core.utils import new_id, utcnow_str
from core.database import get_db

logger = logging.getLogger("claudeos.api")

# /auth/session/<handle> carries a reusable session handle; never log it.
_SESSION_HANDLE_RE = re.compile(r"(/auth/session/)[^/?#]+")
# request.path is percent-decoded: escape control chars so a crafted path can't forge log lines.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


def _log_safe(value: str) -> str:
    return _CONTROL_CHARS_RE.sub(lambda m: m.group().encode("unicode_escape").decode(), value)


def register_middleware(app):
    @app.before_request
    def before():
        g.request_id = new_id()
        g.start_time = time.monotonic()

    @app.after_request
    def after(response):
        duration_ms = int((time.monotonic() - g.get("start_time", time.monotonic())) * 1000)
        logger.info(
            "%s %s %s %dms",
            request.method,
            # URL paths can contain credentials (dashboard session handles).
            request.url_rule.rule if request.url_rule else "unmatched",
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response

    @app.errorhandler(404)
    def not_found(e):
        from flask import jsonify
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import jsonify
        logger.exception("Internal server error")
        return jsonify({"error": "Internal server error"}), 500
