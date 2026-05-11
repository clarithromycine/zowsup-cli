from __future__ import annotations

import base64
import json
from typing import Any


def b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def canonicalize_message(message: dict[str, Any]) -> str:
    """Canonicalize envelope JSON for signature verification.

    Rules:
    - Remove security.signature if present.
    - Keep all other fields unchanged.
    - JSON dumps with sort_keys=True, separators=(",", ":"), ensure_ascii=False.
    """
    msg = json.loads(json.dumps(message))
    sec = msg.get("security")
    if isinstance(sec, dict):
        sec.pop("signature", None)
    return json.dumps(msg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
