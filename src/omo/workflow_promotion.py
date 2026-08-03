"""Governed promotion from a knowledge-backed task to Workflow Mesh.

This broker creates only a ``WorkflowRequested`` event. It never grants
admission, starts a worker, or calls an external connector. The next step is
still owned by the existing approval and admission gates.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .knowledge_action import record_knowledge_action
from .omo_shared import load_yaml
from .omo_task_schema import validate_task_file
from .workflow_mesh import WorkflowMeshStore, new_workflow_event


class WorkflowPromotionError(ValueError):
    """Raised when a task cannot be promoted into a requested workflow."""


_OPERATION_LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
_SCENE_FIELDS = ("scene_id", "journey_id", "outcome_metric")


def _text(value: Any, field: str, *, max_length: int = 240) -> str:
    result = str(value or "").strip()
    if not result:
        raise WorkflowPromotionError(f"missing required field: {field}")
    if len(result) > max_length:
        raise WorkflowPromotionError(f"field is too long: {field}")
    return result


def _scene_binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise WorkflowPromotionError("scene_binding is required")
    result = {
        field: _text(value.get(field), f"scene_binding.{field}", max_length=160)
        for field in _SCENE_FIELDS
    }
    return result


def _evidence_plan(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise WorkflowPromotionError("evidence_plan must be a list of strings")
    if not value or len(value) > 12:
        raise WorkflowPromotionError("evidence_plan must contain 1 to 12 items")
    result = [
        _text(item, f"evidence_plan[{index}]", max_length=300)
        for index, item in enumerate(value)
    ]
    if len(set(result)) != len(result):
        raise WorkflowPromotionError("evidence_plan must not contain duplicates")
    return result


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _task_file(root: Path, task_id: str, omo_dir: str | Path) -> Path:
    if not task_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
        for char in task_id
    ):
        raise WorkflowPromotionError("invalid task id")
    path = root / Path(omo_dir) / "tasks" / "planned" / f"{task_id}.yaml"
    if not path.is_file():
        raise WorkflowPromotionError(f"planned task not found: {task_id}")
    errors = validate_task_file(path)
    if errors:
        raise WorkflowPromotionError("; ".join(errors))
    return path


def _result(
    *,
    status: str,
    task_id: str,
    task_ref: str,
    workflow_run_id: str,
    request: Mapping[str, Any],
    event: Mapping[str, Any],
    knowledge_action: Mapping[str, Any],
) -> dict[str, Any]:
    approval_required = bool(request["approval_required"])
    return {
        "status": status,
        "request_state": "approval_required"
        if approval_required
        else "ready_for_admission",
        "task_id": task_id,
        "task_ref": task_ref,
        "workflow_run_id": workflow_run_id,
        "trace_id": workflow_run_id,
        "workflow": {
            "name": request["workflow_name"],
            "version": request["workflow_version"],
        },
        "scene_binding": request["scene_binding"],
        "operation_level": request["operation_level"],
        "evidence_plan": request["evidence_plan"],
        "approval": {
            "required": approval_required,
            "state": "pending" if approval_required else "not_required",
        },
        "external_side_effects": "disabled",
        "worker_launch": False,
        "knowledge_action": knowledge_action,
        "event": {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "idempotency_key": event["idempotency_key"],
        },
    }


def request_workflow_from_task(
    root: Path,
    *,
    task_id: str,
    workflow_name: str,
    scene_binding: Mapping[str, Any],
    evidence_plan: Sequence[Any],
    actor: str = "omo",
    workflow_version: str = "v1",
    operation_level: str | None = None,
    workflow_run_id: str | None = None,
    omo_dir: str | Path = ".omo",
    now: str | None = None,
) -> dict[str, Any]:
    """Record a knowledge-backed workflow request without admitting it.

    A request is intentionally allowed to stop at ``ready_for_admission`` or
    ``approval_required``. Admission and dispatch remain separate calls.
    """
    task_path = _task_file(root, task_id, omo_dir)
    task = load_yaml(task_path)
    knowledge_refs = task.get("knowledge_refs") or []
    if not isinstance(knowledge_refs, list) or not knowledge_refs:
        raise WorkflowPromotionError("knowledge-backed task requires knowledge_refs")
    if len(knowledge_refs) > 20 or not all(
        isinstance(item, str) and item.strip() for item in knowledge_refs
    ):
        raise WorkflowPromotionError(
            "task knowledge_refs must be a list of up to 20 non-empty strings"
        )

    name = _text(workflow_name, "workflow_name", max_length=160)
    version = _text(workflow_version, "workflow_version", max_length=40)
    binding = _scene_binding(scene_binding)
    plan = _evidence_plan(evidence_plan)
    requested_level = (
        str(
            operation_level
            or task.get("allowed_operation_level")
            or task.get("risk_level")
            or "L0"
        )
        .strip()
        .upper()
    )
    if requested_level not in _OPERATION_LEVELS:
        raise WorkflowPromotionError("operation_level must be L0, L1, L2, or L3")
    task_level = (
        str(task.get("allowed_operation_level") or task.get("risk_level") or "L0")
        .strip()
        .upper()
    )
    if task_level not in _OPERATION_LEVELS:
        raise WorkflowPromotionError("task operation level is invalid")
    if _OPERATION_LEVELS[requested_level] > _OPERATION_LEVELS[task_level]:
        raise WorkflowPromotionError("requested operation level exceeds task allowance")

    approval_required = bool(
        task.get("human_approval_required")
        or task.get("risk_level") in {"L2", "L3"}
        or requested_level in {"L2", "L3"}
    )
    request = {
        "task_id": task_id,
        "workflow_name": name,
        "workflow_version": version,
        "scene_binding": binding,
        "evidence_plan": plan,
        "operation_level": requested_level,
        "approval_required": approval_required,
        "knowledge_ref_digest": _digest({"knowledge_refs": knowledge_refs}),
    }
    request_key = f"workflow-request:{_digest(request)}"
    run_id = workflow_run_id or f"mesh-request-{task_id}-{_digest(request)[:12]}"
    timestamp = now or datetime.now(UTC).replace(microsecond=0).isoformat()
    task_ref = str(task_path.relative_to(root))
    store = WorkflowMeshStore(root / Path(omo_dir))
    existing = next(
        (
            event
            for event in store.events()
            if event.get("idempotency_key") == request_key
        ),
        None,
    )
    event = existing or new_workflow_event(
        "WorkflowRequested",
        run_id,
        trace_id=run_id,
        producer="omo.workflow_promotion",
        idempotency_key=request_key,
        scene_binding=binding,
        payload={
            "task_id": task_id,
            "task_ref": task_ref,
            "workflow": {"name": name, "version": version},
            "operation_level": requested_level,
            "approval_required": approval_required,
            "evidence_plan": plan,
            "knowledge_ref_digest": request["knowledge_ref_digest"],
            "requested_at": timestamp,
            "external_side_effects": "disabled",
        },
    )
    if existing is None:
        event = store.append(event)

    action = record_knowledge_action(
        root / Path(omo_dir),
        {
            "action_kind": "workflow_requested",
            "query_digest": f"sha256:{_digest({'task_id': task_id, 'workflow': name})}",
            "knowledge_refs": [{"ref": item} for item in knowledge_refs],
            "scene_binding": binding,
            "task_ref": task_ref,
            "workflow_run_id": run_id,
            "observed_at": timestamp,
        },
        actor=actor,
    )
    return _result(
        status="deduplicated" if existing else "requested",
        task_id=task_id,
        task_ref=task_ref,
        workflow_run_id=run_id,
        request=request,
        event=event,
        knowledge_action=action,
    )


__all__ = ["WorkflowPromotionError", "request_workflow_from_task"]
