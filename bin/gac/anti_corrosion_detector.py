#!/usr/bin/env python3
"""Detect governance rule staleness and suggest fixes."""

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
GOV_CHECKS = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"
CONVERGENCE_LINT = WORKSPACE / "bin/gac/governance-convergence-lint.py"
ADR_DIR = WORKSPACE / ".omo/_knowledge/decisions"


def detect_stale_rules() -> list[dict]:
    stale: list[dict] = []

    if GOV_CHECKS.exists():
        content = GOV_CHECKS.read_text()
        for match in re.finditer(r"- id: (CR-[^\n]+)\n.*?lifecycle: (\w+)", content, re.DOTALL):
            rule_id, lifecycle = match.groups()
            if lifecycle in ("deprecated", "superseded", "removed"):
                stale.append({"id": rule_id.strip(), "reason": f"lifecycle={lifecycle}", "fix": "Review and update lifecycle or remove"})

    if CONVERGENCE_LINT.exists():
        text = CONVERGENCE_LINT.read_text()
        match = re.search(r"LEGACY_CR_IDS\s*=\s*\{([^}]+)\}", text, re.DOTALL)
        if match:
            ids = [m.strip('"').rstrip(",").strip('"') for m in match.group(1).strip().split("\n") if m.strip()]
            if len(ids) > 80:
                stale.append({"id": "LEGACY_CR_IDS", "reason": f"{len(ids)} entries (>80 threshold)", "fix": "Audit and remove unreferenced entries"})

    if ADR_DIR.exists():
        cutoff = datetime.now(UTC) - timedelta(days=90)
        for adr_file in ADR_DIR.glob("*.md"):
            content = adr_file.read_text()
            for status in ("Status: PROPOSED", "Status: DRAFT"):
                if status in content:
                    stale.append({"id": adr_file.name, "reason": f"{status.split(': ')[1]} for >90 days", "fix": "Review and update status"})

    return stale


def suggest_fixes() -> list[dict]:
    fixes: list[dict] = []
    stale = detect_stale_rules()
    by_area: dict[str, list[dict]] = {}
    for item in stale:
        area = "governance-checks.yaml" if item["id"].startswith("CR-") or item["id"] == "LEGACY_CR_IDS" else "ADR directory"
        by_area.setdefault(area, []).append(item)
    for area, items in by_area.items():
        fixes.append({"area": area, "count": len(items), "items": items})
    return fixes


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Anti-corrosion detector")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    stale = detect_stale_rules()
    fixes = suggest_fixes()

    if args.json:
        print(json.dumps({"stale": stale, "fixes": fixes}, indent=2))
    else:
        print("=== Stale Rules ===")
        for rule in stale:
            print(f"  {rule['id']}: {rule['reason']}")
        print(f"\nTotal: {len(stale)} stale items")
        if stale:
            print("\n=== Suggested Fixes ===")
            for fix in fixes:
                print(f"  {fix['area']}: {fix['count']} items")

    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
