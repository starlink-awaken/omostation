"""P110 refactor: omo_ingress_task_contract 子模块 (从 omo_ingress_task_lifecycle.py 提取).

业务 (2 functions):
  - record_task_contract_request (L967-1060, 94L)
  - route_self_evolution_to_remediation (L1061-1170, 110L)

业务: task contract 记录 + self-evolution 路由 (OPC P6 集成).

模块依赖: (同 promotion 子模块)
  - copy, pathlib, typing (stdlib)
  - omo.omo_audit, omo.omo_io, omo.omo_promotion_request, omo.omo_task_schema
  - omo.omo_ingress_paths, omo.omo_ingress_registry, omo.omo_ingress_trail

向后兼容 (P88-P109 模式):
  omo_ingress_task_lifecycle.py 通过 `from .omo_ingress_task_contract import (...)` re-export.

P110 关联: ADR-0094-103 + ADR-0104 (本 P110 ADR).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_ingress_paths import (
    _audit_log_path,
    _delivery_root,
    _load_yaml,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic
from omo.omo_task_schema import validate_task_data


def record_task_contract_request(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    request_ref: str,
    request_record: dict[str, Any],
    proposal_ref: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    request_path = omo_dir.parent / request_ref

    with fcntl_lock(_lock_path(omo_dir)):
        if not task_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(task_path)
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and request_ref not in handoff_refs:
            handoff_refs.append(request_ref)
        request_deliverables = request_record.get("deliverables")
        if (
            isinstance(request_deliverables, list)
            and request_deliverables
            and not payload.get("deliverables")
        ):
            payload["deliverables"] = list(request_deliverables)

        errors = validate_task_data(payload, group="active")
        if errors:
            raise ValueError(
                "invalid active task after contract request: " + "; ".join(errors)
            )

        write_yaml_atomic(request_path, request_record)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_contract_request_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/active/{task_id}.yaml",
            "request_ref": request_ref,
            "proposal_ref": proposal_ref,
            "actor": actor,
            "source_ref": source_ref,
            "recorded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-contract-request-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-contract-request:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} request_ref={request_ref} "
            f"proposal_ref={proposal_ref or '-'} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_record_task_contract_request",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_contract_request",
            target=f".omo/tasks/active/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_contract_request",
            target=f".omo/tasks/active/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "task_id": task_id,
                "request_ref": request_ref,
                "proposal_ref": proposal_ref,
            },
        )
        return payload


def route_self_evolution_to_remediation(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    review_note_body: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    remediation_path = omo_dir / "tasks" / "remediation" / f"{task_id}.yaml"
    review_note_rel = (
        Path(".omo") / "tasks" / "remediation-notes" / f"{task_id}-review.md"
    )
    review_note_path = omo_dir.parent / review_note_rel
    artifact_rel = (
        Path("runtime")
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / f"{task_id}-route-self-evolution-{_timestamp_slug(timestamp)}.yaml"
    )
    artifact_path = omo_dir.parent / artifact_rel

    with fcntl_lock(_lock_path(omo_dir)):
        if remediation_path.exists() and not planned_path.exists():
            return _load_yaml(remediation_path)
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")
        if not task_id.startswith("OPC-P6-SELF-EVOLUTION-"):
            raise ValueError(f"task is not a self-evolution packet: {task_id}")

        payload = _load_yaml(planned_path)
        payload["status"] = "review"
        payload["assigned_to"] = actor
        payload["dispatch_id"] = (
            f"self-evolution-remediation-{_timestamp_slug(timestamp)}"
        )
        payload["run_ref"] = str(artifact_rel)
        payload["review_ref"] = str(review_note_rel)
        payload["review_note"] = str(review_note_rel)
        payload["started_at"] = timestamp
        payload["approval_state"] = "granted"
        payload["approval_ref"] = (
            f"self-evolution-remediation-approval-{_timestamp_slug(timestamp)}"
        )

        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["routed_to_remediation_at"] = timestamp
            metadata["routed_to_remediation_by"] = actor
            metadata["routed_to_remediation_via"] = "self-evolution-review-lane"
            if source_ref:
                metadata["routed_to_remediation_source_ref"] = source_ref

        errors = validate_task_data(payload, group="remediation")
        if errors:
            raise ValueError("invalid remediation task: " + "; ".join(errors))

        remediation_path.parent.mkdir(parents=True, exist_ok=True)
        review_note_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(review_note_path, review_note_body)
        write_yaml_atomic(remediation_path, payload)
        planned_path.unlink()

        artifact = {
            "kind": "self_evolution_routed_to_remediation",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/remediation/{task_id}.yaml",
            "review_note_ref": str(review_note_rel),
            "actor": actor,
            "source_ref": source_ref,
            "routed_at": timestamp,
        }
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:self-evolution-remediation:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} review_note={review_note_rel} "
            f"source_ref={source_ref or '-'} artifact={artifact_rel}"
        )
        record_audit(
            action="ingress_route_self_evolution_to_remediation",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="route_self_evolution_to_remediation",
            target=f".omo/tasks/remediation/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="route_self_evolution_to_remediation",
            target=f".omo/tasks/remediation/{task_id}.yaml",
            artifact_ref=str(artifact_rel),
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "review_note_ref": str(review_note_rel)},
        )
        return payload
