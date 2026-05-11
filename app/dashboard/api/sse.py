"""
Server-Sent Events (SSE) — dashboard statistics stream.

Endpoint:
    GET /api/statistics-stream

Behaviour:
    1. Sends an initial statistics snapshot immediately.
    2. Pushes a fresh snapshot every PUSH_INTERVAL_S seconds.
    3. Sends ':keep-alive' comment comments every HEARTBEAT_INTERVAL_S
       seconds to prevent proxy / browser timeouts.

Data format (text/event-stream):
    data: {"total_messages": 120, "active_users": 5, ...}\n\n

Authentication:
    Uses the same Bearer-token check as the main API blueprint.
    The before_request hook on sse_bp calls check_bearer().
"""

import json
import logging
import sqlite3
import time

from flask import Blueprint, Response, current_app, stream_with_context

from app.dashboard.api.auth import check_bearer

logger = logging.getLogger(__name__)

sse_bp = Blueprint("sse", __name__)

_PUSH_INTERVAL_S = 15       # seconds between statistics pushes
_HEARTBEAT_INTERVAL_S = 30  # seconds between keep-alive comments


# ---------------------------------------------------------------------------
# Auth guard — applied to every route in this blueprint
# ---------------------------------------------------------------------------

@sse_bp.before_request
def _sse_auth():
    result = check_bearer()
    if result is not None:
        return result


# ---------------------------------------------------------------------------
# Stats query helper
# ---------------------------------------------------------------------------

def _fetch_stats(db_path: str) -> dict:
    """
    Return a lightweight statistics snapshot.
    Kept simple so it completes in well under 50 ms even with large tables.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row

        total_messages = conn.execute(
            "SELECT COUNT(*) FROM chat_messages"
        ).fetchone()[0]

        active_users = conn.execute(
            "SELECT COUNT(DISTINCT user_jid) FROM chat_messages"
        ).fetchone()[0]

        ai_responses = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE direction='out'"
        ).fetchone()[0]

        today_messages = conn.execute(
            "SELECT COUNT(*) FROM chat_messages "
            "WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]

        conn.close()

        return {
            "total_messages": total_messages,
            "active_users": active_users,
            "ai_responses": ai_responses,
            "today_messages": today_messages,
        }
    except Exception as exc:
        logger.warning("SSE stats query failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@sse_bp.route("/statistics-stream")
def statistics_stream():
    """
    Long-lived SSE connection that streams dashboard statistics.

    Clients should use EventSource:
        const es = new EventSource('/api/statistics-stream', {
            headers: {Authorization: 'Bearer <token>'}
        });
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    db_path = current_app.config["DASHBOARD_DB_PATH"]

    def generate():
        # ── initial snapshot ──────────────────────────────────────────────
        yield f"data: {json.dumps(_fetch_stats(db_path))}\n\n"
        last_push = time.time()
        last_heartbeat = time.time()

        while True:
            time.sleep(1)
            now = time.time()

            if now - last_heartbeat >= _HEARTBEAT_INTERVAL_S:
                yield ": keep-alive\n\n"
                last_heartbeat = now

            if now - last_push >= _PUSH_INTERVAL_S:
                yield f"data: {json.dumps(_fetch_stats(db_path))}\n\n"
                last_push = now

    resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"   # prevent nginx buffering
    return resp
