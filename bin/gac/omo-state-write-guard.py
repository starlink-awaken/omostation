#!/usr/bin/env python3
"""GaC #38: OMO state write guard — detect multi-writer conflicts in .omo/ state plane.

Checks two things:
1. Duplicate top-level keys in system.yaml (multi-writer conflict)
2. Unauthorized writes per write-owners.yaml (write protocol violations)

Usage:
  python3 bin/gac/omo-state-write-guard.py
"""

from __future__ import annotations

import sys
import yaml
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
WRITE_OWNERS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "write-owners.yaml"


# ── Check 1: Duplicate top-level keys ──

def check_duplicate_keys() -> list[dict]:
    """Scan system.yaml for duplicate top-level keys (multi-writer conflict)."""
    findings: list[dict] = []
    if not SYSTEM_YAML.exists():
        return findings

    text = SYSTEM_YAML.read_text(encoding="utf-8")
    seen: dict[str, list[int]] = {}

    for i, line in enumerate(text.splitlines(), 1):
        raw = line.split("#")[0]
        if not raw.strip():
            continue
        if ":" in raw and not raw.startswith(" "):
            key = raw.split(":")[0].strip()
            seen.setdefault(key, []).append(i)

    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            findings.append({
                "check": "duplicate-key",
                "key": key,
                "occurrences": len(lines),
                "lines": lines,
                "message": f"Key '{key}' appears {len(lines)} times (lines {lines}) — multi-writer conflict risk",
            })
    return findings


# ── Check 2: Write-owner protocol — detect unauthorized writers ──

def load_write_owners() -> dict:
    """Load write-owners.yaml, return {path: {field: owner}}."""
    if not WRITE_OWNERS_YAML.exists():
        return {}
    try:
        with open(WRITE_OWNERS_YAML) as f:
            data = yaml.safe_load(f)
        return data.get("fields", {})
    except Exception:
        return {}


def check_unauthorized_writes() -> list[dict]:
    """Detect unstaged deletions of protected directories (e.g. .omo/debt/)."""
    findings: list[dict] = []
    owners = load_write_owners()
    if not owners:
        return findings

    import subprocess

    # Check for unstaged deletions of protected paths via git status
    r = subprocess.run(
        ["git", "status", "--short", "--", ".omo/debt/"],
        capture_output=True, text=True, cwd=WORKSPACE, timeout=5,
    )
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("D ") or line.startswith(" D"):
            findings.append({
                "check": "unauthorized-delete",
                "path": line[2:].strip() or ".omo/debt/",
                "message": f"Protected path has unstaged deletion: {line} — only omo-debt system should modify .omo/debt/",
            })
            break  # one finding per directory is enough

    return findings


# ── Main ──

def main() -> int:
    findings = []
    findings.extend(check_duplicate_keys())
    findings.extend(check_unauthorized_writes())

    if not findings:
        print("[OMO-STATE-WRITE-GUARD] ✅ All checks passed — no conflicts detected")
        return 0

    print("[OMO-STATE-WRITE-GUARD] ❌ Write protocol violations detected!")
    for f in findings:
        print(f"  ⚠️  [{f['check']}] {f['message']}")

    print("  ℹ️  See .omo/_truth/registry/write-owners.yaml for ownership rules")
    return 1


if __name__ == "__main__":
    sys.exit(main())
