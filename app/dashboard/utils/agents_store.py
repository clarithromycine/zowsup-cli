"""app/dashboard/utils/agents_store.py
──────────────────────────────────────
Persistent Agent definition store.

An Agent is defined on the server and carries its own HMAC secret.
When the agent process connects to the backend, it authenticates using
that secret.  The backend can then mark it online/offline.

Storage file: data/agents.json
{
  "agents": {
    "<agent_id>": {
      "secret":     "<hex — 32 bytes>",
      "created_at": 1715000000,
      "note":       "optional label"
    }
  }
}

Public API
──────────
list_agents()                    -> list[dict]   (agent_id, created_at, note — no secret)
get_agent_secret(agent_id)       -> bytes | None
add_agent(agent_id, note) -> str (returns the generated hex secret — show once)
delete_agent(agent_id) -> bool
all_secrets() -> dict[str, bytes]
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
import threading
from pathlib import Path
from typing import Optional

_DATA_DIR = Path("data")
_STORE_FILE = _DATA_DIR / "agents.json"
_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read() -> dict:
    try:
        with open(_STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("agents"), dict):
            data["agents"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"agents": {}}


def _write(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=_DATA_DIR, prefix=".agents_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _STORE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Public API ────────────────────────────────────────────────────────────────

def list_agents() -> list[dict]:
    """Return all defined agents without their secrets."""
    with _lock:
        data = _read()
    return [
        {
            "agent_id": agent_id,
            "created_at": rec.get("created_at"),
            "note": rec.get("note", ""),
        }
        for agent_id, rec in data["agents"].items()
    ]


def get_agent_secret(agent_id: str) -> Optional[bytes]:
    """Return secret bytes for agent_id, or None if not defined."""
    with _lock:
        data = _read()
    rec = data["agents"].get(agent_id)
    if not rec:
        return None
    try:
        return bytes.fromhex(rec["secret"])
    except (ValueError, KeyError):
        return None


def all_secrets() -> dict[str, bytes]:
    """Return {agent_id: secret_bytes} for all defined agents."""
    with _lock:
        data = _read()
    result: dict[str, bytes] = {}
    for agent_id, rec in data["agents"].items():
        try:
            result[agent_id] = bytes.fromhex(rec["secret"])
        except (ValueError, KeyError):
            pass
    return result


def add_agent(agent_id: str, note: str = "") -> str:
    """
    Define a new agent with a generated 32-byte secret.
    Returns the hex secret (caller must show it once and discard).
    Raises ValueError if agent_id already exists or is invalid.
    """
    agent_id = agent_id.strip()
    if not agent_id:
        raise ValueError("agent_id must not be empty")
    secret_hex = secrets.token_hex(32)
    with _lock:
        data = _read()
        if agent_id in data["agents"]:
            raise ValueError(f"Agent '{agent_id}' already defined")
        data["agents"][agent_id] = {
            "secret": secret_hex,
            "created_at": int(time.time()),
            "note": note.strip(),
        }
        _write(data)
    return secret_hex


def delete_agent(agent_id: str) -> bool:
    """Delete an agent definition. Returns True if it existed."""
    with _lock:
        data = _read()
        if agent_id not in data["agents"]:
            return False
        del data["agents"][agent_id]
        _write(data)
    return True
