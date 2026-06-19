#!/usr/bin/env python3
"""OMO task CLI — list and create governed tasks via OMO ingress."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .omo_ingress import create_planned_task
from .omo_paths import find_omo_dir


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _governance_refs() -> list[str]:
    return [
        ".omo/standards/omo-governance-surfaces.md",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ".omo/_truth/x1-governance-policies.yaml",
        ".omo/_truth/x2-freshness-rules.yaml",
        ".omo/_truth/x3-value-stack.yaml",
        ".omo/_truth/x4-consistency-rules.yaml",
    ]


def _find_omo_dir() -> Path:
    return find_omo_dir()


def cmd_task_list(omo_dir: Path, status: str | None) -> int:
    """List tasks filtered by status directory."""
    if status:
        dirs = [omo_dir / "tasks" / status]
    else:
        dirs = [omo_dir / "tasks" / s for s in ("active", "planned", "done")]
    total = 0
    for d in dirs:
        if not d.exists():
            continue
        files = sorted(d.glob("*.yaml"))
        if not files:
            continue
        label = d.relative_to(omo_dir / "tasks")
        print(f"=== {label} ({len(files)} tasks) ===")
        for f in files[:20]:
            data = f.read_text().split("\n")[:3]
            tid = ""
            for line in data:
                if line.startswith("id:") or line.startswith("title:"):
                    tid += line.strip() + " "
            print(f"  {f.stem}: {tid[:60]}")
        if len(files) > 20:
            print(f"  ... and {len(files)-20} more")
        total += len(files)
    print(f"\nTotal: {total} tasks")
    return 0


def cmd_task_create(
    omo_dir: Path,
    *,
    title: str,
    desc: str,
    priority: str,
    source_docs: list[str],
    test_plan: list[str],
    deliverables: list[str] | None = None,
    evidence_required: list[str] | None = None,
    task_type: str = "feature",
    risk_level: str = "L0",
    allowed_operation_level: str = "L0",
    context_uri: str | None = None,
    source_ref: str = "",
) -> int:
    task_id = f"TASK-{uuid4().hex[:8].upper()}"
    task_data = {
        "id": task_id,
        "title": title,
        "description": desc,
        "status": "candidate",
        "task_type": task_type,
        "risk_level": risk_level,
        "depends_on": [],
        "source_docs": source_docs,
        "deliverables": deliverables or [f"{priority} 任务交付物"],
        "imported_via": "omo_task_cli",
        "context_uri": context_uri or f"bos://governance/tasks/planned/{task_id}",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": _governance_refs(),
        "entry_gate": [],
        "evidence_required": evidence_required or [],
        "test_plan": test_plan,
        "allowed_operation_level": allowed_operation_level,
        "human_approval_required": False,
        "metadata": {
            "priority": priority,
            "created_via": "omo task create",
            "governance_stack": "state_plane.kernel_plane.ingress_plane",
            "ingress_plane": "projects/omo",
            "created_at": _utc_now(),
        },
    }
    created = create_planned_task(
        omo_dir,
        task_data=task_data,
        ingress_plane="projects/omo",
        source_ref=source_ref or f"omo:task:create:{task_id}",
    )
    print(f"Created governed task: {omo_dir / 'tasks' / 'planned' / f'{task_id}.yaml'}")
    print(f"Ingress artifact: {omo_dir / '_delivery' / 'ingress' / 'tasks' / f'{task_id}.yaml'}")
    print(f"Task ID: {created['id']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo task", description="OMO task browser")
    sub = parser.add_subparsers(dest="command")
    
    tl = sub.add_parser("list", help="List tasks")
    tl.add_argument("--status", "-s", choices=["active", "planned", "done"], help="Filter by status")
    
    tc = sub.add_parser("create", help="Create a new task")
    tc.add_argument("--title", required=True, help="Task title")
    tc.add_argument("--desc", default="", help="Task description")
    tc.add_argument("--priority", default="P2", help="Task priority (P0, P1, P2)")
    tc.add_argument("--source-doc", dest="source_docs", action="append", required=True, help="Source document ref; repeatable")
    tc.add_argument("--test-plan", dest="test_plan", action="append", required=True, help="Verification command or test plan; repeatable")
    tc.add_argument("--deliverable", dest="deliverables", action="append", help="Expected deliverable; repeatable")
    tc.add_argument("--evidence-required", dest="evidence_required", action="append", help="Evidence requirement; repeatable")
    tc.add_argument("--task-type", default="feature", help="Task type")
    tc.add_argument("--risk-level", default="L0", choices=["L0", "L1", "L2", "L3"], help="Risk level")
    tc.add_argument(
        "--allowed-operation-level",
        default="L0",
        choices=["L0", "L1", "L2", "L3"],
        help="Highest allowed operation level",
    )
    tc.add_argument("--context-uri", help="Optional BOS context URI")
    tc.add_argument("--source-ref", default="", help="Stable source ref for ingress registry")
    
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    
    if args.command == "list":
        return cmd_task_list(omo_dir, args.status)
    elif args.command == "create":
        return cmd_task_create(
            omo_dir,
            title=args.title,
            desc=args.desc,
            priority=args.priority,
            source_docs=args.source_docs,
            test_plan=args.test_plan,
            deliverables=args.deliverables,
            evidence_required=args.evidence_required,
            task_type=args.task_type,
            risk_level=args.risk_level,
            allowed_operation_level=args.allowed_operation_level,
            context_uri=args.context_uri,
            source_ref=args.source_ref,
        )
        
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
