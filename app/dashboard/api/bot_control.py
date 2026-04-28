"""
app/dashboard/api/bot_control.py
─────────────────────────────────
Phase 5: Bot login management API.

Endpoints
---------
GET  /api/bot/status          — Current bot running state (reads data/bot_status.json)
POST /api/bot/login-scan      — Launch regwithscan.py subprocess; returns {pid}
GET  /api/bot/qr-stream       — SSE stream that pushes QR-code lines from subprocess stdout
POST /api/bot/login-linkcode  — Launch regwithlinkcode.py; return 8-char link code
POST /api/bot/logout          — Send SIGTERM to running bot via PID in status file

Design constraints
------------------
- Everything is synchronous WSGI; no asyncio, no eventlet/gevent.
- Bot communication is file-based (data/bot_status.json, data/bot.pid).
- Subprocess stdout is read with Popen(stdout=PIPE) — never blocking run().
- QR stream ends automatically when subprocess exits or bot logs in.
- All mutating endpoints (POST) are rate-limited via the shared limiter.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Blueprint, Response, current_app, request, stream_with_context

from app.dashboard.api.auth import check_bearer
from app.dashboard.api.rate_limit import limiter
from app.dashboard.utils.bot_status import read_status, _pid_alive

logger = logging.getLogger(__name__)

bot_bp = Blueprint("bot", __name__)

# Path to the running QR subprocess, held in memory.
# Single-instance assumption: only one scan session at a time.
_qr_proc: "subprocess.Popen | None" = None

_PID_FILE = Path("data") / "bot.pid"
_BOT_STARTUP_TIMEOUT = 30  # seconds to wait for link-code to appear
_BOT_CONNECT_TIMEOUT = 60  # seconds to wait for main.py to reach running state

# Running main.py process started via /api/bot/start (kept for log streaming)
_start_proc: "subprocess.Popen | None" = None


# ---------------------------------------------------------------------------
# Auth guard applied to every route in this blueprint
# ---------------------------------------------------------------------------

@bot_bp.before_request
def _bot_auth():
    result = check_bearer()
    if result is not None:
        return result


# ---------------------------------------------------------------------------
# B.1  GET /api/bot/status
# ---------------------------------------------------------------------------

@bot_bp.get("/status")
def get_bot_status():
    """Return running state of the bot process."""
    status = read_status()
    uptime: int | None = None
    if status.get("running") and status.get("started_at"):
        uptime = int(time.time() - status["started_at"])
    return {
        "running": status.get("running", False),
        "jid": status.get("jid"),
        "pid": status.get("pid"),
        "started_at": status.get("started_at"),
        "uptime_seconds": uptime,
    }


# ---------------------------------------------------------------------------
# B.2  POST /api/bot/login-scan
# ---------------------------------------------------------------------------

@bot_bp.post("/login-scan")
@limiter.limit("5 per minute")
def post_login_scan():
    """
    Launch regwithscan.py as a background subprocess.
    The QR output will be streamed via GET /api/bot/qr-stream.
    """
    global _qr_proc

    # Kill any previous scan process
    _kill_qr_proc()

    script_path = _resolve_script("regwithscan.py")
    if not script_path.exists():
        return {"error": "regwithscan.py not found"}, 404

    try:
        _qr_proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path.cwd()),
        )
        _write_pid_file(_qr_proc.pid)
        logger.info("QR scan subprocess started, PID=%s", _qr_proc.pid)
        return {"ok": True, "pid": _qr_proc.pid}
    except OSError as exc:
        logger.error("Failed to start regwithscan.py: %s", exc)
        return {"error": str(exc)}, 500


# ---------------------------------------------------------------------------
# B.3  GET /api/bot/qr-stream
# ---------------------------------------------------------------------------

@bot_bp.get("/qr-stream")
def get_qr_stream():
    """
    SSE stream that pushes QR-code data from the running scan subprocess.

    Event format:
        event: qr
        data: <base64-encoded QR terminal string>  ← one terminal line per event

        event: status
        data: {"type": "login_success"} | {"type": "timeout"} | {"type": "error", "msg": "..."}
    """
    global _qr_proc

    def generate():
        proc = _qr_proc
        if proc is None or proc.poll() is not None:
            yield _sse_event("status", {"type": "error", "msg": "No active scan session"})
            return

        deadline = time.time() + 300  # 5-minute max stream duration
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if time.time() > deadline:
                    yield _sse_event("status", {"type": "timeout"})
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                # Detect successful login by looking for JID in output
                if "@" in line and ".net" in line:
                    yield _sse_event("status", {"type": "login_success", "jid": line.strip()})
                    break
                yield _sse_event("qr", line)
        except Exception as exc:
            logger.warning("QR stream error: %s", exc)
            yield _sse_event("status", {"type": "error", "msg": str(exc)})
        finally:
            # Don't kill process here — it may still be verifying login
            pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# B.4  POST /api/bot/login-linkcode
# ---------------------------------------------------------------------------

@bot_bp.post("/login-linkcode")
@limiter.limit("5 per minute")
def post_login_linkcode():
    """
    Launch regwithlinkcode.py; capture and return the generated link code.

    Request body (JSON): {"phone": "+8613812345678"}
    Response:            {"link_code": "ABCD1234"}
    """
    body = request.get_json(silent=True) or {}
    phone = str(body.get("phone", "")).strip()
    if not phone:
        return {"error": "phone required"}, 400

    script_path = _resolve_script("regwithlinkcode.py")
    if not script_path.exists():
        return {"error": "regwithlinkcode.py not found"}, 404

    try:
        proc = subprocess.Popen(
            [sys.executable, str(script_path), phone],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path.cwd()),
        )
    except OSError as exc:
        logger.error("Failed to start regwithlinkcode.py: %s", exc)
        return {"error": str(exc)}, 500

    # Read stdout until we see an 8-character link code or process exits
    link_code: str | None = None
    deadline = time.time() + _BOT_STARTUP_TIMEOUT
    for line in proc.stdout:  # type: ignore[union-attr]
        if time.time() > deadline:
            break
        line = line.strip()
        logger.debug("linkcode stdout: %s", line)
        # Link codes are typically 8 alphanumeric characters on their own line
        if len(line) == 8 and line.isalnum():
            link_code = line
            break

    if link_code:
        return {"ok": True, "link_code": link_code}
    else:
        proc.terminate()
        return {"error": "Link code not received within timeout"}, 504


# ---------------------------------------------------------------------------
# B.5  POST /api/bot/logout
# ---------------------------------------------------------------------------

@bot_bp.post("/logout")
@limiter.limit("10 per minute")
def post_logout():
    """Send SIGTERM to the running bot process."""
    from app.dashboard.utils.bot_status import clear_status
    status = read_status()
    pid = status.get("pid")
    if not status.get("running") or not pid:
        return {"error": "Bot is not running"}, 409

    try:
        _terminate_pid(pid)
        logger.info("Sent SIGTERM to bot PID=%s", pid)
        clear_status()
        return {"ok": True, "pid": pid}
    except ProcessLookupError:
        # Process already gone — clean up the stale status file
        clear_status()
        logger.info("Bot PID=%s was already gone; status cleared", pid)
        return {"ok": True, "pid": pid, "note": "process was already stopped"}
    except PermissionError:
        return {"error": "Permission denied terminating process"}, 403


# ---------------------------------------------------------------------------
# B.6  POST /api/bot/start
# ---------------------------------------------------------------------------

@bot_bp.post("/start")
@limiter.limit("5 per minute")
def post_bot_start():
    """
    Start the bot for an already-registered phone number.
    Equivalent to running: python script/main.py <phone>

    Request body (JSON): {"phone": "989334018988"}
    Response:            {"ok": true, "pid": 12345}
    """
    global _start_proc

    body = request.get_json(silent=True) or {}
    phone = str(body.get("phone", "")).strip().lstrip("+")
    if not phone:
        return {"error": "phone required"}, 400
    if not phone.isdigit() or not (7 <= len(phone) <= 15):
        return {"error": "invalid phone number — digits only, 7-15 characters"}, 400

    # Refuse to double-start if a process is already alive
    status = read_status()
    if status.get("running") and status.get("pid") and _pid_alive(status["pid"]):
        return {"error": "Bot is already running", "pid": status["pid"]}, 409

    script_path = _resolve_script("main.py")
    if not script_path.exists():
        return {"error": "script/main.py not found"}, 404

    # Kill any previous start proc so its stdout pipe is freed
    if _start_proc is not None and _start_proc.poll() is None:
        try:
            _start_proc.terminate()
        except OSError:
            pass
    _start_proc = None

    try:
        _start_proc = subprocess.Popen(
            [sys.executable, str(script_path), phone],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path.cwd()),
        )
        _write_pid_file(_start_proc.pid)
        logger.info("Bot start subprocess launched, PID=%s, phone=%s", _start_proc.pid, phone)
        return {"ok": True, "pid": _start_proc.pid}
    except OSError as exc:
        logger.error("Failed to start script/main.py: %s", exc)
        return {"error": str(exc)}, 500


# ---------------------------------------------------------------------------
# B.7  GET /api/bot/start-stream
# ---------------------------------------------------------------------------

@bot_bp.get("/start-stream")
def get_start_stream():
    """
    SSE stream that pushes stdout lines from the running bot start subprocess.

    Streams until one of:
      - bot_status.json reports running=True  → event: status {type: "connected"}
      - subprocess exits with non-zero code   → event: status {type: "error"}
      - _BOT_CONNECT_TIMEOUT seconds elapsed  → event: status {type: "timeout"}

    After the stream ends the subprocess keeps running.  A persistent drain
    thread keeps reading (and discarding) its stdout so the OS pipe buffer
    never fills up and blocks the bot process.

    Event types:
      event: log     data: <text line>
      event: status  data: {"type": "connected"|"error"|"timeout", "msg": "..."}
    """
    global _start_proc

    token = request.args.get("token", "")
    from app.dashboard.api.auth import check_bearer
    # Re-use the same Bearer check but for the query-param token passed by SSE clients
    if token:
        import flask
        flask.request.environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def generate():
        proc = _start_proc
        if proc is None:
            yield _sse_event("status", {"type": "error", "msg": "No active start session"})
            return

        deadline = time.time() + _BOT_CONNECT_TIMEOUT
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if time.time() > deadline:
                    yield _sse_event("status", {"type": "timeout",
                                                 "msg": "Bot did not connect within timeout"})
                    _start_drain_thread(proc)
                    return
                line = line.rstrip("\n")
                if line:
                    yield _sse_event("log", line)
                # Check if bot is now connected
                st = read_status()
                if st.get("running") and st.get("pid") == proc.pid:
                    yield _sse_event("status", {
                        "type": "connected",
                        "jid": st.get("jid"),
                        "pid": st.get("pid"),
                    })
                    _start_drain_thread(proc)
                    return
        except Exception as exc:
            logger.warning("start-stream error: %s", exc)
            yield _sse_event("status", {"type": "error", "msg": str(exc)})
            _start_drain_thread(proc)
            return

        # Process exited — report outcome
        rc = proc.poll()
        if rc == 0:
            st = read_status()
            if st.get("running"):
                yield _sse_event("status", {
                    "type": "connected",
                    "jid": st.get("jid"),
                    "pid": st.get("pid"),
                })
            else:
                yield _sse_event("status", {"type": "error",
                                             "msg": f"Process exited (code {rc}) without connecting"})
        else:
            yield _sse_event("status", {"type": "error",
                                         "msg": f"Process exited with code {rc}"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _start_drain_thread(proc: "subprocess.Popen") -> None:
    """Start a daemon thread that drains proc.stdout until the process exits.

    This prevents the OS pipe buffer from filling up (typically 64 KB on
    Windows) which would block any print/logging call inside the bot and
    cause it to hang silently.
    """
    if proc is None or proc.stdout is None:
        return

    def _drain():
        try:
            for _ in proc.stdout:  # read & discard lines until EOF
                pass
        except Exception:
            pass

    t = threading.Thread(target=_drain, daemon=True, name=f"bot-stdout-drain-{proc.pid}")
    t.start()
    logger.debug("Started stdout drain thread for bot PID=%s", proc.pid)


def _resolve_script(name: str) -> Path:
    """Return absolute path to script/<name>."""
    return Path.cwd() / "script" / name


def _write_pid_file(pid: int) -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid))


def _kill_qr_proc() -> None:
    global _qr_proc
    if _qr_proc is not None and _qr_proc.poll() is None:
        try:
            _qr_proc.terminate()
        except OSError:
            pass
        _qr_proc = None


def _terminate_pid(pid: int) -> None:
    """Send SIGTERM on POSIX; use taskkill on Windows."""
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
        )
        if result.returncode != 0:
            # Exit code 128 = process not found; treat as already gone.
            raise ProcessLookupError(f"taskkill failed (code {result.returncode}): PID {pid} not found")
    else:
        os.kill(pid, signal.SIGTERM)


def _sse_event(event: str, data) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
