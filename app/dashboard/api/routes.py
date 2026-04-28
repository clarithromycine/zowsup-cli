"""
Dashboard API routes (Blueprint).

Phase 1 endpoints return real data where available, or empty structures
that conform to the final schema so the frontend can be built against them.

Endpoints:
  GET  /api/health          health check
  GET  /api/contacts        list of all known contacts with last-message summary
  GET  /api/user-profile    user portrait (empty in Phase 1, real data in Phase 2)
  GET  /api/chat-history    paginated messages
  GET  /api/statistics      aggregated stats
"""

import logging
from flask import Blueprint, current_app, jsonify, request

from app.dashboard.utils.db_init import get_db_connection, verify_db
from app.dashboard.api.auth import check_bearer
from app.dashboard.api.rate_limit import limiter
from app.dashboard.api.validators import (
    validate_jid,
    validate_page_params,
    sanitize_str,
)

bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 4: Bearer-token auth applied to all routes except /health
# ---------------------------------------------------------------------------

@bp.before_request
def _check_auth():
    """Enforce Bearer-token auth on every endpoint except /health."""
    if request.endpoint == "api.health":
        return None
    return check_bearer()


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
# 1.10  GET /api/contacts
# ---------------------------------------------------------------------------

@bp.route("/contacts", methods=["GET"])
def contacts():
    """
    Return all distinct contacts sorted by most recent activity,
    with last-message preview and total message count.

    Response:
      {
        "contacts": [
          {
            "user_jid": "989334018988@s.whatsapp.net",
            "last_message": "...",
            "last_timestamp": 1714300000,
            "message_count": 42
          },
          ...
        ]
      }
    """
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                cm.user_jid,
                cm.content        AS last_message,
                cm.timestamp      AS last_timestamp,
                agg.message_count
            FROM chat_messages cm
            INNER JOIN (
                SELECT user_jid,
                       MAX(timestamp) AS max_ts,
                       COUNT(*)       AS message_count
                FROM   chat_messages
                GROUP  BY user_jid
            ) agg ON cm.user_jid = agg.user_jid
                  AND cm.timestamp = agg.max_ts
            GROUP  BY cm.user_jid
            ORDER  BY last_timestamp DESC
            """
        ).fetchall()
    return jsonify({"contacts": [dict(r) for r in rows]}), 200


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

    valid, err, page, page_size = validate_page_params(
        request.args.get("page", 1),
        request.args.get("page_size", 50),
    )
    if not valid:
        return jsonify({"error": err}), 400
    page_size = min(page_size, 200)  # hard cap for chat-history

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
            "ORDER BY timestamp DESC "
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
# Phase 2  GET /api/user-ai-thoughts?jid=<jid>&page=1&page_size=50
# ---------------------------------------------------------------------------

@bp.route("/user-ai-thoughts", methods=["GET"])
def user_ai_thoughts():
    """
    Return paginated AI thought records for a given JID.

    Query params:
        jid        (required)
        page       (optional, default 1)
        page_size  (optional, default 50, max 200)
    """
    jid = request.args.get("jid", "").strip()
    if not jid:
        return jsonify({"error": "jid parameter is required"}), 400

    valid, err, page, page_size = validate_page_params(
        request.args.get("page", 1),
        request.args.get("page_size", 50),
    )
    if not valid:
        return jsonify({"error": err}), 400
    page_size = min(page_size, 200)  # hard cap for ai-thoughts

    offset = (page - 1) * page_size
    db_path = current_app.config["DASHBOARD_DB_PATH"]

    with get_db_connection(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM ai_thoughts WHERE user_jid = ?", (jid,)
        ).fetchone()[0]

        rows = conn.execute(
            """
            SELECT id, message_id, user_jid,
                   intent, confidence, detected_keywords,
                   strategy_selected, strategy_reasoning,
                   tone, response_quality_score, created_at
            FROM ai_thoughts
            WHERE user_jid = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (jid, page_size, offset),
        ).fetchall()

    import json as _json
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["detected_keywords"] = _json.loads(d["detected_keywords"] or "[]")
        except Exception:
            d["detected_keywords"] = []
        results.append(d)

    return jsonify({
        "jid": jid,
        "page": page,
        "page_size": page_size,
        "total": total,
        "thoughts": results,
    }), 200


# ---------------------------------------------------------------------------
# Phase 3  Strategy engine endpoints
# ---------------------------------------------------------------------------

# Allowed field values (mirrors strategy_manager.py constants)
_VALID_RESPONSE_STYLES = {"formal", "casual", "concise", "detailed"}
_VALID_TONES = {"polite", "friendly", "professional", "empathetic", "neutral"}
_VALID_LANGUAGES = {"auto", "zh", "en", "mixed"}


def _validate_strategy_config(config: dict):
    """
    Validate strategy config fields.  Returns (ok: bool, error_msg: str|None).
    Unknown extra keys are silently ignored.
    """
    if not isinstance(config, dict):
        return False, "config must be a JSON object"
    style = config.get("response_style")
    tone = config.get("tone")
    language = config.get("language")
    custom = config.get("custom_instructions")

    if style is not None and style not in _VALID_RESPONSE_STYLES:
        return False, f"response_style must be one of {sorted(_VALID_RESPONSE_STYLES)}"
    if tone is not None and tone not in _VALID_TONES:
        return False, f"tone must be one of {sorted(_VALID_TONES)}"
    if language is not None and language not in _VALID_LANGUAGES:
        return False, f"language must be one of {sorted(_VALID_LANGUAGES)}"
    if custom is not None and not isinstance(custom, str):
        return False, "custom_instructions must be a string"
    return True, None


def _get_strategy_manager(db_path: str):
    from app.dashboard.strategy.strategy_manager import StrategyManager
    return StrategyManager(db_path)


@bp.route("/apply-strategy", methods=["POST"])
@limiter.limit("20/minute")
def apply_strategy():
    """
    Apply (or update) a personal strategy for a specific JID.

    Body JSON:
        jid     (required) WhatsApp JID
        config  (required) strategy config dict
        note    (optional) human-readable note for audit log
    """
    body = request.get_json(silent=True) or {}
    jid = (body.get("jid") or "").strip()
    config = body.get("config")
    note = body.get("note")

    if not jid:
        return jsonify({"error": "jid is required"}), 400
    if config is None:
        return jsonify({"error": "config is required"}), 400

    ok, err = _validate_strategy_config(config)
    if not ok:
        return jsonify({"error": err}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        strategy_id = sm.apply_strategy(jid, config, note=note)
    except Exception as e:
        logger.exception("apply_strategy failed")
        return jsonify({"error": str(e)}), 500

    # Phase 4: emit WebSocket event
    try:
        from app.dashboard.api.websocket import emit_strategy_applied
        emit_strategy_applied(jid, config)
    except Exception:
        pass

    return jsonify({
        "strategy_id": strategy_id,
        "jid": jid,
        "config": config,
        "note": note,
    }), 201


@bp.route("/apply-global-strategy", methods=["POST"])
@limiter.limit("20/minute")
def apply_global_strategy():
    """
    Apply (or update) the global strategy (affects all JIDs unless overridden).

    Body JSON:
        config  (required) strategy config dict
        note    (optional) human-readable note
    """
    body = request.get_json(silent=True) or {}
    config = body.get("config")
    note = body.get("note")

    if config is None:
        return jsonify({"error": "config is required"}), 400

    ok, err = _validate_strategy_config(config)
    if not ok:
        return jsonify({"error": err}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        strategy_id = sm.apply_global_strategy(config, note=note)
    except Exception as e:
        logger.exception("apply_global_strategy failed")
        return jsonify({"error": str(e)}), 500

    # Phase 4: emit WebSocket event (broadcast — global strategy affects all users)
    try:
        from app.dashboard.api.websocket import emit_strategy_applied
        emit_strategy_applied(None, config)
    except Exception:
        pass

    return jsonify({
        "strategy_id": strategy_id,
        "config": config,
        "note": note,
    }), 201


@bp.route("/strategy", methods=["GET"])
def get_strategy():
    """
    Return current active strategy for a JID (personal + global merged).

    Query params:
        jid  (optional) — omit to query global strategy only
    """
    jid = request.args.get("jid", "").strip() or None
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        raw = sm.get_raw_strategies(jid)
        merged = sm.get_active_strategy(jid)
    except Exception as e:
        logger.exception("get_strategy failed")
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "jid": jid,
        "global_strategy": raw["global"],
        "personal_strategy": raw["personal"],
        "merged_strategy": merged,
    }), 200


@bp.route("/strategy/history", methods=["GET"])
def strategy_history():
    """
    Return strategy application history.

    Query params:
        jid    (optional) — omit for global strategy history
        limit  (optional, default 20, max 100)
    """
    jid = request.args.get("jid", "").strip() or None
    try:
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        history = sm.get_history(jid, limit)
    except Exception as e:
        logger.exception("strategy_history failed")
        return jsonify({"error": str(e)}), 500

    return jsonify({"jid": jid, "history": history}), 200


@bp.route("/strategy/rollback", methods=["POST"])
def strategy_rollback():
    """
    Roll back the current strategy to the previous version.

    Body JSON:
        jid  (optional) — omit to roll back global strategy
    """
    body = request.get_json(silent=True) or {}
    jid = (body.get("jid") or "").strip() or None

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        success = sm.rollback_strategy(jid)
    except Exception as e:
        logger.exception("strategy_rollback failed")
        return jsonify({"error": str(e)}), 500

    if success:
        return jsonify({"success": True, "jid": jid}), 200
    return jsonify({
        "success": False,
        "message": "No previous strategy version found to roll back to",
        "jid": jid,
    }), 409


@bp.route("/strategy/conflicts", methods=["GET"])
def strategy_conflicts():
    """
    Return live conflict detection result for a JID.

    Query params:
        jid   (required) WhatsApp JID
    """
    jid = request.args.get("jid", "").strip()
    if not jid:
        return jsonify({"error": "jid is required"}), 400

    db_path = current_app.config["DASHBOARD_DB_PATH"]
    try:
        sm = _get_strategy_manager(db_path)
        conflicts = sm.detect_conflicts(jid)
    except Exception as e:
        logger.exception("strategy_conflicts failed")
        return jsonify({"error": str(e)}), 500

    return jsonify({"jid": jid, "conflicts": conflicts}), 200


# ---------------------------------------------------------------------------
# 404 / 405 handlers
# ---------------------------------------------------------------------------

@bp.app_errorhandler(404)
def not_found(_e):
    return jsonify({"error": "endpoint not found"}), 404


@bp.app_errorhandler(405)
def method_not_allowed(_e):
    return jsonify({"error": "method not allowed"}), 405
