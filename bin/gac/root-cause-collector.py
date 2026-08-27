#!/usr/bin/env python3
"""
root-cause-collector.py — Collect root-cause evidence on failure.

Usage:
  uv run python3 bin/gac/root-cause-collector.py --failure <type>
  uv run python3 bin/gac/root-cause-collector.py --json
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FAILURE_TYPE_TO_RUNBOOK = {
    "freshness_expired": "docs/operations/runbook-state-freshness.md",
    "silent_workflow": "docs/operations/runbook-p74-silent-workflow.md",
    "concurrent_write": "docs/operations/runbook-concurrent-write.md",
    "gate_failure": "docs/operations/runbook-gate-failure.md",
    "submodule_drift": "docs/operations/runbook-submodule-drift.md",
    "health_degraded": "docs/operations/runbook-state-freshness.md",
}


def run(cmd: str, cwd=None) -> tuple[int, str, str]:
    if cwd is None:
        cwd = REPO_ROOT
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def collect_snapshot(failure_type: str) -> dict:
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "failure_type": failure_type,
        "artifacts": {},
    }

    rc, out, err = run("launchctl list | grep -E 'omo|cockpit|aetherforge'")
    snapshot["artifacts"]["launchctl"] = (out or err).strip()[:1000]

    rc, out, err = run("git status --short")
    snapshot["artifacts"]["git_status"] = (out or err).strip()[:1000]

    rc, out, err = run("uv run python3 bin/compass_radar.py --json")
    snapshot["artifacts"]["radar"] = (out or err).strip()[:2000]

    rc, out, err = run("uv run python3 bin/agent-workflow.py compliance --json")
    snapshot["artifacts"]["compliance"] = (out or err).strip()[:2000]

    return snapshot


def suggest_runbook(failure_type: str) -> str:
    return FAILURE_TYPE_TO_RUNBOOK.get(failure_type, "docs/operations/README.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Root-cause collector")
    parser.add_argument("--failure", required=True, help="Failure type")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    snapshot = collect_snapshot(args.failure)
    runbook = suggest_runbook(args.failure)

    if args.json:
        result = {
            "failure_type": args.failure,
            "runbook": runbook,
            "snapshot": snapshot,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(f"Root Cause Collection: {args.failure}")
    print("=" * 50)
    print(f"Runbook: {runbook}")
    print(f"Timestamp: {snapshot['timestamp']}")
    print()
    for key, value in snapshot["artifacts"].items():
        print(f"--- {key} ---")
        print(value[:500])
        print()
    print("=" * 50)
    print("To package as evidence:")
    print(f"  tar czf /tmp/root-cause-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz ...")


if __name__ == "__main__":
    main()
