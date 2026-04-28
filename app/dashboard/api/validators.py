"""
Input validation helpers for the Dashboard API.

Phase 6 — item 7.13.

Provides:
  - ``require_json()``      — enforce application/json body
  - ``validate_jid()``      — WhatsApp JID format
  - ``validate_page_params()`` — pagination (page / per_page)
  - ``validate_string_field()`` — non-empty string with max-length cap
  - ``sanitize_str()``      — strip and truncate a string value
"""

import re
import logging
from typing import Any

from flask import jsonify, request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WhatsApp JID patterns accepted by the dashboard
# ---------------------------------------------------------------------------
# Individual:  1234567890@s.whatsapp.net
# Group:       1234567890-1234567890@g.us  (digits-digits format)
_JID_RE = re.compile(
    r"^[\d\+][\d\+\-]{4,35}(@s\.whatsapp\.net|@g\.us|@c\.us)$",
    re.IGNORECASE,
)

# Upper bounds to prevent payload abuse
_MAX_STRING_LEN = 4096
_MAX_PAGE = 10_000
_MAX_PER_PAGE = 500


def validate_jid(jid: str) -> tuple[bool, str]:
    """
    Validate a WhatsApp JID string.

    Returns (True, "") on success, (False, error_message) on failure.
    """
    if not jid or not isinstance(jid, str):
        return False, "jid is required"
    jid = jid.strip()
    if len(jid) > 60:
        return False, "jid is too long"
    if not _JID_RE.match(jid):
        return False, f"jid '{jid}' is not a valid WhatsApp JID"
    return True, ""


def validate_page_params(
    page: Any, per_page: Any
) -> tuple[bool, str, int, int]:
    """
    Validate pagination query parameters.

    Returns (valid, error, page_int, per_page_int).
    """
    try:
        page_int = int(page)
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        return False, "page and per_page must be integers", 1, 20

    if page_int < 1:
        return False, "page must be >= 1", 1, 20
    if page_int > _MAX_PAGE:
        return False, f"page must be <= {_MAX_PAGE}", 1, 20
    if per_page_int < 1:
        return False, "per_page must be >= 1", 1, 20
    if per_page_int > _MAX_PER_PAGE:
        return False, f"per_page must be <= {_MAX_PER_PAGE}", 1, 20

    return True, "", page_int, per_page_int


def validate_string_field(
    value: Any, field_name: str, max_len: int = _MAX_STRING_LEN
) -> tuple[bool, str]:
    """
    Validate that *value* is a non-empty string within *max_len* characters.

    Returns (True, "") on success, (False, error_message) on failure.
    """
    if value is None:
        return False, f"{field_name} is required"
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if not value.strip():
        return False, f"{field_name} must not be blank"
    if len(value) > max_len:
        return False, f"{field_name} must be at most {max_len} characters"
    return True, ""


def sanitize_str(value: Any, max_len: int = _MAX_STRING_LEN) -> str:
    """Strip whitespace and truncate to *max_len*.  Returns '' for non-strings."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def require_json():
    """
    Enforce that the request body is JSON.

    Returns a (Response, 415) tuple if the content-type is wrong, or None.
    Suitable for use inside a view or before_request hook.
    """
    if not request.is_json:
        return (
            jsonify({"error": "Content-Type must be application/json"}),
            415,
        )
    return None
