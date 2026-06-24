#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from .omo_ingress import create_blocked_task, create_skill_manifest
from .omo_shared import load_yaml


def register_skill_manifest(root: Path, manifest: dict) -> dict:
    create_skill_manifest(
        root / ".omo",
        manifest=manifest,
        actor="omo_skill.register_skill_manifest",
        source_ref=f"skill:{manifest['id']}",
    )
    return manifest


def create_skill_task_packet(
    root: Path, skill_id: str, task_id: str, title: str
) -> dict[str, str]:
    manifest_path = (
        root / ".omo" / "_truth" / "task-center" / "skills" / f"{skill_id}.yaml"
    )
    manifest = load_yaml(manifest_path)
    task = {
        "id": task_id,
        "phase": 6,
        "milestone": "W3",
        "priority": "P0",
        "title": title,
        "status": "blocked",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": [
            *manifest.get("source_docs", []),
            f".omo/_truth/task-center/skills/{skill_id}.yaml",
        ],
        "deliverables": manifest.get("deliverables", []),
        "risk_level": manifest["risk_level"],
        "allowed_operation_level": manifest["allowed_operation_level"],
        "human_approval_required": False,
        "entry_gate": [],
        "evidence_required": ["skill execution uses governed worker bridge"],
        "test_plan": ["python3 -m pytest .omo/tests/test_omo_skill.py -q"],
        "worker_bridge": manifest["worker_bridge"],
        "allowed_write_paths": manifest.get("allowed_write_paths", []),
        "started_at": None,
        "completed_at": None,
        "blocked_by": "previous_wave_exit",
        "retry_count": 0,
    }
    create_blocked_task(
        root / ".omo",
        task_data=task,
        actor="omo_skill.create_skill_task_packet",
        source_ref=f"skill:{skill_id}",
    )
    output_path = root / ".omo" / "tasks" / "blocked" / f"{task_id.lower()}.yaml"
    return {"task_ref": str(output_path.relative_to(root))}
