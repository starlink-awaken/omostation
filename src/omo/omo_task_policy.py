from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


@dataclass(frozen=True)
class TaskPolicy:
    name: str
    target_roots: tuple[str, ...]
    file_glob: str
    prohibited_roots: tuple[str, ...] = ()
    required_fields: dict[str, Any] = field(default_factory=dict)
    required_status: str | None = None
    custom_validator: Callable[[Path, dict[str, Any]], list[str]] | None = None


OPC_P6_SELF_EVOLUTION_POLICY = TaskPolicy(
    name="self-evolution-approval",
    target_roots=("planned",),
    file_glob="OPC-P6-SELF-EVOLUTION-*.yaml",
    prohibited_roots=("active",),
    required_fields={
        "approval_required": True,
        "human_approval_required": True,
        "approval_state": "awaiting_human",
    },
    required_status="planned",
)


def _validate_human_approval_ref(task_path: Path, payload: dict[str, Any]) -> list[str]:
    if payload.get("human_approval_required") is not True:
        return []
    if payload.get("status") not in {"planned", "review"}:
        return []
    approval_ref = payload.get("approval_ref")
    if not isinstance(approval_ref, str) or not approval_ref:
        return [f"{task_path.name}: approval_ref must point to task-specific promotion approval yaml"]
    if not approval_ref.endswith(".yaml"):
        return [f"{task_path.name}: approval_ref must be a yaml artifact, got {approval_ref!r}"]
    if not approval_ref.startswith(".omo/workers/runs/"):
        return [f"{task_path.name}: approval_ref must live under .omo/workers/runs/, got {approval_ref!r}"]
    approval_path = task_path.parents[3] / approval_ref
    if not approval_path.exists():
        return [f"{task_path.name}: approval_ref target missing: {approval_ref}"]
    return []


HUMAN_APPROVAL_REF_POLICY = TaskPolicy(
    name="human-approval-ref",
    target_roots=("planned", "remediation"),
    file_glob="*.yaml",
    custom_validator=_validate_human_approval_ref,
)

TASK_POLICIES: dict[str, TaskPolicy] = {
    OPC_P6_SELF_EVOLUTION_POLICY.name: OPC_P6_SELF_EVOLUTION_POLICY,
    HUMAN_APPROVAL_REF_POLICY.name: HUMAN_APPROVAL_REF_POLICY,
}


def get_task_policy(name: str) -> TaskPolicy:
    try:
        return TASK_POLICIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(TASK_POLICIES))
        raise KeyError(f"unknown task policy: {name}. known policies: {known}") from exc


def count_planned_matches(workspace_root: Path, policy: TaskPolicy) -> int:
    total = 0
    tasks_root = workspace_root / ".omo" / "tasks"
    for root_name in policy.target_roots:
        target_dir = tasks_root / root_name
        if target_dir.exists():
            total += len(list(target_dir.glob(policy.file_glob)))
    return total


def check_task_policy(workspace_root: Path, policy: TaskPolicy) -> list[str]:
    tasks_root = workspace_root / ".omo" / "tasks"
    issues: list[str] = []

    for root_name in policy.target_roots:
        target_dir = tasks_root / root_name
        if not target_dir.exists():
            continue
        for path in sorted(target_dir.glob(policy.file_glob)):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for field_name, expected in policy.required_fields.items():
                if payload.get(field_name) != expected:
                    issues.append(f"{path.name}: {field_name} must be {expected!r}")
            if policy.required_status is not None and payload.get("status") != policy.required_status:
                issues.append(f"{path.name}: status must remain {policy.required_status}")
            if policy.custom_validator is not None:
                issues.extend(policy.custom_validator(path, payload))

    for root_name in policy.prohibited_roots:
        target_dir = tasks_root / root_name
        if not target_dir.exists():
            continue
        for path in sorted(target_dir.glob(policy.file_glob)):
            issues.append(f"{path.name}: {policy.name} task leaked into {root_name}/")
    return issues
