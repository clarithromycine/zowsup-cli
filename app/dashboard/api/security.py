"""
Security middleware for the Dashboard API.

Phase 6 — items 7.11 (CSRF) and 7.12 (XSS / security headers).

Design note on CSRF
-------------------
All Dashboard API calls use ``Authorization: Bearer <token>`` headers.
Browsers cannot automatically inject custom headers via cross-site
requests, so Bearer-token auth already defeats CSRF for API endpoints.
The ``SameSite`` headers on any future session cookies reinforce this.

The hardening applied here via HTTP response headers covers:
  - Content-Security-Policy  (mitigates XSS, data injection)
  - X-Content-Type-Options   (prevents MIME-type sniffing)
  - X-Frame-Options          (clickjacking protection)
  - Referrer-Policy          (information leakage reduction)
  - Permissions-Policy       (browser-feature restriction)
  - Strict-Transport-Security (HSTS — enabled only when not DEBUG)

Usage
-----
    from app.dashboard.api.security import apply_security_headers
    app.after_request(apply_security_headers)
"""

import os
import logging

from flask import Flask, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Content-Security-Policy  (adjust as the frontend evolves)
# ---------------------------------------------------------------------------
# The SPA loads from the same origin in production (Flask serves static/).
# In development the Vite dev server runs on :5173 but proxies /api to Flask,
# so the Flask process never serves HTML in dev — only API JSON responses.
# Therefore a restrictive policy is safe here.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "   # unsafe-inline needed for Vite HMR in dev
    "style-src 'self' 'unsafe-inline'; "    # Ant Design injects inline styles
    "img-src 'self' data:; "               # data: for QR-code base64 blobs
    "connect-src 'self' ws: wss:; "        # WebSocket connections (SocketIO)
    "font-src 'self'; "
    "frame-ancestors 'none';"             # equivalent to X-Frame-Options: DENY
)

# ---------------------------------------------------------------------------
# Other security header values
# ---------------------------------------------------------------------------
_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), "
        "payment=(), usb=(), magnetometer=()"
    ),
}


def apply_security_headers(response: Response) -> Response:
    """
    Flask after_request hook — attach security headers to every response.

    Does NOT overwrite headers the view has already set explicitly, so that
    endpoints can opt-in to a looser policy when genuinely needed.
    """
    # CSP
    if "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = _CSP

    # Standard hardening headers
    for header, value in _HEADERS.items():
        if header not in response.headers:
            response.headers[header] = value

    # HSTS — only useful over HTTPS; skip in debug/test mode to avoid
    # breaking http:// localhost development.
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true")
    testing = bool(os.environ.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"))
    if not debug and not testing:
        if "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

    return response


def register_security(app: Flask) -> None:
    """Register security middleware on the given Flask app."""
    app.after_request(apply_security_headers)
    logger.info("Security headers middleware registered")
