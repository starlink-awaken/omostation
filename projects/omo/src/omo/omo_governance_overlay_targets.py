from __future__ import annotations

from pathlib import Path

import yaml

try:
    from .omo_promotion_approval import evaluate_promotion_approval
    from .omo_task_schema import validate_task_file
except ModuleNotFoundError:
    from .omo_promotion_approval import evaluate_promotion_approval
    from .omo_task_schema import validate_task_file


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _task_has_task_specific_promotion_approval(approval_ref: str | None) -> bool:
    return bool(approval_ref and approval_ref.endswith(".yaml") and "-promotion-approval-" in approval_ref)


def evaluate_governance_overlay_planned_target(
    root: Path, target_ref: str, *, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    if not target_ref.startswith(".omo/tasks/planned/"):
        return {
            "target_ref": target_ref,
            "task_id": None,
            "state": "unsupported_target_ref",
            "action": "mark_blocked",
            "result": "unsupported_target_ref",
            "detail": "only .omo/tasks/planned/*.yaml target refs are supported in v1",
        }

    task_path = root / target_ref
    if not task_path.exists():
        return {
            "target_ref": target_ref,
            "task_id": Path(target_ref).stem,
            "state": "missing_target_ref",
            "action": "mark_blocked",
            "result": "missing_target_ref",
            "detail": "target ref is missing from planned/active/done/blocked task directories",
        }

    omo = Path(omo_dir)
    goals = _load_yaml_required(root / omo / "goals" / "current.yaml")
    task = _load_yaml_required(task_path)
    task_id = str(task["id"])
    active_target = root / omo / "tasks" / "active" / task_path.name
    approval_ref = str(task.get("approval_ref")) if task.get("approval_ref") else None
    approval_result = (
        {"approval_ready": True, "blocker": None}
        if not task.get("human_approval_required")
        else evaluate_promotion_approval(
            root,
            approval_ref=approval_ref,
            task_id=task_id,
            task_ref=target_ref,
        )
    )

    blockers: list[str] = []
    if task.get("status") not in {"candidate", "pending"}:
        blockers.append("status_invalid")
    if task.get("phase") != int(goals["phase"]) + 1:
        blockers.append("phase_mismatch")
    if approval_result["blocker"] == "approval_missing":
        blockers.append("approval_missing")
    elif approval_result["blocker"] == "approval_invalid":
        blockers.append("approval_invalid")
    if active_target.exists():
        blockers.append("target_path_exists")
    if validate_task_file(task_path):
        blockers.append("active_schema_invalid")

    if not blockers:
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": "planned_promotion_ready",
            "action": "promote_apply",
            "result": "promotion_ready",
            "detail": "task is eligible for promote-apply without further gates",
        }

    if blockers == ["approval_missing"]:
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": "planned_approval_needed",
            "action": "request_approval",
            "result": "approval_request_needed",
            "detail": "task requires task-specific promotion approval before promote-apply",
        }

    if blockers == ["phase_mismatch", "approval_missing"]:
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": "planned_approval_prep_needed",
            "action": "request_approval",
            "result": "approval_prep_needed",
            "detail": "phase gate is still closed, but task-specific promotion approval can be prepared now",
            "blockers": blockers,
        }

    if blockers == ["approval_invalid"] and _task_has_task_specific_promotion_approval(approval_ref):
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": "planned_approval_pending",
            "action": "await_approval",
            "result": "approval_pending",
            "detail": "task-specific promotion approval exists but is not granted yet",
        }

    if blockers == ["phase_mismatch", "approval_invalid"] and _task_has_task_specific_promotion_approval(approval_ref):
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": "planned_approval_prep_pending",
            "action": "await_approval",
            "result": "approval_prep_pending",
            "detail": "phase gate is still closed and task-specific promotion approval is not granted yet",
            "blockers": blockers,
        }

    return {
        "target_ref": target_ref,
        "task_id": task_id,
        "state": "planned_promotion_blocked",
        "action": "promote_apply",
        "result": "promotion_blocked",
        "detail": "planned task is blocked by existing promotion gates",
        "blockers": blockers,
    }
