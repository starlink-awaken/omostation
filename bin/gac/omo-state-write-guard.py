#!/usr/bin/env python3
"""GaC #38: OMO state write guard — detect multi-writer conflicts in system.yaml.

system.yaml has 3 write sources (cron scan, c2g sync, agent patch) that can
overwrite each other's fields. This check flags duplicate top-level keys
that indicate conflicting writes.

Nested keys (e.g. inside runtime_health_summary: or debt_weight_items:) are
NOT flagged — they belong to their respective sub-documents.

Usage:
  python3 bin/gac/omo-state-write-guard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"


def check_duplicate_keys() -> list[dict]:
    """Scan system.yaml for duplicate top-level keys (multi-writer conflict).

    Only keys at indent=0 are checked. Nested keys inside dict/list values
    are ignored because they naturally repeat (e.g. desc/weight in debt_items).
    """
    findings: list[dict] = []
    if not SYSTEM_YAML.exists():
        return findings

    text = SYSTEM_YAML.read_text(encoding="utf-8")
    seen: dict[str, list[int]] = {}

    for i, line in enumerate(text.splitlines(), 1):
        raw = line.split("#")[0]  # strip inline comments but preserve leading spaces
        if not raw.strip():
            continue
        # Only match top-level keys: no leading spaces before key name
        if ":" in raw and not raw.startswith(" "):
            key = raw.split(":")[0].strip()
            seen.setdefault(key, []).append(i)

    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            findings.append({
                "key": key,
                "occurrences": len(lines),
                "lines": lines,
                "message": f"Key '{key}' appears {len(lines)} times (lines {lines}) — multi-writer conflict risk",
            })

    return findings


def main() -> int:
    findings = check_duplicate_keys()

    if not findings:
        print("[OMO-STATE-WRITE-GUARD] ✅ No duplicate keys in system.yaml")
        return 0

    print("[OMO-STATE-WRITE-GUARD] ❌ Duplicate keys detected — multi-writer conflict!")
    for f in findings:
        print(f"  ⚠️  {f['message']}")
    print("  ℹ️  system.yaml has multiple writers (cron scan / c2g sync / agent patch).")
    print("  ℹ️  Each key should appear exactly once. Merge or remove duplicates.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
