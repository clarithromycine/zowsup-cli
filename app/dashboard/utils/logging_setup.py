"""
app/dashboard/utils/logging_setup.py
──────────────────────────────────────
Phase 7: Configures rotating file logging for the dashboard.

Call `setup_dashboard_logging()` once at startup (before create_app).
It adds a RotatingFileHandler to the root logger so all dashboard
components write to logs/dashboard.log in addition to stderr.

Settings are driven by CONFIG / environment variables:
  LOG_LEVEL         INFO (default) | DEBUG | WARNING | ERROR
  LOG_DIR           logs/  (relative to project root)
  LOG_MAX_BYTES     10 MB (default)
  LOG_BACKUP_COUNT  5 (default)
"""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_dashboard_logging(
    log_dir: str | None = None,
    log_level: str | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> None:
    """
    Add a RotatingFileHandler to the root logger.

    Safe to call multiple times — checks for duplicate handlers so
    it won't add a second file handler if already configured.

    Parameters mirror the CONFIG dict; pass None to use env-var / defaults.
    """
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

    resolved_dir = Path(
        log_dir
        or os.environ.get("LOG_DIR", str(_PROJECT_ROOT / "logs"))
    )
    resolved_level_name = (
        log_level
        or os.environ.get("LOG_LEVEL", "INFO")
    ).upper()
    resolved_level = getattr(logging, resolved_level_name, logging.INFO)
    resolved_max_bytes = max_bytes or int(
        os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024))
    )
    resolved_backup_count = backup_count or int(
        os.environ.get("LOG_BACKUP_COUNT", "5")
    )

    resolved_dir.mkdir(parents=True, exist_ok=True)
    log_file = resolved_dir / "dashboard.log"

    root_logger = logging.getLogger()

    # Avoid duplicate file handlers
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            if getattr(handler, "baseFilename", "") == str(log_file.resolve()):
                return  # already configured

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=resolved_max_bytes,
        backupCount=resolved_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(resolved_level)

    root_logger.addHandler(file_handler)

    # Ensure the audit log also writes to file
    audit_logger = logging.getLogger("dashboard_audit")
    audit_file = resolved_dir / "dashboard_audit.log"
    _has_audit_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        and getattr(h, "baseFilename", "") == str(audit_file.resolve())
        for h in audit_logger.handlers
    )
    if not _has_audit_handler:
        audit_handler = logging.handlers.RotatingFileHandler(
            filename=str(audit_file),
            maxBytes=resolved_max_bytes,
            backupCount=resolved_backup_count,
            encoding="utf-8",
        )
        audit_handler.setFormatter(formatter)
        audit_handler.setLevel(logging.DEBUG)  # capture all audit events
        audit_logger.addHandler(audit_handler)
        audit_logger.propagate = False  # don't double-write to root

    logging.getLogger("dashboard").info(
        f"File logging enabled: {log_file}  (level={resolved_level_name}, "
        f"max={resolved_max_bytes // 1024}KB, backups={resolved_backup_count})"
    )
