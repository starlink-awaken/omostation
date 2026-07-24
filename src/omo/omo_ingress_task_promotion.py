"""P110 refactor: omo_ingress_task_promotion 子模块 (从 omo_ingress_task_lifecycle.py 提取).

ADR-0103 P109 治理赋能三件套后, P110 推进 omo_ingress_task_lifecycle.py 拆解 (P109 --roadmap 第 1, HIGH ROI).
1530L god-module 拆 3 子模块 (promotion + contract + archive), main 保留 create + status.

业务 (4 functions):
  - promote_task_to_active (L595-675, 81L)
  - repair_task_promotion_approval (L676-789, 114L)
  - request_task_promotion_approval (L790-884, 95L)
  - revert_task_to_planned (L885-966, 82L)

业务: task promotion 流程 (active 状态进入/退出 + 审批修复/请求/撤回).

模块依赖:
  - copy (stdlib, deepcopy)
  - pathlib (Path)
  - typing (Any)
  - omo.omo_audit (record_audit)
  - omo.omo_io (fcntl_lock, write_text_atomic, write_yaml_atomic)
  - omo.omo_promotion_request (build_promotion_approval_request, promotion_approval_ref)
  - omo.omo_task_schema (validate_task_data)
  - omo.omo_ingress_paths (8 helpers)
  - omo.omo_ingress_registry (4 helpers)
  - omo.omo_ingress_trail (_record_trail)

向后兼容 (P88-P109 模式):
  omo_ingress_task_lifecycle.py 通过 `from .omo_ingress_task_promotion import (...)` re-export,
  保持 `from omo.omo_ingress_task_lifecycle import promote_task_to_active` 等不破.

P110 收益:
  - omo_ingress_task_lifecycle.py 1530L → ~705L (3 子模块拆后 + 5 re-export overhead)
  - 13 god-module list: 仍 12 (Python 3→2, omo_ingress_task_lifecycle 拆后 <1500L)
  - omostation task lifecycle 业务模块化, 后续维护成本下降
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
    _audit_log_path,
    _delivery_root,
    _find_task_path,
    _load_yaml,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_yaml_atomic
from omo.omo_promotion_request import (
    build_promotion_approval_request,
    promotion_approval_ref,
)
from omo.omo_task_schema import validate_task_data


def promote_task_to_active(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    handoff_ref: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if active_path.exists():
            return _load_yaml(active_path)
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(planned_path)
        if handoff_ref:
            handoffs = payload.setdefault("handoff_refs", [])
            if isinstance(handoffs, list) and handoff_ref not in handoffs:
                handoffs.append(handoff_ref)

        errors = validate_task_data(payload, group="active")
        if errors:
            raise ValueError("invalid promoted task: " + "; ".join(errors))

        write_yaml_atomic(active_path, payload)
        planned_path.unlink()

        artifact = {
            "kind": "task_promoted_to_active",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/active/{task_id}.yaml",
            "handoff_ref": handoff_ref,
            "actor": actor,
            "source_ref": source_ref,
            "promoted_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-promote-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-promote:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} handoff_ref={handoff_ref or '-'} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_promote_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="promote_task_to_active",
            target=f".omo/tasks/active/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="promote_task_to_active",
            target=f".omo/tasks/active/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "handoff_ref": handoff_ref},
        )
        return payload


def repair_task_promotion_approval(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    located = _find_task_path(
        omo_dir, task_id, groups=("planned", "active", "done", "remediation")
    )
    if located is None:
        raise ValueError(f"task not found: {task_id}")

    group, task_path = located
    approval_path: Path
    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        if not payload.get("human_approval_required"):
            raise ValueError("task does not require human approval")

        approval_ref = payload.get("approval_ref")
        if (
            not isinstance(approval_ref, str)
            or not approval_ref.endswith(".yaml")
            or not approval_ref.startswith(".omo/workers/runs/")
        ):
            approval_ref = promotion_approval_ref(task_id, timestamp)
            payload["approval_ref"] = approval_ref

        approval_path = omo_dir.parent / approval_ref
        task_ref = str(task_path.relative_to(omo_dir.parent))
        approval_record = build_promotion_approval_request(
            task_id=task_id,
            task_ref=task_ref,
            requested_operation_level=str(
                payload.get("allowed_operation_level")
                or payload.get("risk_level")
                or "L0"
            ),
            requested_at=str(payload.get("created_at") or timestamp),
            approval_ref=approval_ref,
        )
        if payload.get("approval_state") == "granted" or payload.get("status") in {
            "review",
            "done",
        }:
            approved_at = str(
                payload.get("updated_at") or payload.get("started_at") or timestamp
            )
            approval_record["approval_status"] = "granted"
            approval_record["approved_at"] = approved_at
            approval_record["approver"] = "omo-repair"

        write_yaml_atomic(approval_path, approval_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_promotion_approval_repaired",
            "task_id": task_id,
            "task_group": group,
            "task_ref": task_ref,
            "approval_ref": approval_ref,
            "actor": actor,
            "source_ref": source_ref,
            "repaired_at": timestamp,
            **_artifact_lifecycle_fields(
                artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{task_id}-approval-repair-{_timestamp_slug(timestamp)}.yaml"
            ),
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-approval-repair-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-approval-repair:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} group={group} actor={actor} approval_ref={approval_ref} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_repair_task_promotion_approval",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="repair_task_promotion_approval",
            target=task_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="repair_task_promotion_approval",
            target=task_ref,
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "task_id": task_id,
                "task_group": group,
                "approval_ref": approval_ref,
            },
        )
        return payload


def request_task_promotion_approval(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    approval_ref: str,
    approval_record: dict[str, Any],
    proposal_ref: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    approval_path = omo_dir.parent / approval_ref

    with fcntl_lock(_lock_path(omo_dir)):
        if not task_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(task_path)
        existing_ref = payload.get("approval_ref")
        if (
            existing_ref
            and isinstance(existing_ref, str)
            and existing_ref.endswith(".yaml")
            and "-promotion-approval-" in existing_ref
        ):
            raise ValueError(
                "task already points to a task-specific promotion approval"
            )

        payload["approval_ref"] = approval_ref
        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError(
                "invalid planned task after approval request: " + "; ".join(errors)
            )

        write_yaml_atomic(approval_path, approval_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_promotion_approval_requested",
            "task_id": task_id,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "approval_ref": approval_ref,
            "proposal_ref": proposal_ref,
            "actor": actor,
            "source_ref": source_ref,
            "requested_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-promotion-approval-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-promotion-approval:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} approval_ref={approval_ref} "
            f"proposal_ref={proposal_ref or '-'} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_request_task_promotion_approval",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="request_task_promotion_approval",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="request_task_promotion_approval",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "task_id": task_id,
                "approval_ref": approval_ref,
                "proposal_ref": proposal_ref,
            },
        )
        return payload


def revert_task_to_planned(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    handoff_refs_override: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if planned_path.exists():
            return _load_yaml(planned_path)
        if not active_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(active_path)
        if handoff_refs_override is not None:
            payload["handoff_refs"] = list(handoff_refs_override)
        payload["assigned_to"] = None
        payload["dispatch_id"] = None
        payload["run_ref"] = None
        payload["review_ref"] = None
        payload.pop("started_at", None)
        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError("invalid reverted planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, payload)
        active_path.unlink()

        artifact = {
            "kind": "task_reverted_to_planned",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/active/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "reverted_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-revert-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-revert:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_revert_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="revert_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="revert_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return payload
