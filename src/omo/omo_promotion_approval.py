from __future__ import annotations

from pathlib import Path

from .omo_shared import load_yaml


def _load_yaml(path: Path) -> dict:
    return load_yaml(path)


def evaluate_promotion_approval(
    root: Path,
    *,
    approval_ref: str | None,
    task_id: str,
    task_ref: str,
) -> dict[str, object]:
    if not approval_ref:
        return {"approval_ready": False, "blocker": "approval_missing"}
    if not approval_ref.endswith(".yaml"):
        return {"approval_ready": False, "blocker": "approval_invalid"}

    approval_path = root / approval_ref
    try:
        approval = _load_yaml(approval_path)
    except (FileNotFoundError, OSError):
        return {"approval_ready": False, "blocker": "approval_invalid"}

    if approval.get("task_id") != task_id:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_status") != "granted":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_scope") != "task.promote_apply":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("refs", {}).get("task_ref") != task_ref:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    return {"approval_ready": True, "blocker": None}
