#!/usr/bin/env python3
"""check-silent-loss: detect silently lost tasks across the system.

Scans multiple data sources for signs of tasks that were dispatched
but never completed or explicitly failed:

  1. `.omo/state/collab-dualtrack.yaml` — throughput_track.silent_loss
     must be 0 (hard red line, P84 §0).
  2. `.omo/_delivery/agent-workflow/runs/*.yaml` — for each run with
     status 'closed', verify dispatch count matches completed+failed.
     Any gap > 0 = silently lost task.

Output:
  - exit 0 = no silent losses
  - exit 1 = silent loss detected (blocking)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DUALTRACK_YAML = WORKSPACE / ".omo" / "state" / "collab-dualtrack.yaml"
RUNS_DIR = WORKSPACE / ".omo" / "_delivery" / "agent-workflow" / "runs"


def _check_dualtrack() -> list[dict]:
    findings: list[dict] = []
    if not DUALTRACK_YAML.is_file():
        return findings

    data = yaml.safe_load(DUALTRACK_YAML.read_text(encoding="utf-8")) or {}
    throughput = data.get("throughput_track") or {}
    sl = throughput.get("silent_loss")

    if sl is None:
        findings.append({
            "kind": "missing_field",
            "source": "collab-dualtrack.yaml",
            "message": "throughput_track.silent_loss field missing",
        })
    elif sl != 0:
        findings.append({
            "kind": "silent_loss_detected",
            "source": "collab-dualtrack.yaml",
            "value": sl,
            "message": f"throughput_track.silent_loss = {sl} (expected 0, hard red line P84 §0)",
        })

    return findings


def _check_workflow_runs() -> list[dict]:
    """Check agent workflow runs for dispatch/completion gaps."""
    findings: list[dict] = []
    if not RUNS_DIR.is_dir():
        return findings

    for run_file in sorted(RUNS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue

        status = data.get("status", "")
        if status not in ("closed", "completed", "ok"):
            continue

        # Look for dispatch/completion tracking fields
        dispatched = data.get("dispatched_count") or data.get("tasks_dispatched")
        completed = data.get("completed_count") or data.get("tasks_completed")
        failed = data.get("failed_count") or data.get("tasks_failed")

        if dispatched is None or completed is None:
            # Run doesn't track dispatch metrics — skip silently
            continue

        completed = completed or 0
        failed = failed or 0
        accounted = completed + failed
        gap = dispatched - accounted

        if gap > 0:
            findings.append({
                "kind": "run_silent_loss",
                "source": run_file.name,
                "dispatched": dispatched,
                "completed": completed,
                "failed": failed,
                "gap": gap,
                "message": f"Run {run_file.stem}: {gap} task(s) dispatched but not completed/failed",
            })

    return findings


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings: list[dict] = []
    findings.extend(_check_dualtrack())
    findings.extend(_check_workflow_runs())

    if args.json:
        print(json.dumps({"ok": len(findings) == 0, "findings": findings}))
    else:
        if findings:
            for f in findings:
                print(f"  FAIL: [{f['kind']}] {f['message']}")
            print(f"check-silent-loss: FAIL ({len(findings)} finding(s))")
        else:
            print("check-silent-loss: PASS")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
