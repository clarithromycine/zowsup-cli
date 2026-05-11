"""app/dashboard/api/agent_gateway.py
────────────────────────────────────
Agent ↔ Backend WebSocket gateway  (/agent namespace)

Design
──────
Agents are *defined* on the server (via agents_store / REST API) with an
auto-generated HMAC secret.  Each defined agent has a unique agent_id.
When the agent process starts on a remote machine it authenticates using
that same agent_id + secret.  The backend then marks it online.

Connect auth payload (sent by agent on connect)
───────────────────────────────────────────────
{
  "agent_id":  "server-hk-01",   # must match a defined agent
  "signed_at": 1715000000,
  "sig":       "<hex HMAC-SHA256 of '{agent_id}:{signed_at}'>"
}

Commands dispatched to agents (from backend → agent)
─────────────────────────────────────────────────────
start_bot    {"phone": "..."}
stop_bot     {"phone": "..."}
get_status   {"phone": "..."} or {} for all
list_phones  {}

Events from agents (from agent → backend → frontend)
─────────────────────────────────────────────────────
bot_log      forwarded as `bot_log` in "/" namespace
bot_status   forwarded as `bot_status_changed` in "/" namespace
heartbeat    forwarded as `agent:heartbeat`
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Module-level SocketIO reference (set by register_agent_namespace) ─────────
_sio = None

# ── Command-job configuration ─────────────────────────────────────────────────
_CMD_MAX_ATTEMPTS: int = int(os.environ.get("AGENT_CMD_MAX_ATTEMPTS", "3"))
_CMD_TIMEOUT_S: float = float(os.environ.get("AGENT_CMD_TIMEOUT", "15"))

# ── Bot start failure tracking ────────────────────────────────────────────────
# phone → consecutive start failures
_start_fail_counts: dict[str, int] = {}
_START_FAIL_ALERT_THRESHOLD: int = int(os.environ.get("AGENT_BOT_FAIL_THRESHOLD", "3"))
_start_fail_lock = threading.Lock()

# ── Agent registry ─────────────────────────────────────────────────────────────
# sid -> {"agent_id": str, "phones": list[str], "connected_at": float}
_agents_by_sid: dict[str, dict] = {}
# agent_id -> sid
_sid_by_agent: dict[str, str] = {}
# phone (digits only, no +) -> agent_id
_agent_by_phone: dict[str, str] = {}
_registry_lock = threading.Lock()

# ── Agent-reported bot statuses ────────────────────────────────────────────────
# phone -> {"running": bool, "jid": str|None, "agent_id": str}
# Updated from heartbeat and bot_status agent events.
_agent_bot_status: dict[str, dict] = {}
_bot_status_lock = threading.Lock()

# ── Pending command table ───────────────────────────────────────────────────────
# cmd_id -> {"event": threading.Event, "result": dict | None}
_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()

# ── Key store ───────────────────────────────────────────────────────────────────
_KEY_STORE: dict[str, bytes] = {}


def _load_keys() -> None:
    """Load env-var fallback secrets (legacy quick-start support)."""
    global _KEY_STORE
    keys: dict[str, bytes] = {}
    single_id = os.environ.get("AGENT_KEY_ID", "").strip()
    single_sec = os.environ.get("AGENT_KEY_SECRET", "").strip()
    if single_id and single_sec:
        keys[single_id] = bytes.fromhex(single_sec) if len(single_sec) == 64 else single_sec.encode()
    _KEY_STORE = keys


def _resolve_secret(agent_id: str) -> Optional[bytes]:
    """
    Resolve the HMAC secret for *agent_id* at connect time.
    Priority: agents_store (data/agents.json) > env var fallback.
    New agents added via API take effect immediately without restart.
    """
    try:
        from app.dashboard.utils.agents_store import get_agent_secret
        secret = get_agent_secret(agent_id)
        if secret is not None:
            return secret
    except Exception:
        pass
    return _KEY_STORE.get(agent_id)


def _verify_connect_auth(auth: Any) -> Optional[str]:
    """Return agent_id on success, None on rejection."""
    if not isinstance(auth, dict):
        return None
    agent_id = str(auth.get("agent_id", "")).strip()
    sig = str(auth.get("sig", "")).strip()
    try:
        signed_at = int(auth.get("signed_at", 0))
    except (TypeError, ValueError):
        return None
    if not (agent_id and sig):
        return None
    if abs(int(time.time()) - signed_at) > 120:
        logger.warning("Agent %s auth: time window exceeded", agent_id)
        return None
    secret = _resolve_secret(agent_id)
    if secret is None:
        logger.warning("Agent %s: not a defined agent or no secret", agent_id)
        return None
    expected = hmac.new(
        secret,
        f"{agent_id}:{signed_at}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        logger.warning("Agent %s auth: signature mismatch", agent_id)
        return None
    return agent_id


# ── Public API ──────────────────────────────────────────────────────────────────

def get_agent_for_phone(phone: str) -> Optional[str]:
    """Return agent_id that manages *phone*, or None."""
    with _registry_lock:
        return _agent_by_phone.get(phone.lstrip("+"))


def get_agent_running_phones() -> set[str]:
    """Return the set of phone numbers that agents currently report as running."""
    with _bot_status_lock:
        return {ph for ph, st in _agent_bot_status.items() if st.get("running")}


def get_agent_phone_status(phone: str) -> Optional[dict]:
    """Return the latest status dict for *phone* as reported by its agent."""
    with _bot_status_lock:
        return _agent_bot_status.get(phone.lstrip("+"))


def get_all_agent_phones() -> dict[str, str]:
    """Return {phone: agent_id} for every phone currently registered by a connected agent."""
    with _registry_lock:
        return dict(_agent_by_phone)


def get_all_agents() -> list[dict]:
    """Snapshot of connected agents."""
    now = time.time()
    with _registry_lock:
        return [
            {
                "agent_id": v["agent_id"],
                "phones": list(v["phones"]),
                "connected_at": v["connected_at"],
                "uptime_seconds": int(now - v["connected_at"]),
            }
            for v in _agents_by_sid.values()
        ]


# ── Agent command-job DB helpers ──────────────────────────────────────────────

def _get_db_path() -> Optional[str]:
    try:
        from app.dashboard.config import CONFIG
        return CONFIG.get("DASHBOARD_DB_PATH")
    except Exception:
        return None


def _job_create(job_id: str, agent_id: str, cmd_type: str, payload: dict) -> None:
    """Insert a new command job record with state='queued'."""
    db = _get_db_path()
    if not db:
        return
    now = int(time.time())
    try:
        with sqlite3.connect(db, timeout=5) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO agent_command_jobs "
                "(job_id, agent_id, command_name, request_payload, state, attempt, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'queued', 0, ?, ?)",
                (job_id, agent_id, cmd_type, json.dumps(payload), now, now),
            )
    except Exception as exc:
        logger.debug("_job_create failed: %s", exc)


def _job_update(job_id: str, state: str, result: Optional[dict] = None,
                error: Optional[str] = None, attempt: Optional[int] = None) -> None:
    """Update job state and optionally its result/error."""
    db = _get_db_path()
    if not db:
        return
    now = int(time.time())
    try:
        with sqlite3.connect(db, timeout=5) as conn:
            if attempt is not None:
                conn.execute(
                    "UPDATE agent_command_jobs SET state=?, result_payload=?, error=?, "
                    "attempt=?, updated_at=? WHERE job_id=?",
                    (state, json.dumps(result) if result is not None else None,
                     error, attempt, now, job_id),
                )
            else:
                conn.execute(
                    "UPDATE agent_command_jobs SET state=?, result_payload=?, error=?, "
                    "updated_at=? WHERE job_id=?",
                    (state, json.dumps(result) if result is not None else None,
                     error, now, job_id),
                )
    except Exception as exc:
        logger.debug("_job_update failed: %s", exc)


def _bot_instance_upsert(phone: str, agent_id: str, running: bool,
                          jid: Optional[str] = None, pid: Optional[int] = None) -> None:
    """Insert or update the bot_instances row for *phone*."""
    db = _get_db_path()
    if not db:
        return
    now = int(time.time())
    try:
        with sqlite3.connect(db, timeout=5) as conn:
            conn.execute(
                "INSERT INTO bot_instances (phone, agent_id, bot_jid, pid, running, last_status_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(phone) DO UPDATE SET "
                "  agent_id=excluded.agent_id, "
                "  bot_jid=COALESCE(excluded.bot_jid, bot_jid), "
                "  pid=excluded.pid, "
                "  running=excluded.running, "
                "  last_status_at=excluded.last_status_at",
                (phone, agent_id, jid, pid, int(running), now, now),
            )
    except Exception as exc:
        logger.debug("_bot_instance_upsert failed: %s", exc)


def _agent_upsert(agent_id: str, status: str) -> None:
    """Insert or update the agents row for *agent_id*."""
    db = _get_db_path()
    if not db:
        return
    now = int(time.time())
    try:
        with sqlite3.connect(db, timeout=5) as conn:
            conn.execute(
                "INSERT INTO agents (agent_id, note, status, last_seen_at, created_at, updated_at) "
                "VALUES (?, '', ?, ?, ?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET status=excluded.status, "
                "  last_seen_at=excluded.last_seen_at, updated_at=excluded.updated_at",
                (agent_id, status, now, now, now),
            )
    except Exception as exc:
        logger.debug("_agent_upsert failed: %s", exc)


def dispatch_command(
    agent_id: str,
    cmd_type: str,
    payload: dict,
    timeout: float = _CMD_TIMEOUT_S,
) -> Optional[dict]:
    """
    Send a command to an agent and wait for its ack.

    Features:
    - Persists job to agent_command_jobs (idempotency / audit trail).
    - Retries up to AGENT_CMD_MAX_ATTEMPTS times on timeout.
    - Marks job as 'dead' and emits an alert after all retries exhausted.

    Returns the ack payload dict on success, None on timeout or no agent.
    Thread-safe; can be called from any Flask request thread.
    """
    if _sio is None:
        return None
    with _registry_lock:
        sid = _sid_by_agent.get(agent_id)
    if sid is None:
        return None

    job_id = str(uuid.uuid4())
    _job_create(job_id, agent_id, cmd_type, payload)

    for attempt in range(1, _CMD_MAX_ATTEMPTS + 1):
        _job_update(job_id, "sent", attempt=attempt)
        ev = threading.Event()
        with _pending_lock:
            _pending[job_id] = {"event": ev, "result": None}
        try:
            _sio.emit(
                "command",
                {"cmd_id": job_id, "type": cmd_type, "payload": payload},
                to=sid,
                namespace="/agent",
            )
            ev.wait(timeout=timeout)
            with _pending_lock:
                rec = _pending.pop(job_id, {})
            result = rec.get("result")
            if result is not None:
                # Command was acknowledged
                success = result.get("ok", True)
                state = "succeeded" if success else "failed"
                error = result.get("error") if not success else None
                _job_update(job_id, state, result=result, error=error)
                # Track bot start failures
                if cmd_type == "start_bot":
                    phone = str(payload.get("phone", "")).lstrip("+")
                    if phone:
                        with _start_fail_lock:
                            if success:
                                _start_fail_counts.pop(phone, None)
                            else:
                                count = _start_fail_counts.get(phone, 0) + 1
                                _start_fail_counts[phone] = count
                                if count >= _START_FAIL_ALERT_THRESHOLD:
                                    _emit_alert("bot_start_failures", {
                                        "agent_id": agent_id,
                                        "phone": phone,
                                        "consecutive_failures": count,
                                        "last_error": error,
                                    })
                return result
            # Timed out — check if agent is still connected before retrying
            with _registry_lock:
                still_connected = agent_id in _sid_by_agent
            if not still_connected:
                _job_update(job_id, "failed", error="agent disconnected during command")
                return None
            logger.warning(
                "Command %s type=%s timed out (attempt %d/%d)",
                job_id, cmd_type, attempt, _CMD_MAX_ATTEMPTS,
            )
            _emit_alert("command_timeout", {
                "agent_id": agent_id,
                "cmd_type": cmd_type,
                "job_id": job_id,
                "attempt": attempt,
                "max_attempts": _CMD_MAX_ATTEMPTS,
            })
        except Exception as exc:
            logger.error("dispatch_command attempt %d failed: %s", attempt, exc)
            with _pending_lock:
                _pending.pop(job_id, None)
            _job_update(job_id, "failed", error=str(exc))
            return None

    # All retries exhausted → dead letter
    _job_update(job_id, "dead", error=f"all {_CMD_MAX_ATTEMPTS} attempts timed out")
    _emit_alert("command_dead", {
        "agent_id": agent_id,
        "cmd_type": cmd_type,
        "job_id": job_id,
        "attempts": _CMD_MAX_ATTEMPTS,
        "payload": payload,
    })
    logger.error(
        "Command %s type=%s moved to dead letter after %d attempts",
        job_id, cmd_type, _CMD_MAX_ATTEMPTS,
    )
    return None


# ── Alert helper ──────────────────────────────────────────────────────────────

def _emit_alert(alert_type: str, data: dict) -> None:
    """Emit an alert event to all connected frontend clients."""
    if _sio is None:
        return
    try:
        _sio.emit(
            "agent_alert",
            {"alert_type": alert_type, "ts": int(time.time()), **data},
            namespace="/",
        )
        logger.warning("ALERT %s: %s", alert_type, data)
    except Exception as exc:
        logger.debug("_emit_alert failed: %s", exc)


# ── Namespace registration ───────────────────────────────────────────────────────

# agent_id → last heartbeat timestamp
_agent_last_heartbeat: dict[str, float] = {}
_heartbeat_lock = threading.Lock()
# Seconds without a heartbeat before an overdue alert fires (default 90s = 3 × 30s interval)
_HEARTBEAT_OVERDUE_S: float = float(os.environ.get("AGENT_HEARTBEAT_OVERDUE", "90"))


def register_agent_namespace(sio) -> None:
    """Attach /agent namespace handlers to the Flask-SocketIO instance."""
    global _sio
    _sio = sio
    _load_keys()

    @sio.on("connect", namespace="/agent")
    def on_agent_connect(auth=None):
        from flask import request as freq
        from flask_socketio import disconnect

        sid = freq.sid
        agent_id = _verify_connect_auth(auth)
        if agent_id is None:
            logger.warning("Rejected agent connection SID=%s", sid)
            disconnect(sid=sid, namespace="/agent")
            return False

        with _registry_lock:
            # Remove stale SID if agent reconnects from same agent_id
            old_sid = _sid_by_agent.get(agent_id)
            if old_sid and old_sid in _agents_by_sid:
                del _agents_by_sid[old_sid]
            _agents_by_sid[sid] = {
                "agent_id": agent_id,
                "phones": [],
                "connected_at": time.time(),
            }
            _sid_by_agent[agent_id] = sid

        with _heartbeat_lock:
            _agent_last_heartbeat[agent_id] = time.time()

        _agent_upsert(agent_id, "online")
        logger.info("Agent %s connected (SID=%s)", agent_id, sid)
        sio.emit("agent_connected", {"agent_id": agent_id}, namespace="/")

    @sio.on("disconnect", namespace="/agent")
    def on_agent_disconnect():
        from flask import request as freq

        sid = freq.sid
        with _registry_lock:
            info = _agents_by_sid.pop(sid, None)
            if info:
                aid = info["agent_id"]
                _sid_by_agent.pop(aid, None)
                for ph in info.get("phones", []):
                    if _agent_by_phone.get(ph) == aid:
                        _agent_by_phone.pop(ph, None)
                # Mark all phones this agent managed as not running
                with _bot_status_lock:
                    for ph, st in list(_agent_bot_status.items()):
                        if st.get("agent_id") == aid:
                            _agent_bot_status[ph] = {**st, "running": False}
                            _bot_instance_upsert(ph, aid, running=False)

                _agent_upsert(aid, "offline")
                logger.info("Agent %s disconnected", aid)
                sio.emit("agent_disconnected", {"agent_id": aid}, namespace="/")
                _emit_alert("agent_offline", {
                    "agent_id": aid,
                    "phones": list(info.get("phones", [])),
                })

    @sio.on("agent_ready", namespace="/agent")
    def on_agent_ready(data):
        """Agent sends this right after connect with its managed phone list."""
        from flask import request as freq

        sid = freq.sid
        phones: list[str] = []
        if isinstance(data, dict):
            phones = [str(p).strip().lstrip("+") for p in data.get("phones", []) if p]

        with _registry_lock:
            info = _agents_by_sid.get(sid)
            if not info:
                return
            aid = info["agent_id"]
            # Clear old phone registrations for this agent
            for ph in info.get("phones", []):
                if _agent_by_phone.get(ph) == aid:
                    _agent_by_phone.pop(ph, None)
            info["phones"] = phones
            for ph in phones:
                _agent_by_phone[ph] = aid

        logger.info("Agent %s manages phones: %s", aid, phones)
        sio.emit("agent_phones_updated", {"agent_id": aid, "phones": phones}, namespace="/")

    @sio.on("agent_event", namespace="/agent")
    def on_agent_event(data):
        """Agent pushes events (bot_log, bot_status, heartbeat, …)."""
        from flask import request as freq

        sid = freq.sid
        if not isinstance(data, dict):
            return
        ev_type = str(data.get("type", ""))
        payload = data.get("payload") or {}
        with _registry_lock:
            info = _agents_by_sid.get(sid)
        agent_id = info["agent_id"] if info else "unknown"

        if ev_type == "bot_log":
            sio.emit("bot_log", {**payload, "source": "agent", "agent_id": agent_id}, namespace="/")
        elif ev_type == "bot_status":
            # Single bot status update — store it
            phone = str(payload.get("phone", "")).lstrip("+")
            if phone:
                running = bool(payload.get("running"))
                jid = payload.get("jid")
                with _bot_status_lock:
                    _agent_bot_status[phone] = {
                        "running": running,
                        "jid": jid,
                        "agent_id": agent_id,
                    }
                # Also register this phone in _agent_by_phone if not already there
                # (handles phones started after agent connected that weren't in agent_ready)
                with _registry_lock:
                    if _agent_by_phone.get(phone) != agent_id:
                        _agent_by_phone[phone] = agent_id
                        if info:
                            if phone not in info.get("phones", []):
                                info.setdefault("phones", []).append(phone)
                _bot_instance_upsert(phone, agent_id, running=running, jid=jid)
            sio.emit("bot_status_changed", {**payload, "agent_id": agent_id}, namespace="/")
        elif ev_type == "heartbeat":
            # Update last-heartbeat timestamp for overdue detection
            with _heartbeat_lock:
                _agent_last_heartbeat[agent_id] = time.time()
            _agent_upsert(agent_id, "online")
            # Bulk status from heartbeat
            bots = payload.get("bots") or []
            with _bot_status_lock:
                for bot in bots:
                    if not isinstance(bot, dict):
                        continue
                    phone = str(bot.get("phone", "")).lstrip("+")
                    if phone:
                        running = bool(bot.get("running"))
                        jid = bot.get("jid")
                        _agent_bot_status[phone] = {
                            "running": running,
                            "jid": jid,
                            "agent_id": agent_id,
                        }
                        _bot_instance_upsert(phone, agent_id, running=running, jid=jid)
            sio.emit(f"agent:{ev_type}", {**payload, "agent_id": agent_id}, namespace="/")
        else:
            sio.emit(f"agent:{ev_type}", {**payload, "agent_id": agent_id}, namespace="/")

    @sio.on("command_ack", namespace="/agent")
    def on_command_ack(data):
        """Agent acknowledges a command with its result."""
        if not isinstance(data, dict):
            return
        from flask import request as freq
        sid = freq.sid
        cmd_id = str(data.get("cmd_id", ""))
        cmd_type = data.get("type", "")

        # For start/stop commands, eagerly update _agent_bot_status HERE,
        # before waking dispatch_command.  This ensures that by the time the
        # HTTP response reaches the frontend and it calls fetchBotAccounts(),
        # the status is already correct — avoiding the race condition where
        # on_agent_event (with the bot_status payload) runs in a separate
        # thread and may finish after dispatch_command returns.
        if cmd_type in ("start_bot", "stop_bot") and data.get("ok"):
            phone = str(data.get("phone", "")).lstrip("+")
            if phone:
                with _registry_lock:
                    info = _agents_by_sid.get(sid)
                agent_id = info["agent_id"] if info else None
                if agent_id:
                    running = (cmd_type == "start_bot")
                    with _bot_status_lock:
                        existing = _agent_bot_status.get(phone, {})
                        _agent_bot_status[phone] = {
                            **existing,
                            "running": running,
                            "agent_id": agent_id,
                        }
                    with _registry_lock:
                        if _agent_by_phone.get(phone) != agent_id:
                            _agent_by_phone[phone] = agent_id
                            if info and phone not in info.get("phones", []):
                                info.setdefault("phones", []).append(phone)
                    # Push the status change to the frontend
                    sio.emit(
                        "bot_status_changed",
                        {"phone": phone, "running": running, "agent_id": agent_id},
                        namespace="/",
                    )

        with _pending_lock:
            rec = _pending.get(cmd_id)
        if rec:
            rec["result"] = data
            rec["event"].set()

    # ── Heartbeat-overdue monitor ────────────────────────────────────────────
    def _heartbeat_monitor_loop() -> None:
        """
        Background thread: checks every 30 s if any connected agent has missed
        heartbeats for longer than AGENT_HEARTBEAT_OVERDUE seconds.
        Emits 'agent_heartbeat_overdue' alert and marks agent as 'degraded'.
        """
        while True:
            time.sleep(30)
            now = time.time()
            with _heartbeat_lock:
                snapshot = dict(_agent_last_heartbeat)
            with _registry_lock:
                connected = set(_sid_by_agent.keys())
            for aid, last_ts in snapshot.items():
                if aid not in connected:
                    continue
                overdue = now - last_ts
                if overdue > _HEARTBEAT_OVERDUE_S:
                    logger.warning(
                        "Agent %s heartbeat overdue: %.0f s (threshold %.0f s)",
                        aid, overdue, _HEARTBEAT_OVERDUE_S,
                    )
                    _agent_upsert(aid, "degraded")
                    _emit_alert("agent_heartbeat_overdue", {
                        "agent_id": aid,
                        "seconds_since_heartbeat": int(overdue),
                        "threshold": int(_HEARTBEAT_OVERDUE_S),
                    })

    threading.Thread(
        target=_heartbeat_monitor_loop,
        daemon=True,
        name="agent-heartbeat-monitor",
    ).start()
