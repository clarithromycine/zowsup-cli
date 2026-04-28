"""
Dashboard Flask application factory.

Design constraints (see DASHBOARD_TODO.md architecture decisions):
  - Standard synchronous WSGI only.  NO eventlet / gevent imports.
  - Flask process is completely separate from the bot asyncio process.
  - Data access is read-only from dashboard.db (bot writes, Flask reads).
"""

import logging
from flask import Flask
from flask_cors import CORS

from app.dashboard.config import CONFIG
from app.dashboard.utils.db_init import init_db


def create_app(db_path: str | None = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        db_path: Override the database path (used in tests to point at a
                 temporary file).  Defaults to CONFIG["DASHBOARD_DB_PATH"].
    """
    app = Flask(__name__)

    # Store db_path in app.config so routes can read it via current_app.
    resolved_db_path = db_path or CONFIG["DASHBOARD_DB_PATH"]
    app.config["DASHBOARD_DB_PATH"] = resolved_db_path

    # ------------------------------------------------------------------
    # CORS – allow the Vite dev server (port 5173) and any same-origin
    # request.  In production, restrict origins to your actual domain.
    # ------------------------------------------------------------------
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ------------------------------------------------------------------
    # Ensure dashboard.db exists with the correct schema before handling
    # any request.
    # ------------------------------------------------------------------
    init_db(resolved_db_path)

    # ------------------------------------------------------------------
    # Request / response logging middleware
    # ------------------------------------------------------------------
    _register_middleware(app)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from app.dashboard.api.routes import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


def _register_middleware(app: Flask) -> None:
    import time
    from flask import request, g

    logger = logging.getLogger("dashboard.access")

    @app.before_request
    def _start_timer():
        g.start_time = time.time()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.time() - g.get("start_time", time.time())) * 1000
        logger.info(
            f"{request.method} {request.path} → {response.status_code} "
            f"({duration_ms:.1f}ms)"
        )
        return response
