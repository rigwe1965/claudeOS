"""Request logging and CORS middleware."""
import time
import logging
from flask import request, g

from core.utils import new_id, utcnow_str
from core.database import get_db

logger = logging.getLogger("claudeos.api")


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
            request.path,
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
