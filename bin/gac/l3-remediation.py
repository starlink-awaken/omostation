#!/usr/bin/env python3
"""l3-remediation — detect L3 high-risk tasks and emit concrete remediation.

L3 tasks need human approval (`human_approval_required: true`). The system
correctly flags them in radar's anomaly_score, but the operator must
look at each L3 task individually to figure out next steps.

This tool:
  - finds all L3 tasks under .omo/tasks/
  - shows their entry_gate (preconditions), evidence_required, and
    a link to the BET ledger entry
  - emits a remediation plan per task: "unblock X, then run Y"
  - skips `candidate`/`pending`/etc. with explanation
  - exits 1 if any L3 task is ready-to-unblock (owner-actionable)

Usage:
  python3 bin/gac/l3-remediation.py
  python3 bin/gac/l3-remediation.py --json
  python3 bin/gac/l3-remediation.py --task BET-Y3H1-T7-01   # single task
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
TASKS_DIR = WORKSPACE / ".omo" / "tasks"


def _load_task(path: Path) -> dict | None:
    """Load a YAML task file. Returns None on parse error or missing file."""
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, FileNotFoundError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _is_l3(task: dict) -> bool:
    """True if task is L3 (both risk_level and operation level)."""
    risk = str(task.get("risk_level", "")).upper()
    op = str(task.get("allowed_operation_level", "")).upper()
    return risk == "L3" or op == "L3"


def _is_actionable(task: dict) -> tuple[bool, str]:
    """True if task is ready for human/agent action.

    Returns (actionable, reason).
    """
    status = str(task.get("status", "")).lower()
    completed = task.get("completed_at")
    if completed:
        return False, f"completed_at={completed}"
    if status in {"closed", "resolved", "done"}:
        return False, f"status={status}"
    if status == "candidate":
        return True, "status=candidate (not yet picked up)"
    if status == "pending":
        return True, "status=pending (in queue)"
    if status == "blocked":
        return True, "status=blocked (action needed to unblock)"
    if status in {"registered", "open", "scheduled", "in_progress", "mitigated"}:
        return True, f"status={status}"
    return False, f"unknown status: {status!r}"


def _remediation_plan(task: dict) -> list[str]:
    """Generate concrete next-step suggestions for a L3 task."""
    plan: list[str] = []
    plan.append("Pre-flight: read source_ref → docs/plans/3y-bet-ledger.yaml")
    deps = task.get("depends_on") or []
    if deps:
        plan.append(f"Wait for depends_on to be done: {', '.join(str(d) for d in deps)}")
    entry = task.get("entry_gate") or []
    for e in entry:
        plan.append(f"Verify entry gate: {e}")
    evidence = task.get("evidence_required") or []
    for ev in evidence:
        plan.append(f"Collect evidence: {ev}")
    if task.get("human_approval_required"):
        owner = task.get("owner", "human")
        if owner == "human":
            plan.append("HUMAN ACTION: review and approve via cockpit or CLI")
        else:
            plan.append(f"Agent {owner} should request human approval before proceeding")
    workflow = task.get("workflow", "bet-execution")
    plan.append(f"Use workflow: bin/agent-workflow.py start {workflow} --profile <agent>")
    write_surfaces = task.get("write_surfaces") or []
    if write_surfaces:
        plan.append(f"Touch only: {', '.join(write_surfaces)}")
    return plan


def find_l3_tasks() -> list[Path]:
    """Find all task files in .omo/tasks/."""
    if not TASKS_DIR.exists():
        return []
    return sorted(TASKS_DIR.rglob("*.yaml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--task", help="Show only this task id (e.g. BET-Y3H1-T7-01)")
    args = parser.parse_args(argv)

    paths = find_l3_tasks()
    report: list[dict] = []
    actionable_count = 0

    for path in paths:
        # Skip archived/historical paths
        if "/archived/" in str(path) or "/_archive" in str(path):
            continue
        task = _load_task(path)
        if not task:
            continue
        if not _is_l3(task):
            continue
        tid = str(task.get("id", ""))
        if args.task and tid != args.task:
            continue

        actionable, reason = _is_actionable(task)
        if actionable:
            actionable_count += 1
        report.append({
            "id": tid,
            "title": task.get("title", ""),
            "status": task.get("status", ""),
            "owner": task.get("owner", "human"),
            "risk_level": task.get("risk_level", ""),
            "human_approval_required": task.get("human_approval_required", False),
            "depends_on": task.get("depends_on", []),
            "actionable": actionable,
            "reason": reason,
            "remediation": _remediation_plan(task) if actionable else [],
            "file": str(path.relative_to(WORKSPACE)),
        })

    summary = {
        "total_l3": len(report),
        "actionable": actionable_count,
        "tasks": report,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("═══ L3 Remediation Plan ═══")
        print(f"   total L3 tasks:  {len(report)}")
        print(f"   actionable:      {actionable_count}")
        print()
        for t in report:
            icon = "🔴" if t["actionable"] else "⚪"
            print(f"  {icon} {t['id']}: {t['title']}")
            print(f"     status: {t['status']}  owner: {t['owner']}  risk: {t['risk_level']}")
            if t["actionable"]:
                print(f"     reason: {t['reason']}")
                print("     plan:")
                for step in t["remediation"]:
                    print(f"       - {step}")
            else:
                print(f"     skipped: {t['reason']}")
            print()

    return 0 if actionable_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())