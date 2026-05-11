"""app/dashboard/utils/agent_keys.py
─────────────────────────────────────
Persistent agent key store.

Keys are stored in data/agent_keys.json as:
{
  "keys": {
    "<kid>": {
      "secret": "<hex string>",
      "created_at": 1715000000,
      "note": "optional label"
    }
  }
}

Secrets are stored as hex so they are printable and diff-friendly.
They are returned as bytes to the caller.

Public API
──────────
list_keys()                      -> list[dict]   (kid, created_at, note — no secret)
get_key_secret(kid) -> bytes | None
add_key(kid, note) -> str        (returns the generated hex secret)
delete_key(kid) -> bool
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
_KEY_FILE = _DATA_DIR / "agent_keys.json"
_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read() -> dict:
    try:
        with open(_KEY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("keys"), dict):
            data["keys"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"keys": {}}


def _write(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=_DATA_DIR, prefix=".agent_keys_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _KEY_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Public API ────────────────────────────────────────────────────────────────

def list_keys() -> list[dict]:
    """Return all keys without the secret."""
    with _lock:
        data = _read()
    return [
        {
            "kid": kid,
            "created_at": rec.get("created_at"),
            "note": rec.get("note", ""),
        }
        for kid, rec in data["keys"].items()
    ]


def get_key_secret(kid: str) -> Optional[bytes]:
    """Return secret bytes for kid, or None if not found."""
    with _lock:
        data = _read()
    rec = data["keys"].get(kid)
    if not rec:
        return None
    try:
        return bytes.fromhex(rec["secret"])
    except (ValueError, KeyError):
        return None


def all_secrets() -> dict[str, bytes]:
    """Return {kid: secret_bytes} for all keys — used by gateway at startup."""
    with _lock:
        data = _read()
    result: dict[str, bytes] = {}
    for kid, rec in data["keys"].items():
        try:
            result[kid] = bytes.fromhex(rec["secret"])
        except (ValueError, KeyError):
            pass
    return result


def add_key(kid: str, note: str = "") -> str:
    """
    Generate a new 32-byte random secret for *kid* and persist it.
    Returns the secret as a hex string (show once to the user).
    Raises ValueError if kid already exists.
    """
    kid = kid.strip()
    if not kid:
        raise ValueError("kid must not be empty")
    secret_hex = secrets.token_hex(32)
    with _lock:
        data = _read()
        if kid in data["keys"]:
            raise ValueError(f"Key '{kid}' already exists")
        data["keys"][kid] = {
            "secret": secret_hex,
            "created_at": int(time.time()),
            "note": note.strip(),
        }
        _write(data)
    return secret_hex


def delete_key(kid: str) -> bool:
    """Delete key. Returns True if it existed."""
    with _lock:
        data = _read()
        if kid not in data["keys"]:
            return False
        del data["keys"][kid]
        _write(data)
    return True
