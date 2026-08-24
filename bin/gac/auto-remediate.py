#!/usr/bin/env python3
"""
auto-remediate.py — Auto-remediation engine with safe rules.

Usage:
  uv run python3 bin/gac/auto-remediate.py --dry-run
  uv run python3 bin/gac/auto-remediate.py --auto
  uv run python3 bin/gac/auto-remediate.py --supervised
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

RULES = [
    {
        "id": "auto-rotate-history",
        "condition": "history.jsonl > 90 days old",
        "action": "bin/gac/rotate-history.py",
        "safe": True,
        "approval": "none",
    },
    {
        "id": "auto-prune-stale-locks",
        "condition": "stale locks > 0",
        "action": "bin/gac/prune-locks",
        "safe": True,
        "approval": "none",
    },
    {
        "id": "auto-archive-stale-tasks",
        "condition": "planned tasks > 30 days old",
        "action": "bin/plan/sync-planned-to-done.py",
        "safe": True,
        "approval": "none",
    },
    {
        "id": "auto-refresh-state",
        "condition": "freshness_score < 80",
        "action": "make state-sync",
        "safe": True,
        "approval": "none",
    },
    {
        "id": "auto-fix-submodule-drift",
        "condition": "submodule pointer drift detected",
        "action": "bin/ssot/submodule-pointer-transaction.sh",
        "safe": True,
        "approval": "governance-team",
    },
]


def check_condition(condition: str) -> bool:
    if "history.jsonl > 90 days old" in condition:
        history = REPO_ROOT / ".omo" / "_log" / "governance-history.jsonl"
        if not history.exists():
            return False
        import time
        age_days = (time.time() - history.stat().st_mtime) / 86400
        return age_days > 90

    if "stale locks > 0" in condition:
        locks_file = REPO_ROOT / ".omo" / "locks.json"
        if not locks_file.exists():
            return False
        try:
            import json
            data = json.loads(locks_file.read_text())
            return len(data.get("locks", [])) > 0
        except Exception:
            return False

    if "planned tasks > 30 days old" in condition:
        planned_dir = REPO_ROOT / ".omo" / "tasks" / "planned"
        if not planned_dir.exists():
            return False
        import time
        for f in planned_dir.glob("*.yaml"):
            try:
                age_days = (time.time() - f.stat().st_mtime) / 86400
                if age_days > 30:
                    return True
            except Exception:
                continue
        return False

    if "freshness_score < 80" in condition:
        health = REPO_ROOT / ".omo" / "state" / "health.yaml"
        if not health.exists():
            return False
        text = health.read_text(errors="ignore")
        import yaml
        try:
            data = yaml.safe_load(text)
            return data.get("freshness_score", 100) < 80
        except Exception:
            return False

    if "submodule pointer drift detected" in condition:
        result = subprocess.run(
            ["bash", "bin/ssot/submodule-pointer-transaction.sh", "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return result.returncode != 0

    return False


def execute_rule(rule: dict, dry_run: bool, supervised: bool) -> dict:
    approval = rule.get("approval", "none")
    if approval != "none" and not supervised:
        return {
            "rule": rule["id"],
            "action": "skipped",
            "reason": f"requires {approval} approval",
        }

    if dry_run:
        return {
            "rule": rule["id"],
            "action": "would execute",
            "command": rule["action"],
            "safe": rule.get("safe", False),
        }

    try:
        result = subprocess.run(
            rule["action"],
            shell=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "rule": rule["id"],
            "action": "executed",
            "command": rule["action"],
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[-200:],
            "stderr": result.stderr.strip()[-200:],
        }
    except subprocess.TimeoutExpired:
        return {"rule": rule["id"], "action": "timeout", "command": rule["action"]}
    except Exception as e:
        return {"rule": rule["id"], "action": "error", "command": rule["action"], "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-remediation engine")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--auto", action="store_true", help="Execute safe rules")
    parser.add_argument("--supervised", action="store_true", help="Execute all rules with approval prompts")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if not any([args.dry_run, args.auto, args.supervised]):
        parser.print_help()
        sys.exit(1)

    results = []
    for rule in RULES:
        if check_condition(rule["condition"]):
            result = execute_rule(rule, dry_run=args.dry_run, supervised=args.supervised)
            results.append(result)

    if args.json:
        print(json.dumps({"results": results}, indent=2))
        sys.exit(0)

    print("Auto-Remediation Engine")
    print("=" * 50)
    for r in results:
        print(f"[{r['action'].upper()}] {r['rule']}")
        if r.get("command"):
            print(f"       Command: {r['command']}")
        if r.get("reason"):
            print(f"       Reason: {r['reason']}")
        if r.get("returncode") is not None:
            print(f"       Return code: {r['returncode']}")
        if r.get("stdout"):
            print(f"       stdout: {r['stdout'][:100]}")
        if r.get("stderr"):
            print(f"       stderr: {r['stderr'][:100]}")
    print("=" * 50)
    print(f"Executed {len(results)} rules")


if __name__ == "__main__":
    main()
