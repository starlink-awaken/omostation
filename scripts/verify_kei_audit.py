#!/usr/bin/env python3
"""Verification script for KEI Sandbox audit records.

Reads the audit log produced by kei_sandbox.py and summarizes it.
"""

import json
import sys
from pathlib import Path

AUDIT_DEFAULT = Path.home() / "runtime" / "audit" / "kei-audit.jsonl"


def summarize(audit_path: Path) -> int:
    if not audit_path.exists():
        print(f"❌ Audit file not found: {audit_path}")
        return 1

    print(f"📂 Reading audit records from: {audit_path}")
    print(f"   File size: {audit_path.stat().st_size} bytes\n")

    records = []
    errors = 0

    with open(audit_path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Line {lineno}: malformed JSON — {e}")
                errors += 1

    if not records and errors == 0:
        print("ℹ️  Audit file exists but is empty.")
        return 0

    # Count by action
    actions = {}
    statuses = {}
    for r in records:
        act = r.get("action", "?")
        st = r.get("status", "?")
        actions[act] = actions.get(act, 0) + 1
        statuses[st] = statuses.get(st, 0) + 1

    print(f"📊 Summary ({len(records)} total record(s), {errors} parse error(s)):\n")

    print("  By action:")
    for act in sorted(actions):
        print(f"    {act}: {actions[act]}")

    print("  By status:")
    for st in sorted(statuses):
        print(f"    {st}: {statuses[st]}")

    print("\n  Last 5 records:")
    for r in records[-5:]:
        print(
            f"    [{r.get('ts', '?')}] {r.get('action')}/{r.get('status')} "
            f"— {r.get('extension_id')} — {r.get('details', '')[:80]}"
        )

    print(
        f"\n{'✅ All records valid.' if errors == 0 else '⚠️  Some records had parse errors.'}"
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else AUDIT_DEFAULT
    sys.exit(summarize(path))
