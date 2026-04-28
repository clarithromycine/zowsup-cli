"""
app/dashboard/utils/bot_status.py
──────────────────────────────────
Tiny utility for reading/writing data/bot_status.json.

The bot process (script/main.py) calls write_status() on connect/disconnect.
The Flask dashboard reads it via read_status().
No locking needed: file writes are atomic via rename on POSIX; Windows uses
a tmp-file swap.  Reads are tolerant of missing/corrupt files.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

_STATUS_FILE = Path("data") / "bot_status.json"

_EMPTY: dict = {
    "running": False,
    "jid": None,
    "pid": None,
    "started_at": None,
    "updated_at": None,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_status() -> dict:
    """Return current bot status dict; never raises."""
    try:
        with open(_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Stale-PID check: if PID is set but process is gone, mark offline.
        if data.get("running") and data.get("pid"):
            if not _pid_alive(data["pid"]):
                data["running"] = False
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_EMPTY)


def write_status(
    running: bool,
    jid: Optional[str] = None,
    pid: Optional[int] = None,
) -> None:
    """Atomically write bot status to data/bot_status.json."""
    _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "running": running,
        "jid": jid,
        "pid": pid if pid is not None else os.getpid(),
        "started_at": read_status().get("started_at") if running else None,
        "updated_at": time.time(),
    }
    if running and payload["started_at"] is None:
        payload["started_at"] = time.time()

    _atomic_write(_STATUS_FILE, json.dumps(payload, indent=2))


def clear_status() -> None:
    """Mark bot as offline (called on clean shutdown)."""
    write_status(running=False, jid=None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, content: str) -> None:
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".bot_status_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)  # atomic on POSIX; near-atomic on Windows
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _pid_alive(pid: int) -> bool:
    """Return True if a process with *pid* is running (cross-platform safe)."""
    if os.name == "nt":
        # On Windows, os.kill(pid, 0) sends CTRL_C_EVENT — do NOT use it.
        # Instead use the OpenProcess kernel API (no extra dependencies).
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we can't signal it
        except OSError:
            return False
