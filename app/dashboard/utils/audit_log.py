"""
Security audit log for the Dashboard API.

Phase 6 — item 7.15.

All security-relevant events are written to a dedicated ``dashboard_audit``
logger so they can be directed to a separate file handler in production.

Event categories
----------------
AUTH_SUCCESS   — valid token accepted
AUTH_FAILURE   — invalid / missing token (logged with source IP + path)
TOKEN_VERIFY   — explicit token-verify call
AUTH_BYPASS    — dev-mode bypass (no token configured)
"""

import logging
import time
from typing import Optional

from flask import request

logger = logging.getLogger("dashboard_audit")


def _context() -> dict:
    """Collect request context for log records."""
    ctx: dict = {
        "ts": int(time.time()),
        "method": "-",
        "path": "-",
        "ip": "unknown",
    }
    try:
        ctx["method"] = request.method
        ctx["path"] = request.path
        xff = request.headers.get("X-Forwarded-For", "")
        ctx["ip"] = xff.split(",")[0].strip() if xff else (request.remote_addr or "unknown")
    except RuntimeError:
        # Called outside of a Flask request context (e.g., tests calling functions directly)
        pass
    return ctx


def log_auth_success(jid: Optional[str] = None) -> None:
    """Record a successful bearer-token authentication."""
    ctx = _context()
    logger.info(
        "AUTH_SUCCESS ip=%s path=%s jid=%s",
        ctx["ip"], ctx["path"], jid or "-",
    )


def log_auth_failure(reason: str = "invalid_token") -> None:
    """Record a failed authentication attempt."""
    ctx = _context()
    logger.warning(
        "AUTH_FAILURE ip=%s path=%s method=%s reason=%s",
        ctx["ip"], ctx["path"], ctx["method"], reason,
    )


def log_auth_bypass() -> None:
    """Record that auth was bypassed because no token is configured (dev mode)."""
    ctx = _context()
    logger.warning(
        "AUTH_BYPASS ip=%s path=%s — DASHBOARD_API_TOKEN not set",
        ctx["ip"], ctx["path"],
    )


def log_token_verify(valid: bool) -> None:
    """Record the result of an explicit /api/auth/verify call."""
    ctx = _context()
    status = "VALID" if valid else "INVALID"
    logger.info(
        "TOKEN_VERIFY ip=%s result=%s",
        ctx["ip"], status,
    )
