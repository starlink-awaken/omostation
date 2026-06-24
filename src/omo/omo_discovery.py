#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from .omo_ingress import create_blocked_task, write_discovery_registry
from .omo_shared import load_yaml_docs, load_yaml_required


def _load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    tail = text[len("---\n") :]
    parts = tail.split("\n---\n")
    if len(parts) < 2:
        return {}
    frontmatter = "\n---\n".join(parts[:-1])
    return load_yaml_docs(frontmatter)


def discover_task_blueprints(root: Path, scan_dir: Path) -> dict:
    entries: list[dict[str, object]] = []
    blueprints: dict[str, dict[str, object]] = {}
    for path in sorted(scan_dir.rglob("*.md")):
        data = _load_frontmatter(path)
        blueprint = data.get("omo", {}).get("blueprint")
        if not blueprint:
            continue
        relative_path = str(path.relative_to(root))
        blueprint_id = blueprint["id"]
        entries.append(
            {
                "blueprint_id": blueprint_id,
                "title": blueprint["title"],
                "phase": blueprint["phase"],
                "milestone": blueprint["milestone"],
                "source_doc": relative_path,
            }
        )
        blueprints[blueprint_id] = {
            **blueprint,
            "source_doc": relative_path,
        }

    registry = {"entries": entries, "blueprints": blueprints}
    write_discovery_registry(
        root / ".omo",
        registry=registry,
        actor="omo_discovery.discover_task_blueprints",
        source_ref=str(scan_dir.relative_to(root)),
    )
    return registry


def instantiate_task_template(
    root: Path, blueprint_id: str, task_id: str, title: str
) -> dict[str, str]:
    registry_path = root / ".omo" / "_truth" / "task-center" / "discovery-registry.yaml"
    registry = load_yaml_required(registry_path)
    blueprint = registry["blueprints"][blueprint_id]

    task = {
        "id": task_id,
        "phase": blueprint["phase"],
        "milestone": blueprint["milestone"],
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
        "source_docs": [*blueprint.get("source_docs", []), blueprint["source_doc"]],
        "deliverables": blueprint.get("deliverables", []),
        "risk_level": blueprint["risk_level"],
        "allowed_operation_level": blueprint["allowed_operation_level"],
        "human_approval_required": False,
        "entry_gate": [],
        "evidence_required": blueprint.get("evidence_required", []),
        "test_plan": blueprint.get("test_plan", []),
        "started_at": None,
        "completed_at": None,
        "blocked_by": "previous_wave_exit",
        "retry_count": 0,
    }
    create_blocked_task(
        root / ".omo",
        task_data=task,
        actor="omo_discovery.instantiate_task_template",
        source_ref=f"blueprint:{blueprint_id}",
    )
    output_path = root / ".omo" / "tasks" / "blocked" / f"{task_id.lower()}.yaml"
    return {"task_ref": str(output_path.relative_to(root))}
