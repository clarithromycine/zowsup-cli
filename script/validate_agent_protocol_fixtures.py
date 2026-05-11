#!/usr/bin/env python3
"""Validate agent protocol fixtures against docs/agent-protocol.schema.json.

Usage:
    python script/validate_agent_protocol_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "agent-protocol.schema.json"
VALID_DIR = ROOT / "docs" / "agent-protocol-fixtures" / "valid"
INVALID_DIR = ROOT / "docs" / "agent-protocol-fixtures" / "invalid"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print("Missing dependency: jsonschema")
        print("Install with: pip install jsonschema")
        return 2

    schema = load_json(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    ok = True

    # valid fixtures must pass
    for p in sorted(VALID_DIR.glob("*.json")):
        data = load_json(p)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            ok = False
            print(f"[FAIL valid] {p.name}")
            for e in errors:
                print(f"  - {e.message}")
        else:
            print(f"[PASS valid] {p.name}")

    # invalid fixtures must fail
    for p in sorted(INVALID_DIR.glob("*.json")):
        data = load_json(p)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            print(f"[PASS invalid] {p.name}")
        else:
            ok = False
            print(f"[FAIL invalid] {p.name} (unexpectedly valid)")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
