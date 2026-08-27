#!/usr/bin/env python3
"""
session-recovery.py — Show what changed since last session.

Usage:
  uv run python3 bin/gac/session-recovery.py --since "2 days ago"
  uv run python3 bin/gac/session-recovery.py --json
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


def get_code_changes(since: str) -> dict:
    rc, out, err = run(f"git log --since=\"{since}\" --oneline --no-merges")
    commits = [line.strip() for line in (out or "").splitlines() if line.strip()]
    return {
        "commits": commits[:20],
        "count": len(commits),
    }


def get_state_changes() -> dict:
    changes = []
    for f in [".omo/state/health.yaml", ".omo/state/system.yaml"]:
        p = REPO_ROOT / f
        if p.exists():
            import time
            age_hours = (time.time() - p.stat().st_mtime) / 3600
            changes.append({
                "file": f,
                "age_hours": round(age_hours, 1),
            })
    return {"files": changes}


def get_anomalies() -> dict:
    rc, out, err = run("uv run python3 bin/gac/check-silent-workflows.py --list-silent 2>&1")
    silent = (out or err).strip()[:500]
    rc2, out2, err2 = run("uv run python3 bin/gac/prune-locks --list-stale 2>&1")
    stale_locks = (out2 or err2).strip()[:500]
    return {
        "silent_workflows": silent,
        "stale_locks": stale_locks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Session recovery")
    parser.add_argument("--since", default="2 days ago", help="Time window")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    code = get_code_changes(args.since)
    state = get_state_changes()
    anomalies = get_anomalies()

    if args.json:
        result = {
            "since": args.since,
            "code_changes": code,
            "state_changes": state,
            "anomalies": anomalies,
            "action_items": [
                "Review silent workflows: bin/gac/check-silent-workflows.py --list-silent",
                "Check PR status on GitHub",
            ],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(f"Session Recovery (since: {args.since})")
    print("=" * 50)
    print("=== Code Changes ===")
    if code["commits"]:
        for c in code["commits"][:10]:
            print(f"  {c}")
    else:
        print("  No commits in this window")
    print(f"  Total: {code['count']} commits")
    print()
    print("=== State Changes ===")
    for s in state["files"]:
        print(f"  {s['file']}: {s['age_hours']}h old")
    print()
    print("=== Anomalies ===")
    if anomalies["silent_workflows"]:
        print("  Silent workflows detected:")
        for line in anomalies["silent_workflows"].splitlines()[:5]:
            print(f"    {line}")
    if anomalies["stale_locks"]:
        print("  Stale locks:")
        for line in anomalies["stale_locks"].splitlines()[:5]:
            print(f"    {line}")
    print("=" * 50)


if __name__ == "__main__":
    main()
