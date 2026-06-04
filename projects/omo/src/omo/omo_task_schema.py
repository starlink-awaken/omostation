from __future__ import annotations

import argparse
from pathlib import Path

import yaml

VALID_STATUSES = {
    "candidate",
    "pending",
    "in_progress",
    "review",
    "done",
    "blocked",
    "failed",
}
VALID_LEVELS = {"L0", "L1", "L2", "L3"}
EXECUTION_STATUSES = {"pending", "in_progress", "review"}
PLANNED_STATUSES = {"candidate", "pending"}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _require_fields(task: dict, fields: list[str], errors: list[str]) -> None:
    for field in fields:
        if field not in task:
            errors.append(f"missing required field: {field}")


def _require_list(
    task: dict, field: str, errors: list[str], allow_empty: bool = True
) -> None:
    value = task.get(field)
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    if not allow_empty and not value:
        errors.append(f"{field} must not be empty")


def _require_task_packet(task: dict, errors: list[str]) -> None:
    if "test_plan" not in task:
        errors.append("missing required field: test_plan")
    else:
        _require_list(task, "test_plan", errors, allow_empty=False)
    if not task.get("source_docs"):
        errors.append("source_docs must not be empty")


def validate_task_data(task: dict, group: str | None = None) -> list[str]:
    errors: list[str] = []

    _require_fields(
        task,
        [
            "id",
            "title",
            "status",
            "assigned_to",
            "dispatch_id",
            "run_ref",
            "approval_ref",
            "review_ref",
            "knowledge_refs",
            "handoff_refs",
            "risk_level",
            "allowed_operation_level",
            "human_approval_required",
            "source_docs",
            "entry_gate",
            "evidence_required",
        ],
        errors,
    )

    if "status" in task and task["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: {task['status']}")
    if "risk_level" in task and task["risk_level"] not in VALID_LEVELS:
        errors.append(f"invalid risk_level: {task['risk_level']}")
    if (
        "allowed_operation_level" in task
        and task["allowed_operation_level"] not in VALID_LEVELS
    ):
        errors.append(
            f"invalid allowed_operation_level: {task['allowed_operation_level']}"
        )

    for field in (
        "knowledge_refs",
        "handoff_refs",
        "source_docs",
        "entry_gate",
        "evidence_required",
        "deliverables",
    ):
        if field in task:
            _require_list(
                task,
                field,
                errors,
                allow_empty=field in {"knowledge_refs", "handoff_refs", "entry_gate"},
            )

    planned_context = group == "planned"
    execution_context = group == "active" or task.get("status") in EXECUTION_STATUSES
    if planned_context:
        _require_task_packet(task, errors)
        if task.get("status") not in PLANNED_STATUSES:
            errors.append("planned tasks must use candidate or pending status")
        for field, error in (
            ("assigned_to", "planned tasks must not set assigned_to"),
            ("dispatch_id", "planned tasks must not set dispatch_id"),
            ("run_ref", "planned tasks must not set run_ref"),
            ("review_ref", "planned tasks must not set review_ref"),
            ("started_at", "planned tasks must not set started_at"),
        ):
            if task.get(field) is not None:
                errors.append(error)
    elif execution_context:
        _require_task_packet(task, errors)

        requires_approval = (
            task.get("risk_level") in {"L2", "L3"}
            or task.get("allowed_operation_level") in {"L2", "L3"}
            or bool(task.get("human_approval_required"))
        )
        if requires_approval and not task.get("approval_ref"):
            errors.append("approval_ref is required for L2/L3 tasks")

    if not planned_context and task.get("status") == "in_progress":
        for field in ("assigned_to", "dispatch_id", "run_ref", "started_at"):
            if not task.get(field):
                errors.append(f"{field} must be set when status=in_progress")

    if not planned_context and task.get("status") == "review":
        for field in ("assigned_to", "dispatch_id", "run_ref", "review_ref"):
            if not task.get(field):
                errors.append(f"{field} must be set when status=review")

    return errors


def validate_task_file(path: Path) -> list[str]:
    task = _load_yaml(path)
    return validate_task_data(task, group=path.parent.name)


def validate_task_group(root: Path, group: str) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for task_file in sorted((root / ".omo" / "tasks" / group).glob("*.yaml")):
        errors = validate_task_file(task_file)
        if errors:
            results[str(task_file)] = errors
    return results


def validate_active_tasks(root: Path) -> dict[str, list[str]]:
    return validate_task_group(root, "active")


def validate_planned_tasks(root: Path) -> dict[str, list[str]]:
    return validate_task_group(root, "planned")


def main() -> int:
    parser = argparse.ArgumentParser(prog="omo-task-schema")
    parser.add_argument("task_file", nargs="?")
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--all-active", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.all_active or not args.task_file:
        results = validate_active_tasks(root)
        if not results:
            return 0
        for path, errors in results.items():
            print(path)
            for error in errors:
                print(f"  - {error}")
        return 1

    errors = validate_task_file(Path(args.task_file))
    if not errors:
        return 0
    for error in errors:
        print(error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
