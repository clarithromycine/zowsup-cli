"""
Dashboard configuration.

Reads settings from conf/config.conf (same file as the bot uses),
so there is a single source of truth for paths.
"""

import os
import configparser
from pathlib import Path


def _load_config() -> dict:
    """Load config from conf/config.conf relative to project root."""
    # Walk up from this file's location to find project root (where conf/ lives)
    here = Path(__file__).resolve()
    # app/dashboard/config.py  →  up 3 levels = project root
    project_root = here.parent.parent.parent
    config_path = project_root / "conf" / "config.conf"

    conf = configparser.ConfigParser()
    if config_path.exists():
        conf.read(config_path, encoding='utf-8')

    account_path = conf.get("SysVar", "ACCOUNT_PATH", fallback="/data/account/")

    default_db = str(project_root / "data" / "dashboard.db")
    default_log_dir = str(project_root / "logs")

    return {
        "PROJECT_ROOT": str(project_root),
        "ACCOUNT_PATH": account_path,
        # dashboard.db lives inside the project's data/ folder, completely
        # separate from any per-account db.db
        "DASHBOARD_DB_PATH": os.environ.get("DASHBOARD_DB_PATH", default_db),
        "FLASK_HOST": os.environ.get("DASHBOARD_HOST", "0.0.0.0"),
        "FLASK_PORT": int(os.environ.get("DASHBOARD_PORT", "5000")),
        "FLASK_DEBUG": os.environ.get("DASHBOARD_DEBUG", "false").lower() == "true",
        # Simple bearer token for API auth
        "API_TOKEN": os.environ.get("DASHBOARD_API_TOKEN", ""),
        # CORS allowed origins (comma-separated)
        "CORS_ORIGINS": [
            o.strip()
            for o in os.environ.get("CORS_ORIGINS", "*").split(",")
            if o.strip()
        ],
        # Logging
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
        "LOG_DIR": os.environ.get("LOG_DIR", default_log_dir),
        "LOG_MAX_BYTES": int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        "LOG_BACKUP_COUNT": int(os.environ.get("LOG_BACKUP_COUNT", "5")),
    }


# Module-level singleton so imports always get the same object
CONFIG = _load_config()
