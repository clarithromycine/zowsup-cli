#!/usr/bin/env python3
"""Verify agent signing vectors without third-party dependencies.

Usage:
    python3 script/verify_agent_signing_vectors.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = ROOT / "docs" / "agent-protocol-fixtures" / "signing"


def b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def canonicalize(message: dict) -> str:
    msg = json.loads(json.dumps(message))
    sec = msg.get("security")
    if isinstance(sec, dict) and "signature" in sec:
        sec.pop("signature", None)
    return json.dumps(msg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_vector(path: Path) -> tuple[bool, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    key = data["key"].encode("utf-8")
    canonical = canonicalize(data["message"])
    expected_canonical = data["canonical_json"]
    if canonical != expected_canonical:
        return False, f"canonical mismatch\nexpected: {expected_canonical}\nactual:   {canonical}"

    sig = b64url_no_pad(hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).digest())
    if sig != data["expected_signature"]:
        return False, f"signature mismatch expected={data['expected_signature']} actual={sig}"
    return True, "ok"


def main() -> int:
    files = sorted(VECTORS_DIR.glob("*.json"))
    if not files:
        print("No vectors found")
        return 1

    ok_all = True
    for p in files:
        ok, msg = verify_vector(p)
        if ok:
            print(f"[PASS] {p.name}")
        else:
            ok_all = False
            print(f"[FAIL] {p.name}: {msg}")

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
