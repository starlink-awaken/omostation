from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .omo_ingress import create_planned_task
from .omo_io import write_text_atomic


def write_planned_self_evolution_tasks(
    workspace_root: Path, tasks: list[dict[str, Any]], generated_at: str
) -> list[Path]:
    out_dir = workspace_root / ".omo" / "tasks" / "planned"
    paths: list[Path] = []
    for task in tasks:
        out = out_dir / f"{task['id']}.yaml"
        if out.exists():
            paths.append(out)
            continue
        task_data = {
            "id": task["id"],
            "title": task["title"],
            "status": "candidate",
            "task_type": "governance",
            "risk_level": "L1",
            "depends_on": [],
            "source_docs": [task["drift_ref"]],
            "deliverables": [task["title"]],
            "imported_via": "opc_p6_self_evolve",
            "context_uri": f"bos://governance/tasks/planned/{task['id']}",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "entry_gate": ["P6 drift review accepted"],
            "evidence_required": ["human approval granted before promotion"],
            "test_plan": [
                "python3 scripts/omo/omo_worker.py task promotion-readiness --omo-dir .omo"
            ],
            "allowed_operation_level": "L1",
            "human_approval_required": bool(
                task.get("human_approval_required", task["approval_required"])
            ),
            "approval_required": bool(task["approval_required"]),
            "approval_state": task.get("approval_state", "awaiting_human"),
            "created_at": generated_at,
            "source": task["source"],
            "drift_ref": task["drift_ref"],
            "loop_history_ref": task.get(
                "loop_history_ref", ".omo/_control/evolution/loop/history.json"
            ),
            "review_lane": "opc-p6-self-evolution-board",
            "prerequisite_for": "OPC-P6",
            "red_lines": [
                "self-evolution task 仅落 planned/, 永不入 active/ 除非 human approval"
            ],
            "next_action": "human reviewer approve in OMO audit queue before promoting to active/",
            "metadata": {
                "created_via": "opc_p6_self_evolve",
                "generated_at": generated_at,
            },
        }
        if task.get("last_run_at"):
            task_data["last_run_at"] = task["last_run_at"]
        if task.get("latest_week"):
            task_data["latest_week"] = task["latest_week"]
        create_planned_task(
            workspace_root / ".omo",
            task_data=task_data,
            ingress_plane="scripts/opc_p6_self_evolve.py",
            source_ref=f"opc-p6-self-evolve:{task['id']}",
            now=generated_at,
        )
        paths.append(out)
    return paths


def write_self_evolve_summary(
    workspace_root: Path, summary: dict[str, Any], generated_at: str
) -> Path:
    out_dir = workspace_root / ".omo" / "_control" / "evolution" / "self-evolve"
    out_path = out_dir / f"{generated_at[:10]}.json"
    write_text_atomic(
        out_path,
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    )
    return out_path
