"""
Dashboard server entry-point.

Run as a completely separate process from the bot:
    python run_dashboard.py

Environment variables (all optional):
    DASHBOARD_HOST       bind address  (default: 0.0.0.0)
    DASHBOARD_PORT       port          (default: 5000)
    DASHBOARD_DEBUG      enable debug  (default: false)
    DASHBOARD_API_TOKEN  bearer token  (default: empty = no auth, Phase 5 enforces)

IMPORTANT: This file MUST NOT import anything from the bot's asyncio stack
(zowbot_layer, consonance, core, etc.).  The two processes share ONLY the
dashboard.db file on disk.
"""

import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path so `app.dashboard.*` resolves
# regardless of the working directory the user starts from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging setup (before importing anything that logs)
# ---------------------------------------------------------------------------
log_level = logging.DEBUG if os.environ.get("DASHBOARD_DEBUG", "").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# Import app factory (deferred so logging is set up first)
# ---------------------------------------------------------------------------
from app.dashboard.api.app import create_app
from app.dashboard.config import CONFIG

app = create_app()


if __name__ == "__main__":
    host = CONFIG["FLASK_HOST"]
    port = CONFIG["FLASK_PORT"]
    debug = CONFIG["FLASK_DEBUG"]

    logger.info(f"Starting Dashboard server on http://{host}:{port}  debug={debug}")
    logger.info(f"Dashboard DB: {CONFIG['DASHBOARD_DB_PATH']}")

    # Standard Werkzeug WSGI server.
    # DO NOT replace with socketio.run() or use_reloader with eventlet/gevent.
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
