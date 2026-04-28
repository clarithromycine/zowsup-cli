"""
Dashboard API routes (Blueprint).

Phase 1 endpoints return real data where available, or empty structures
that conform to the final schema so the frontend can be built against them.

Endpoints:
  GET  /api/health          health check
  GET  /api/user-profile    user portrait (empty in Phase 1, real data in Phase 2)
  GET  /api/chat-history    paginated messages
  GET  /api/statistics      aggregated stats
"""

import logging
from flask import Blueprint, current_app, jsonify, request

from app.dashboard.utils.db_init import get_db_connection, verify_db

bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1.14  GET /api/health
# ---------------------------------------------------------------------------

@bp.route("/health", methods=["GET"])
def health():
    """
    Returns DB status so the operator can verify the service is alive and
    dashboard.db is properly initialised.
    """
    try:
        db_path = current_app.config["DASHBOARD_DB_PATH"]
        db_info = verify_db(db_path)
        all_present = all(v != "MISSING" for v in db_info["tables"].values())
        return jsonify({
            "status": "ok" if all_present else "degraded",
            "journal_mode": db_info["journal_mode"],
            "tables": db_info["tables"],
        }), 200
    except Exception as e:
        logger.exception("Health check failed")
        return jsonify({"status": "error", "detail": str(e)}), 500


# ---------------------------------------------------------------------------
# 1.11  GET /api/user-profile?jid=<jid>
# ---------------------------------------------------------------------------

@bp.route("/user-profile", methods=["GET"])
def user_profile():
    """
    Return the computed portrait for a given JID.

    Phase 1: reads from user_profiles table (will be empty until Phase 2
    computes the data).  Returns a well-typed empty structure instead of 404
    so the frontend can be developed against a stable schema.

    Query params:
        jid  (required)  WhatsApp JID e.g. 8613800001234@s.whatsapp.net
    """
    jid = request.args.get("jid", "").strip()
    if not jid:
        return jsonify({"error": "jid parameter is required"}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_jid = ?", (jid,)
        ).fetchone()

    if row is None:
        # Return empty-but-typed structure so the frontend schema is stable
        return jsonify(_empty_profile(jid)), 200

    return jsonify(dict(row)), 200


def _empty_profile(jid: str) -> dict:
    return {
        "user_jid": jid,
        "total_interactions": 0,
        "first_seen": None,
        "last_seen": None,
        "user_category": None,
        "communication_style": None,
        "topic_preferences": {},
        "satisfaction_score": None,
        "trend_7d": {"dates": [], "counts": []},
        "trend_30d": {"dates": [], "counts": []},
        "current_strategy": None,
        "updated_at": None,
    }


# ---------------------------------------------------------------------------
# 1.12  GET /api/chat-history?jid=<jid>&page=1&page_size=50
# ---------------------------------------------------------------------------

@bp.route("/chat-history", methods=["GET"])
def chat_history():
    """
    Return paginated chat messages for a given JID.

    Query params:
        jid        (required)
        page       (optional, default 1)
        page_size  (optional, default 50, max 200)
    """
    jid = request.args.get("jid", "").strip()
    if not jid:
        return jsonify({"error": "jid parameter is required"}), 400

    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(200, max(1, int(request.args.get("page_size", 50))))
    except ValueError:
        return jsonify({"error": "page and page_size must be integers"}), 400

    offset = (page - 1) * page_size

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    with get_db_connection(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE user_jid = ?", (jid,)
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT id, user_jid, direction, content, message_type, timestamp, created_at "
            "FROM chat_messages "
            "WHERE user_jid = ? "
            "ORDER BY timestamp ASC "
            "LIMIT ? OFFSET ?",
            (jid, page_size, offset),
        ).fetchall()

    return jsonify({
        "jid": jid,
        "page": page,
        "page_size": page_size,
        "total": total,
        "messages": [dict(r) for r in rows],
    }), 200


# ---------------------------------------------------------------------------
# 1.13  GET /api/statistics
# ---------------------------------------------------------------------------

@bp.route("/statistics", methods=["GET"])
def statistics():
    """
    Return aggregated dashboard statistics.

    Phase 1: computes live counts from chat_messages table.
    Phase 2 will also populate daily_statistics for trend charts.

    Query params:
        days  (optional, default 30)  look-back window
    """
    try:
        days = max(1, int(request.args.get("days", 30)))
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    with get_db_connection(db_path) as conn:
        # Total messages
        total_messages = conn.execute(
            "SELECT COUNT(*) FROM chat_messages "
            "WHERE timestamp >= strftime('%s', 'now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()[0]

        # Incoming / outgoing split
        incoming = conn.execute(
            "SELECT COUNT(*) FROM chat_messages "
            "WHERE direction = 'in' AND timestamp >= strftime('%s', 'now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()[0]

        outgoing = conn.execute(
            "SELECT COUNT(*) FROM chat_messages "
            "WHERE direction = 'out' AND timestamp >= strftime('%s', 'now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()[0]

        # Unique active users
        active_users = conn.execute(
            "SELECT COUNT(DISTINCT user_jid) FROM chat_messages "
            "WHERE timestamp >= strftime('%s', 'now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()[0]

        # Total known users (all time)
        total_users = conn.execute(
            "SELECT COUNT(DISTINCT user_jid) FROM chat_messages"
        ).fetchone()[0]

        # Daily breakdown (last N days)
        daily_rows = conn.execute(
            "SELECT date(timestamp, 'unixepoch') AS day, "
            "       SUM(CASE WHEN direction='in'  THEN 1 ELSE 0 END) AS incoming, "
            "       SUM(CASE WHEN direction='out' THEN 1 ELSE 0 END) AS outgoing "
            "FROM chat_messages "
            "WHERE timestamp >= strftime('%s', 'now', ? || ' days') "
            "GROUP BY day ORDER BY day ASC",
            (f"-{days}",),
        ).fetchall()

    return jsonify({
        "window_days": days,
        "total_messages": total_messages,
        "incoming_messages": incoming,
        "outgoing_messages": outgoing,
        "active_users": active_users,
        "total_users": total_users,
        "daily_breakdown": [dict(r) for r in daily_rows],
    }), 200


# ---------------------------------------------------------------------------
# 404 / 405 handlers
# ---------------------------------------------------------------------------

@bp.app_errorhandler(404)
def not_found(_e):
    return jsonify({"error": "endpoint not found"}), 404


@bp.app_errorhandler(405)
def method_not_allowed(_e):
    return jsonify({"error": "method not allowed"}), 405
