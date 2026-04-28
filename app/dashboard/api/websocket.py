"""
WebSocket event handlers (Flask-SocketIO, async_mode='threading').

Architecture constraint: NO eventlet / gevent.
The 'threading' async_mode is the only safe choice given the project's
asyncio bot process running in a separate process.

Server → Client events:
    new_message      {jid, message: {id, direction, content, message_type, timestamp}}
    profile_updated  {jid, profile: {...}}
    strategy_applied {jid|null, strategy: {...}}

Client → Server events:
    subscribe_user   {jid}   — join room 'user:<jid>'
    unsubscribe_user {jid}   — leave room

Background monitor:
    Polls chat_messages every 2 s; emits new_message to the correct room
    for any rows inserted since last check.
"""

import logging
import os
import sqlite3
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conditional import so the rest of the app starts even if flask-socketio
# is not installed.
# ---------------------------------------------------------------------------
try:
    from flask_socketio import SocketIO, join_room, leave_room
    _SOCKETIO_AVAILABLE = True
except ImportError:
    _SOCKETIO_AVAILABLE = False
    logger.warning("flask-socketio not installed — WebSocket features disabled")

# Module-level singleton; populated by init_socketio().
socketio: Optional["SocketIO"] = None

_monitor_thread: Optional[threading.Thread] = None
_monitor_lock = threading.Lock()


# ---------------------------------------------------------------------------
# App-factory integration
# ---------------------------------------------------------------------------

def init_socketio(app) -> Optional["SocketIO"]:
    """
    Create a SocketIO instance and attach it to the Flask app.

    Returns the SocketIO object (or None if unavailable).
    Must be called before socketio.run() in run_dashboard.py.
    In TESTING mode SocketIO is still initialised so test_client() works;
    only the background monitor thread is suppressed.
    """
    global socketio

    if not _SOCKETIO_AVAILABLE:
        return None

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",   # no eventlet / gevent — compatible with asyncio bot
        logger=False,
        engineio_logger=False,
    )
    _register_events(socketio)
    logger.info("Flask-SocketIO initialised (async_mode=threading)")
    return socketio


# ---------------------------------------------------------------------------
# Client → Server event handlers
# ---------------------------------------------------------------------------

def _register_events(sio: "SocketIO") -> None:

    @sio.on("connect")
    def on_connect():
        # All clients join the global room to receive new-contact notifications
        join_room("global")
        logger.debug("WebSocket client connected")

    @sio.on("disconnect")
    def on_disconnect():
        logger.debug("WebSocket client disconnected")

    @sio.on("subscribe_user")
    def on_subscribe_user(data):
        jid = (data or {}).get("jid", "")
        if jid:
            join_room(f"user:{jid}")
            logger.debug("WS client subscribed to room user:%s", jid)

    @sio.on("unsubscribe_user")
    def on_unsubscribe_user(data):
        jid = (data or {}).get("jid", "")
        if jid:
            leave_room(f"user:{jid}")
            logger.debug("WS client unsubscribed from room user:%s", jid)


# ---------------------------------------------------------------------------
# Background DB-monitor → emit loop
# ---------------------------------------------------------------------------

def start_monitor_thread(db_path: str) -> None:
    """
    Start the background thread that polls for new chat_messages and emits
    new_message WebSocket events.  Idempotent — safe to call multiple times.
    """
    global _monitor_thread
    if os.environ.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    with _monitor_lock:
        if _monitor_thread and _monitor_thread.is_alive():
            return
        _monitor_thread = threading.Thread(
            target=_monitor_loop,
            args=(db_path,),
            daemon=True,
            name="ws-db-monitor",
        )
        _monitor_thread.start()
    logger.info("WebSocket DB-monitor thread started (poll interval: 2 s)")


def _monitor_loop(db_path: str) -> None:
    """Poll for new rows; emit new_message for each one found."""
    last_id = _latest_message_id(db_path)
    while True:
        time.sleep(2)
        try:
            if socketio is None:
                continue
            new_rows = _fetch_new_messages(db_path, last_id)
            for row in new_rows:
                last_id = max(last_id, row["id"])
                emit_new_message(row)
        except Exception:
            logger.exception("WebSocket monitor error")


def _latest_message_id(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        val = conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM chat_messages"
        ).fetchone()[0]
        conn.close()
        return val
    except Exception:
        return 0


def _fetch_new_messages(db_path: str, after_id: int) -> list:
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, user_jid, direction, content, message_type, timestamp "
        "FROM chat_messages WHERE id > ? ORDER BY id ASC LIMIT 50",
        (after_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Server → Client emit helpers
# (callable from routes, scheduler callbacks, etc.)
# ---------------------------------------------------------------------------

def emit_new_message(msg: dict) -> None:
    """Emit new_message to the user:<jid> room and the global room."""
    if socketio is None:
        return
    jid = msg.get("user_jid", "")
    payload = {
        "jid": jid,
        "message": {
            "id": msg["id"],
            "user_jid": jid,
            "direction": msg["direction"],
            "content": msg["content"],
            "message_type": msg.get("message_type", "text"),
            "timestamp": msg.get("timestamp"),
            "created_at": msg.get("created_at", ""),
        },
    }
    # Emit to the per-user room (subscribers see it) AND global (for contact-list updates)
    socketio.emit("new_message", payload, room=f"user:{jid}")
    socketio.emit("new_message", payload, room="global")


def emit_strategy_applied(jid: Optional[str], strategy: dict) -> None:
    """
    Emit strategy_applied.
    If jid is None → broadcast to all connected clients (global strategy change).
    """
    if socketio is None:
        return
    payload = {"jid": jid, "strategy": strategy}
    if jid:
        socketio.emit("strategy_applied", payload, room=f"user:{jid}")
    else:
        socketio.emit("strategy_applied", payload)


def emit_profile_updated(jid: str, profile: dict) -> None:
    """Emit profile_updated to the user's room."""
    if socketio is None:
        return
    socketio.emit(
        "profile_updated",
        {"jid": jid, "profile": profile},
        room=f"user:{jid}",
    )
