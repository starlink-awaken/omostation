#!/usr/bin/env python3
"""Close orphaned Workflow Mesh runs that have WorkflowRequested but no WorkflowClosed.

Usage:
    python3 bin/mesh/mesh-orphan-cleanup.py            # dry-run, list orphans
    python3 bin/mesh/mesh-orphan-cleanup.py --apply     # close all orphans
    python3 bin/mesh/mesh-orphan-cleanup.py --json      # JSON output
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TIMEOUT = 30  # seconds per subprocess call
RETRY = 3    # max retries on transient failure

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "projects" / "omo" / "src"))

from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
from omo.workflow_mesh import WorkflowMeshStore, project_workflow_run


def find_orphans(store):
    events = store.events()
    run_ids = {e["workflow_run_id"] for e in events}
    orphans = []
    for rid in sorted(run_ids):
        try:
            snapshot = project_workflow_run(events, rid)
            if snapshot["state"] not in ("closed",) and snapshot["event_count"] > 0:
                orphans.append(
                    {
                        "run_id": rid,
                        "state": snapshot["state"],
                        "event_count": snapshot["event_count"],
                        "last_event_type": snapshot.get("last_event_type"),
                    }
                )
        except Exception:
            orphans.append(
                {
                    "run_id": rid,
                    "state": "error",
                    "event_count": 0,
                    "last_event_type": None,
                }
            )
    return orphans


def close_orphan(run_id, workspace):
    return emit_workflow_mesh_event(
        "AgentWorkflowClosed",
        run_id,
        {"status": "cancelled", "ok": False, "reason": "orphan cleanup"},
        workspace=workspace,
    )


def main():
    parser = argparse.ArgumentParser(description="Close orphaned Workflow Mesh runs")
    parser.add_argument("--apply", action="store_true", help="Close orphans (default: dry-run)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    store = WorkflowMeshStore(WORKSPACE / ".omo")
    orphans = find_orphans(store)

    if not orphans:
        if args.json:
            print(json.dumps({"orphans": [], "closed": 0}))
        else:
            print("No orphaned runs found.")
        return 0

    if not args.apply:
        if args.json:
            print(json.dumps({"orphans": orphans, "closed": 0}))
        else:
            print(f"Found {len(orphans)} orphaned run(s) (dry-run, use --apply to close):")
            for o in orphans:
                print(f"  {o['run_id']} state={o['state']} events={o['event_count']}")
        return 0

    closed = 0
    for o in orphans:
        if close_orphan(o["run_id"], WORKSPACE):
            closed += 1

    if args.json:
        print(json.dumps({"orphans": orphans, "closed": closed}))
    else:
        print(f"Closed {closed}/{len(orphans)} orphaned run(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
