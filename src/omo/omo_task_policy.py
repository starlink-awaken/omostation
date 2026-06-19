from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TaskPolicy:
    name: str
    planned_glob: str
    active_glob: str
    required_fields: dict[str, Any] = field(default_factory=dict)
    required_status: str = "planned"


OPC_P6_SELF_EVOLUTION_POLICY = TaskPolicy(
    name="self-evolution-approval",
    planned_glob="OPC-P6-SELF-EVOLUTION-*.yaml",
    active_glob="OPC-P6-SELF-EVOLUTION-*.yaml",
    required_fields={
        "approval_required": True,
        "human_approval_required": True,
        "approval_state": "awaiting_human",
    },
    required_status="planned",
)

TASK_POLICIES: dict[str, TaskPolicy] = {
    OPC_P6_SELF_EVOLUTION_POLICY.name: OPC_P6_SELF_EVOLUTION_POLICY,
}


def get_task_policy(name: str) -> TaskPolicy:
    try:
        return TASK_POLICIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(TASK_POLICIES))
        raise KeyError(f"unknown task policy: {name}. known policies: {known}") from exc


def count_planned_matches(workspace_root: Path, policy: TaskPolicy) -> int:
    planned_dir = workspace_root / ".omo" / "tasks" / "planned"
    if not planned_dir.exists():
        return 0
    return len(list(planned_dir.glob(policy.planned_glob)))


def check_task_policy(workspace_root: Path, policy: TaskPolicy) -> list[str]:
    planned_dir = workspace_root / ".omo" / "tasks" / "planned"
    active_dir = workspace_root / ".omo" / "tasks" / "active"
    issues: list[str] = []

    for path in sorted(planned_dir.glob(policy.planned_glob)):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for field_name, expected in policy.required_fields.items():
            if payload.get(field_name) != expected:
                issues.append(f"{path.name}: {field_name} must be {expected!r}")
        if payload.get("status") != policy.required_status:
            issues.append(f"{path.name}: status must remain {policy.required_status}")

    for path in sorted(active_dir.glob(policy.active_glob)):
        issues.append(f"{path.name}: {policy.name} task leaked into active/")
    return issues
