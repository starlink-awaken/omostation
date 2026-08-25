#!/usr/bin/env python3
"""
subtraction-quota-enforcer.py — Enforce T6-05 subtraction quota.

Usage:
  uv run python3 bin/gac/subtraction-quota-enforcer.py --proposed-new script
  uv run python3 bin/gac/subtraction-quota-enforcer.py --check
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOVERNANCE_CHECKS = REPO_ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def count_scripts() -> int:
    count = 0
    for f in (REPO_ROOT / "bin").rglob("*.py"):
        count += 1
    for f in (REPO_ROOT / "bin").rglob("*.sh"):
        count += 1
    return count


def count_rules() -> int:
    if not GOVERNANCE_CHECKS.exists():
        return 0
    import yaml
    text = GOVERNANCE_CHECKS.read_text()
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict) and "gac" in doc:
            return len(doc["gac"].get("rules", []))
    return 0


def count_adrs() -> int:
    adr_dir = REPO_ROOT / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.exists():
        return 0
    return len(list(adr_dir.glob("*.md")))


def get_baselines() -> dict:
    if not GOVERNANCE_CHECKS.exists():
        return {"rule_baseline": 0, "adr_baseline": 0, "script_baseline": 0}
    import yaml
    text = GOVERNANCE_CHECKS.read_text()
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict) and "gac" in doc:
            sq = doc["gac"].get("subtraction_quota", {})
            return {
                "rule_baseline": sq.get("rule_baseline", 0),
                "adr_baseline": sq.get("adr_baseline", 0),
                "script_baseline": sq.get("script_baseline", 0),
            }
    return {"rule_baseline": 0, "adr_baseline": 0, "script_baseline": 0}


def check(proposed_new: str = None) -> bool:
    baselines = get_baselines()
    current_rules = count_rules()
    current_adrs = count_adrs()
    current_scripts = count_scripts()

    print(f"Subtraction Quota Check")
    print(f"========================")
    print(f"Rules:   {current_rules} / {baselines['rule_baseline']} baseline")
    print(f"ADRs:    {current_adrs} / {baselines['adr_baseline']} baseline")
    print(f"Scripts: {current_scripts} / {baselines['script_baseline']} baseline")

    if proposed_new == "script":
        new_count = current_scripts + 1
        if new_count > baselines["script_baseline"]:
            print(f"\nFAIL: Adding 1 script would exceed baseline ({new_count} > {baselines['script_baseline']})")
            print("You must deprecate 1 existing script first, or bump the baseline.")
            return False

    if proposed_new == "rule":
        new_count = current_rules + 1
        if new_count > baselines["rule_baseline"]:
            print(f"\nFAIL: Adding 1 rule would exceed baseline ({new_count} > {baselines['rule_baseline']})")
            print("You must deprecate 1 existing rule first, or bump the baseline.")
            return False

    print("\nPASS: Within quota")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Subtraction quota enforcer")
    parser.add_argument("--proposed-new", choices=["script", "rule", "adr"], help="Check if adding this type is allowed")
    parser.add_argument("--check", action="store_true", help="Check current state against baselines")
    args = parser.parse_args()

    if args.proposed_new:
        ok = check(args.proposed_new)
        sys.exit(0 if ok else 1)
    elif args.check:
        ok = check()
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
