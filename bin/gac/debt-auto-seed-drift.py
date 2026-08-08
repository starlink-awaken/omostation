#!/usr/bin/env python3
"""Auto-seed submodule pointer drift issues into .omo/debt/items/SUBMODULE_DRIFT.yaml.

Runs check-submodule-pointer-drift.py --json, parses results, and updates
the SUBMODULE_DRIFT debt item with current drift details.

Usage:
    python3 bin/gac/debt-auto-seed-drift.py [--apply]

    --apply: write changes to disk (default: dry-run)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DEBT_ITEM = WORKSPACE / ".omo" / "debt" / "items" / "SUBMODULE_DRIFT.yaml"
DRIFT_SCRIPT = WORKSPACE / "bin" / "gac" / "check-submodule-pointer-drift.py"


def run_drift_check() -> dict:
    """Run check-submodule-pointer-drift.py --json and parse output."""
    result = subprocess.run(
        [sys.executable, str(DRIFT_SCRIPT), "--json"],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    lines = result.stdout.splitlines()
    json_text = ""
    for line in lines:
        json_text += line + "\n"
        try:
            json.loads(json_text)
            break
        except Exception:
            continue
    return json.loads(json_text)


def update_debt_item(drift_data: dict, apply: bool = False) -> str:
    """Update SUBMODULE_DRIFT.yaml with current drift details.

    Returns a summary of changes.
    """
    if not DEBT_ITEM.exists():
        return f"❌ Debt item not found: {DEBT_ITEM}"

    debt = yaml.safe_load(DEBT_ITEM.read_text())
    results = drift_data.get("results", [])
    issues = [r for r in results if r.get("status") not in ("skip", "aligned")]

    if not issues:
        # No drift — mark resolved if not already
        if debt.get("lifecycle_state") != "resolved":
            debt["lifecycle_state"] = "resolved"
            debt["last_reviewed_at"] = str(date.today())
            if apply:
                DEBT_ITEM.write_text(yaml.dump(debt, allow_unicode=True, sort_keys=False))
            return "✅ No drift detected. Debt item marked resolved."
        return "✅ No drift detected. Debt item already resolved."

    # Drift found — reopen debt item
    drift_details = []
    for item in issues:
        submodule = item.get("submodule", "?")
        status = item.get("status", "unknown")
        gitlink = item.get("gitlink", "?")[:12]
        origin = item.get("origin_main", "?")[:12] if item.get("origin_main") else "?"
        fix_cmd = f"cd {submodule} && git checkout main && git pull && cd ../.. && git add {submodule}"
        drift_details.append(
            f"- {submodule}: {status} (gitlink={gitlink}, origin={origin})\n  Fix: {fix_cmd}"
        )

    debt["lifecycle_state"] = "open"
    debt["last_reviewed_at"] = str(date.today())
    debt["description"] = (
        f"Submodule gitlink drift detected: {len(issues)} issue(s).\n\n"
        + "\n".join(drift_details)
    )
    debt.setdefault("affected_roots", [])
    debt["affected_roots"] = [
        r for r in debt["affected_roots"]
        if r != ".omo/state/health.yaml"
    ] + [f"{item.get('submodule')}" for item in issues]
    debt.setdefault("evidence_refs", [])
    debt["evidence_refs"].append(f"check-submodule-pointer-drift.py --json ({date.today()})")
    debt.setdefault("mitigation_refs", [])
    for item in issues:
        fix_cmd = f"cd {item.get('submodule')} && git checkout main && git pull && cd ../.. && git add {item.get('submodule')}"
        if fix_cmd not in debt["mitigation_refs"]:
            debt["mitigation_refs"].append(fix_cmd)

    if apply:
        DEBT_ITEM.write_text(yaml.dump(debt, allow_unicode=True, sort_keys=False))

    return (
        f"⚠️  Drift detected in {len(issues)} submodule(s):\n"
        + "\n".join(drift_details)
        + f"\nDebt item {'updated' if apply else 'would be updated'}: {DEBT_ITEM}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-seed submodule drift into debt items")
    parser.add_argument("--apply", action="store_true", help="Write changes to disk (default: dry-run)")
    args = parser.parse_args()

    try:
        drift_data = run_drift_check()
    except Exception as e:
        print(f"❌ Failed to run drift check: {e}")
        return 1

    summary = update_debt_item(drift_data, apply=args.apply)
    print(summary)

    # Exit 1 if drift found (for CI integration)
    issues = [r for r in drift_data.get("results", []) if r.get("status") not in ("skip", "aligned")]
    if issues:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
