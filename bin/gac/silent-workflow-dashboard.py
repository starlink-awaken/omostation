#!/usr/bin/env python3
"""
silent-workflow-dashboard.py — Dedicated silent workflow dashboard.

Usage:
  uv run python3 bin/gac/silent-workflow-dashboard.py
  uv run python3 bin/gac/silent-workflow-dashboard.py --json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd=None) -> tuple[int, str, str]:
    if cwd is None:
        cwd = REPO_ROOT
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def get_silent_workflows() -> list:
    rc, out, err = run("uv run python3 bin/gac/check-silent-workflows.py --list-silent 2>&1")
    output = (out or err).strip()
    workflows = []
    for line in output.splitlines():
        line = line.strip()
        if line and not line.startswith("[") and not line.startswith("="):
            parts = line.split()
            if len(parts) >= 3:
                workflows.append({
                    "name": parts[0],
                    "last_run": parts[1] if len(parts) > 1 else "unknown",
                    "status": parts[2] if len(parts) > 2 else "unknown",
                })
    return workflows


def get_recommendations(workflows: list) -> list:
    recommendations = []
    for w in workflows:
        if w["status"] == "dead":
            recommendations.append({
                "workflow": w["name"],
                "action": "archive",
                "reason": "replaced by newer implementation",
            })
        elif w["status"] == "silent":
            recommendations.append({
                "workflow": w["name"],
                "action": "add_coverage",
                "reason": "no recent runs, add diff_check or cron schedule",
            })
    return recommendations


def main() -> None:
    parser = argparse.ArgumentParser(description="Silent workflow dashboard")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    workflows = get_silent_workflows()
    recommendations = get_recommendations(workflows)

    if args.json:
        result = {
            "silent_workflows": workflows,
            "recommendations": recommendations,
            "total": len(workflows),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("Silent Workflow Dashboard")
    print("=" * 70)
    print(f"{'Workflow':<30} {'Last Run':<20} {'Status':<10}")
    print("-" * 70)
    for w in workflows:
        print(f"{w['name']:<30} {w['last_run']:<20} {w['status']:<10}")
    print("=" * 70)
    print("Recommendations:")
    for r in recommendations:
        print(f"  - {r['workflow']}: {r['action']} ({r['reason']})")
    print("=" * 70)
    if not workflows:
        print("No silent workflows detected. System is healthy.")


if __name__ == "__main__":
    main()
