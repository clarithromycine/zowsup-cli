#!/usr/bin/env python3
"""Evaluate backend security verification cases for agent protocol (v0.7).

No third-party dependency required.

Usage:
    python3 script/evaluate_agent_security_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.agent_security.stores import InMemoryKeyStore, InMemoryNonceStore
from app.dashboard.agent_security_contract import VerifyContext, verify_message_security

CASES_PATH = ROOT / "docs" / "agent-protocol-fixtures" / "security" / "verification_cases.json"


def main() -> int:
    spec = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    window = int(spec["window_seconds"])
    key_store = InMemoryKeyStore.from_plain_dict(spec["keys"])
    nonce_store = InMemoryNonceStore()
    cases = spec["cases"]

    ok_all = True

    for c in cases:
        now_ts = int(c["now"])
        nonce_store.set_now(now_ts)
        result = verify_message_security(
            c["message"],
            VerifyContext(now_ts=now_ts, require_security=True, window_seconds=window),
            key_store,
            nonce_store,
        )
        decision = "ACCEPT" if result.accepted else "REJECT"
        code = result.code

        expected_decision = c["expect"]
        expected_code = c.get("reject_code")

        if decision != expected_decision:
            ok_all = False
            print(f"[FAIL] {c['id']}: decision {decision} != {expected_decision}")
            continue

        if expected_decision == "REJECT" and expected_code != code:
            ok_all = False
            print(f"[FAIL] {c['id']}: reject_code {code} != {expected_code}")
            continue

        print(f"[PASS] {c['id']} -> {decision}{'' if code == 'ok' else ' / ' + code}")

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
