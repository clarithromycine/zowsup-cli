"""
Dashboard Flask application factory.

Design constraints (see DASHBOARD_TODO.md architecture decisions):
  - Standard synchronous WSGI only.  NO eventlet / gevent imports.
  - Flask process is completely separate from the bot asyncio process.
  - Data access is read-only from dashboard.db (bot writes, Flask reads).

Phase 4 additions:
  - Bearer-token auth (require DASHBOARD_API_TOKEN env var in production).
  - Rate limiting via flask-limiter (in-memory, single-instance).
  - WebSocket support via Flask-SocketIO (async_mode='threading').
  - SSE statistics-stream endpoint.
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
    # Phase 4: Rate limiting
    # ------------------------------------------------------------------
    from app.dashboard.api.rate_limit import limiter
    limiter.init_app(app)

    # ------------------------------------------------------------------
    # Phase 6: Security headers (CSP, XSS, CSRF mitigations, HSTS)
    # ------------------------------------------------------------------
    from app.dashboard.api.security import register_security
    register_security(app)

    # ------------------------------------------------------------------
    # Phase 4: WebSocket (Flask-SocketIO, threading mode — no eventlet)
    # ------------------------------------------------------------------
    from app.dashboard.api.websocket import init_socketio, start_monitor_thread
    _sio = init_socketio(app)
    if _sio is not None:
        start_monitor_thread(resolved_db_path)
    # Expose SocketIO on app for run_dashboard.py to call socketio.run()
    app.extensions["socketio"] = _sio

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from app.dashboard.api.routes import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # Phase 6: Auth endpoints (verify + refresh)
    from app.dashboard.api.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # Phase 4: SSE blueprint (registered under /api so auth + CORS apply)
    from app.dashboard.api.sse import sse_bp
    app.register_blueprint(sse_bp, url_prefix="/api")

    # Phase 5: Bot control blueprint
    from app.dashboard.api.bot_control import bot_bp
    app.register_blueprint(bot_bp, url_prefix="/api/bot")

    # ------------------------------------------------------------------
    # Phase 7: Swagger UI docs endpoint
    # ------------------------------------------------------------------
    from app.dashboard.api.docs import docs_bp
    app.register_blueprint(docs_bp)

    # ------------------------------------------------------------------
    # Phase 7: Optional Sentry error tracking
    # Activated when SENTRY_DSN is set in the environment.
    # ------------------------------------------------------------------
    _init_sentry(app)

    # ------------------------------------------------------------------
    # Phase 2: Background profile scheduler (APScheduler)
    # Runs UserProfileAnalyzer.update_all_profiles() every 5 minutes.
    # Only started in production — not during pytest (avoid stray threads).
    # ------------------------------------------------------------------
    _start_profile_scheduler(app, resolved_db_path)

    return app


def _read_llm_config() -> dict:
    """Read LLM backend config from conf/config.conf for profile analysis."""
    import configparser
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    config_path = project_root / "conf" / "config.conf"
    conf = configparser.ConfigParser()
    if not config_path.exists():
        return {}
    conf.read(config_path)
    if not conf.getboolean("AI_LLM_ACTIVE", "enabled", fallback=False):
        return {}
    backend = conf.get("AI_LLM_ACTIVE", "backend", fallback="").upper()
    section = f"AI_LLM_{backend}"
    if section not in conf:
        return {}
    return {
        "backend": backend,
        "api_key": conf.get(section, "api_key", fallback=""),
        "model": conf.get(section, "model", fallback=""),
        "auth_mode": conf.get(section, "auth_mode", fallback="apikey"),
    }


def _start_profile_scheduler(app: Flask, db_path: str) -> None:
    """Start an APScheduler background job for user profile computation."""
    import os
    # Skip scheduler in test environments
    if os.environ.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    llm_config = _read_llm_config()

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.dashboard.analyzer.user_profile_analyzer import UserProfileAnalyzer

        scheduler = BackgroundScheduler(daemon=True)

        def _run_profile_update():
            try:
                analyzer = UserProfileAnalyzer(db_path, llm_config=llm_config)
                n = analyzer.update_all_profiles()
                if n:
                    logging.getLogger("dashboard.scheduler").info(
                        f"Profile update: {n} profiles refreshed"
                    )
            except Exception:
                logging.getLogger("dashboard.scheduler").exception(
                    "Profile update job failed"
                )

        scheduler.add_job(_run_profile_update, "interval", minutes=5,
                          id="profile_update", replace_existing=True)
        scheduler.start()
        app.extensions["profile_scheduler"] = scheduler
        logging.getLogger("dashboard.scheduler").info(
            "Profile scheduler started (every 5 minutes)"
        )
    except ImportError:
        logging.getLogger("dashboard.scheduler").warning(
            "APScheduler not installed — background profile updates disabled. "
            "Run: pip install apscheduler"
        )
    except Exception:
        logging.getLogger("dashboard.scheduler").exception(
            "Failed to start profile scheduler"
        )


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


def _init_sentry(app: Flask) -> None:
    """Initialise Sentry SDK when SENTRY_DSN is set. No-op otherwise."""
    import os

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        import logging as _logging

        sentry_logging = LoggingIntegration(
            level=_logging.WARNING,       # breadcrumbs from WARNING+
            event_level=_logging.ERROR,   # send Sentry events for ERROR+
        )
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration(), sentry_logging],
            traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
            ),
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=os.environ.get("SENTRY_RELEASE", None),
            # Never send potentially sensitive PII
            send_default_pii=False,
        )
        logging.getLogger("dashboard").info(
            "Sentry error tracking enabled "
            f"(env={os.environ.get('SENTRY_ENVIRONMENT', 'production')})"
        )
    except ImportError:
        logging.getLogger("dashboard").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Run: pip install sentry-sdk[flask]"
        )
    except Exception:
        logging.getLogger("dashboard").exception("Failed to initialise Sentry")
