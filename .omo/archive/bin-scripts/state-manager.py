#!/usr/bin/env python3
"""StateManager — unified state management for .omo/state/."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE_DIR = REPO / ".omo" / "state"


def validate_state_file(path: Path) -> tuple[bool, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return False, "empty_file"
        data = json.loads(text)
    except Exception as e:
        return False, f"invalid_json: {e}"

    if isinstance(data, list):
        return True, None

    if not isinstance(data, dict):
        return False, "not_a_mapping"

    missing = []
    for key in ("version", "updated_at", "schema_version"):
        if key not in data:
            missing.append(key)

    if missing:
        return False, f"missing_fields: {', '.join(missing)}"

    return True, None


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print("Usage: state-manager.py --validate-all | --count | --list [--warn]")
        return 0

    command = args[0]
    warn_mode = "--warn" in args

    if command == "--validate-all":
        errors = []
        warnings = []
        for path in sorted(STATE_DIR.glob("*.json")):
            ok, err = validate_state_file(path)
            if not ok:
                if warn_mode:
                    warnings.append(f"{path.name}: {err}")
                else:
                    errors.append(f"{path.name}: {err}")
        if errors:
            print(f"FAIL: {len(errors)} state files invalid")
            for e in errors[:20]:
                print(f"  - {e}")
            return 1
        if warnings:
            print(f"WARN: {len(warnings)} state files need migration")
            for w in warnings[:20]:
                print(f"  - {w}")
        print(f"PASS: all state files valid")
        return 0

    if command == "--count":
        count = len(list(STATE_DIR.glob("*.json")))
        print(count)
        return 0

    if command == "--list":
        for path in sorted(STATE_DIR.glob("*.json")):
            ok, err = validate_state_file(path)
            status = "valid" if ok else f"INVALID ({err})"
            print(f"{path.name}: {status}")
        return 0

    print(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
