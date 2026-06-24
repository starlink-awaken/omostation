from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


from omo.omo_audit import record as record_audit
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic
from omo.omo_task_schema import validate_task_data
from omo.omo_ingress_paths import (
    _audit_log_path,
    _delivery_root,
    _load_yaml,
    _lock_path,
    _timestamp_slug,
    _utc_now,
)
from omo.omo_ingress_registry import (
    _load_registry,
    _record_mutation,
    _register_ingress,
    _write_registry,
)
from omo.omo_ingress_trail import _record_trail
from omo.omo_ingress_doc import (  # noqa: F401  (public re-export, 调用方 `from omo.omo_ingress import` 不变)
    create_audit_report,
    create_knowledge_doc,
    create_standard_doc,
)
from omo.omo_ingress_goal import (  # noqa: F401  (public re-export, 调用方 `from omo.omo_ingress import` 不变)
    create_goal,
    update_goal_progress,
)
from omo.omo_ingress_registry_writes import (  # noqa: F401  (public re-export, 调用方 `from omo.omo_ingress import` 不变)
    create_skill_manifest,
    update_governance_overlay_state,
    write_capability_registry_bundle,
    write_discovery_registry,
    write_manual_capabilities,
    write_task_center_control_decision,
    write_task_center_freshness,
    write_usage_accounting,
)
from omo.omo_ingress_task_lifecycle import (  # noqa: F401  (public re-export, 调用方 `from omo.omo_ingress import` 不变)
    complete_task,
    create_blocked_task,
    create_planned_task,
    promote_task_to_active,
    record_task_consensus,
    repair_task_promotion_approval,
    update_done_task_evidence_paths,
    update_planned_task_evidence_paths,
)


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
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
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
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
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
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
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
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return payload


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
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
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
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
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
    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    remediation_path = omo_dir / "tasks" / "remediation" / f"{task_id}.yaml"
    review_note_rel = (
        Path(".omo") / "tasks" / "remediation-notes" / f"{task_id}-review.md"
    )
    review_note_path = omo_dir.parent / review_note_rel
    artifact_rel = (
        Path(".omo")
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


def yield_task_to_planned(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    reason: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    active_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if planned_path.exists() and not active_path.exists():
            return _load_yaml(planned_path)
        if not active_path.exists():
            raise ValueError(f"active task not found: {task_id}")

        payload = _load_yaml(active_path)
        payload["status"] = "candidate"
        payload["assigned_to"] = None
        payload["dispatch_id"] = None
        payload["run_ref"] = None
        payload["review_ref"] = None
        payload.pop("started_at", None)

        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["yielded_at"] = timestamp
            metadata["yielded_via"] = "omo worker yield"
            metadata["yield_reason"] = reason
            metadata["yield_actor"] = actor
            if source_ref:
                metadata["yield_source_ref"] = source_ref

        errors = validate_task_data(payload, group="planned")
        if errors:
            raise ValueError("invalid yielded planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, payload)
        active_path.unlink()

        artifact = {
            "kind": "task_yielded_to_planned",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/active/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "reason": reason,
            "source_ref": source_ref,
            "yielded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-yield-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-yield:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} reason={reason} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_yield_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="yield_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="yield_task_to_planned",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "reason": reason},
        )
        return payload


def archive_done_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    archive_subdir: str = "",
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    done_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"
    archive_root = omo_dir / "tasks" / "archived"
    archive_dir = archive_root / archive_subdir if archive_subdir else archive_root
    archive_path = archive_dir / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if archive_path.exists() and not done_path.exists():
            return _load_yaml(archive_path)
        if not done_path.exists():
            raise ValueError(f"done task not found: {task_id}")

        payload = _load_yaml(done_path)
        payload["status"] = "archived"
        payload["archived_at"] = timestamp
        payload["archived_by"] = actor
        if source_ref:
            payload["archived_source_ref"] = source_ref

        archive_dir.mkdir(parents=True, exist_ok=True)
        write_yaml_atomic(archive_path, payload)
        done_path.unlink()

        archived_ref = f".omo/tasks/archived/{task_id}.yaml"
        if archive_subdir:
            archived_ref = f".omo/tasks/archived/{archive_subdir}/{task_id}.yaml"

        artifact = {
            "kind": "task_archived_from_done",
            "task_id": task_id,
            "task_ref_before": f".omo/tasks/done/{task_id}.yaml",
            "task_ref_after": archived_ref,
            "actor": actor,
            "source_ref": source_ref,
            "archived_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-archive-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-archive:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} archived_ref={archived_ref} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_archive_done_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="archive_done_task",
            target=archived_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="archive_done_task",
            target=archived_ref,
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return payload


# create_audit_report → 移至 omo_ingress_doc.py (SRP · P60+ 第五步, 见顶部 re-export)


def normalize_legacy_planned_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    planned_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    archived_dir = omo_dir / "tasks" / "archived" / "legacy-normalized"
    archived_path = archived_dir / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        if not planned_path.exists():
            raise ValueError(f"planned task not found: {task_id}")

        payload = _load_yaml(planned_path)
        original_status = str(payload.get("status") or "missing")
        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.setdefault("legacy_normalized_from", "planned")
            metadata["legacy_status"] = original_status
            metadata["normalized_at"] = timestamp
            metadata["normalized_by"] = actor
            if source_ref:
                metadata["normalization_source_ref"] = source_ref
            if "owner" in payload and payload.get("owner"):
                metadata.setdefault("legacy_owner", payload.get("owner"))
            if "priority" in payload and payload.get("priority"):
                metadata.setdefault("priority", payload.get("priority"))

        if original_status in {"done", "archived", "failed", "blocked"} or payload.get(
            "completed_at"
        ):
            archived_payload = deepcopy(payload)
            archived_payload["status"] = "archived"
            archived_payload["archived_at"] = timestamp
            archived_payload["archived_by"] = actor
            archived_dir.mkdir(parents=True, exist_ok=True)
            write_yaml_atomic(archived_path, archived_payload)
            planned_path.unlink()

            artifact = {
                "kind": "planned_task_legacy_archived",
                "task_id": task_id,
                "legacy_status": original_status,
                "task_ref_before": f".omo/tasks/planned/{task_id}.yaml",
                "task_ref_after": f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                "actor": actor,
                "source_ref": source_ref,
                "normalized_at": timestamp,
            }
            artifact_path = (
                _delivery_root(omo_dir)
                / "tasks"
                / f"{task_id}-legacy-archive-{_timestamp_slug(timestamp)}.yaml"
            )
            write_yaml_atomic(artifact_path, artifact)
            record_audit(
                action="ingress_archive_legacy_planned_task",
                debt_id="",
                actor=actor,
                details=(
                    f"task_id={task_id} legacy_status={original_status} source_ref={source_ref or '-'} "
                    f"artifact={artifact_path.relative_to(omo_dir.parent)}"
                ),
                audit_file=_audit_log_path(omo_dir),
            )
            _record_trail(
                omo_dir,
                actor=f"broker:{actor}",
                action="normalize_legacy_planned_task",
                target=f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                parent_step_id=f"ingress:legacy-planned-archive:{task_id}:{timestamp}",
            )
            _record_mutation(
                omo_dir,
                actor=actor,
                action="normalize_legacy_planned_task",
                target=f".omo/tasks/archived/legacy-normalized/{task_id}.yaml",
                artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
                source_ref=source_ref,
                created_at=timestamp,
                extra={
                    "task_id": task_id,
                    "legacy_status": original_status,
                    "result": "archived",
                },
            )
            return {"action": "archived", "task": archived_payload}

        normalized = deepcopy(payload)
        normalized["status"] = (
            "pending" if original_status == "pending" else "candidate"
        )
        normalized.setdefault("task_type", "feature")
        normalized.setdefault("risk_level", normalized.get("risk", "L0") or "L0")
        normalized.setdefault("depends_on", [])
        normalized.setdefault("deliverables", [normalized.get("title", task_id)])
        normalized.setdefault(
            "source_docs", [f".omo/tasks/planned/{task_id}.yaml#legacy-normalized"]
        )
        normalized.setdefault("knowledge_refs", [])
        normalized.setdefault("handoff_refs", [])
        normalized.setdefault("entry_gate", [])
        normalized.setdefault("evidence_required", ["legacy planned packet normalized"])
        normalized.setdefault(
            "test_plan", ["python3 scripts/omo_worker.py task validate --all-planned"]
        )
        normalized["assigned_to"] = None
        normalized["dispatch_id"] = None
        normalized["run_ref"] = None
        normalized["approval_ref"] = None
        normalized["review_ref"] = None
        normalized.pop("started_at", None)
        normalized.pop("completed_at", None)
        normalized.pop("completed_by", None)
        normalized.pop("archived_at", None)
        normalized.pop("archived_by", None)

        risk_level = str(normalized.get("risk_level") or "L0")
        if not normalized.get("allowed_operation_level"):
            normalized["allowed_operation_level"] = (
                risk_level if risk_level in {"L2", "L3"} else "L0"
            )
        if "human_approval_required" not in normalized:
            normalized["human_approval_required"] = normalized.get(
                "allowed_operation_level"
            ) in {"L2", "L3"}

        errors = validate_task_data(normalized, group="planned")
        if errors:
            raise ValueError("invalid normalized planned task: " + "; ".join(errors))

        write_yaml_atomic(planned_path, normalized)
        artifact = {
            "kind": "planned_task_legacy_normalized",
            "task_id": task_id,
            "legacy_status": original_status,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "normalized_at": timestamp,
            "normalized_status": normalized["status"],
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-legacy-normalize-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        record_audit(
            action="ingress_normalize_legacy_planned_task",
            debt_id="",
            actor=actor,
            details=(
                f"task_id={task_id} legacy_status={original_status} normalized_status={normalized['status']} "
                f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
            ),
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="normalize_legacy_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=f"ingress:legacy-planned-normalize:{task_id}:{timestamp}",
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="normalize_legacy_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "task_id": task_id,
                "legacy_status": original_status,
                "normalized_status": normalized["status"],
            },
        )
        return {"action": "normalized", "task": normalized}


def upsert_debt_item(
    omo_dir: Path,
    *,
    debt_data: dict[str, Any],
    ingress_plane: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    if not isinstance(debt_data, dict):
        raise ValueError("debt_data must be a dict")
    if not debt_data.get("id"):
        raise ValueError("debt item requires id")
    if not debt_data.get("title"):
        raise ValueError("debt item requires title")

    debt_id = str(debt_data["id"])
    debt_path = omo_dir / "debt" / "items" / f"{debt_id}.yaml"
    timestamp = now or _utc_now()
    effective_source_ref = source_ref or str(debt_data.get("source_ref") or "")
    artifact_ref = f".omo/_delivery/ingress/debts/{debt_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)

        if effective_source_ref:
            mapped_debt_id = registry["debts"]["by_source_ref"].get(
                effective_source_ref
            )
            if mapped_debt_id and mapped_debt_id != debt_id:
                raise ValueError(
                    f"source_ref already mapped to different debt: {effective_source_ref} -> {mapped_debt_id}"
                )

        existing_payload = _load_yaml(debt_path) if debt_path.exists() else {}
        payload = deepcopy(existing_payload)
        payload.update(deepcopy(debt_data))
        payload["id"] = debt_id
        payload["title"] = str(payload["title"])
        payload["source_ref"] = effective_source_ref
        payload.setdefault("description", "")
        payload.setdefault("severity", "medium")
        payload.setdefault("source", ingress_plane)
        payload.setdefault("domain", "workspace")
        payload.setdefault("scope", "governance_kernel")
        payload.setdefault("owner", ingress_plane)
        payload.setdefault("affected_roots", [".omo"])
        payload.setdefault("evidence_refs", [])
        payload.setdefault("mitigation_refs", [])
        payload.setdefault("gate_level", "none")
        payload.setdefault("history", [])

        first_seen_at = str(
            existing_payload.get("first_seen_at")
            or payload.get("first_seen_at")
            or payload.get("registered_at")
            or timestamp
        )
        registered_at = str(
            existing_payload.get("registered_at")
            or payload.get("registered_at")
            or first_seen_at
        )
        opened_at = str(
            existing_payload.get("opened_at")
            or payload.get("opened_at")
            or registered_at
        )
        occurrence_count = int(existing_payload.get("occurrence_count") or 0) + 1

        payload["registered_at"] = registered_at
        payload["opened_at"] = opened_at
        payload["first_seen_at"] = first_seen_at
        payload["last_seen_at"] = timestamp
        payload["occurrence_count"] = occurrence_count
        payload["status"] = str(payload.get("status") or "open")
        payload["lifecycle_state"] = str(
            payload.get("lifecycle_state")
            or existing_payload.get("lifecycle_state")
            or "identified"
        )

        note = (
            f"Observed debt {debt_id} again (occurrence_count={occurrence_count})."
            if existing_payload
            else f"Registered debt item {debt_id}."
        )
        history = payload.get("history")
        if not isinstance(history, list):
            payload["history"] = []
        payload["history"].append(
            {
                "at": timestamp,
                "action": "register" if not existing_payload else "seen_again",
                "note": note,
                "actor": ingress_plane,
            }
        )

        write_yaml_atomic(debt_path, payload)

        debt_registry_path = omo_dir / "_truth" / "registry" / "debt.yaml"
        debt_registry = (
            _load_yaml(debt_registry_path)
            if debt_registry_path.exists()
            else {"version": 1}
        )
        debt_registry.setdefault("items_dir", ".omo/debt/items")
        debt_registry.setdefault("seed_items", [])
        debt_ref = f".omo/debt/items/{debt_id}.yaml"
        if debt_ref not in debt_registry["seed_items"]:
            debt_registry["seed_items"] = [*debt_registry["seed_items"], debt_ref]
        write_yaml_atomic(debt_registry_path, debt_registry)

        artifact = {
            "kind": "debt_upserted",
            "debt_id": debt_id,
            "title": payload["title"],
            "ingress_plane": ingress_plane,
            "source_ref": effective_source_ref,
            "created_at": registered_at,
            "last_seen_at": timestamp,
            "occurrence_count": occurrence_count,
            "debt_ref": debt_ref,
            "lifecycle_state": payload["lifecycle_state"],
            "artifact_ref": artifact_ref,
            "broker_ref": "projects/omo/src/omo/omo_ingress.py",
            "retention_mode": "manual_archive",
        }
        artifact_path = _delivery_root(omo_dir) / "debts" / f"{debt_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)

        _register_ingress(
            registry,
            kind="debts",
            item_id=debt_id,
            source_ref=effective_source_ref,
            artifact_ref=artifact_ref,
            fingerprint=payload,
            created_at=registered_at,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:debt:{debt_id}:{timestamp}"
        details = (
            f"debt_id={debt_id} ingress_plane={ingress_plane} "
            f"source_ref={effective_source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_upsert_debt",
            debt_id=debt_id,
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="upsert_debt_item",
            target=debt_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="upsert_debt_item",
            target=debt_ref,
            artifact_ref=artifact["artifact_ref"],
            source_ref=effective_source_ref,
            created_at=timestamp,
            extra={"debt_id": debt_id, "occurrence_count": occurrence_count},
        )
        return payload


def remove_debt_item(
    omo_dir: Path,
    *,
    debt_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> bool:
    debt_path = omo_dir / "debt" / "items" / f"{debt_id}.yaml"
    artifact_path = _delivery_root(omo_dir) / "debts" / f"{debt_id}.yaml"
    debt_registry_path = omo_dir / "_truth" / "registry" / "debt.yaml"
    timestamp = now or _utc_now()

    with fcntl_lock(_lock_path(omo_dir)):
        if not debt_path.exists() and not artifact_path.exists():
            return False

        registry = _load_registry(omo_dir)
        if debt_id in registry["debts"]["by_id"]:
            existing = registry["debts"]["by_id"].pop(debt_id)
            mapped_source_ref = str(existing.get("source_ref") or "")
            if mapped_source_ref:
                registry["debts"]["by_source_ref"].pop(mapped_source_ref, None)
        elif source_ref:
            registry["debts"]["by_source_ref"].pop(source_ref, None)
        _write_registry(omo_dir, registry)

        if debt_registry_path.exists():
            debt_registry = _load_yaml(debt_registry_path) or {"version": 1}
            seed_items = debt_registry.get("seed_items", [])
            debt_ref = f".omo/debt/items/{debt_id}.yaml"
            debt_registry["seed_items"] = [
                item for item in seed_items if item != debt_ref
            ]
            write_yaml_atomic(debt_registry_path, debt_registry)

        if debt_path.exists():
            debt_path.unlink()
        if artifact_path.exists():
            artifact_path.unlink()

        record_audit(
            action="ingress_remove_debt",
            debt_id=debt_id,
            actor=actor,
            details=f"debt_id={debt_id} actor={actor}",
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="remove_debt_item",
            target=f".omo/debt/items/{debt_id}.yaml",
            parent_step_id=f"ingress:debt-remove:{debt_id}:{timestamp}",
        )
        return True


def write_system_projection_fields(
    omo_dir: Path,
    *,
    updates: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
    allowed_fields: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """原子写入 system.yaml 的投影字段 (白名单控制)."""
    timestamp = now or _utc_now()
    system_path = omo_dir / "state" / "system.yaml"
    if not system_path.exists():
        raise FileNotFoundError(f"missing state/system.yaml: {system_path}")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("system projection updates must be a non-empty mapping")

    allowed = set(allowed_fields or updates.keys())
    invalid = sorted(key for key in updates if key not in allowed)
    if invalid:
        raise ValueError(
            f"system projection contains non-whitelisted fields: {invalid}"
        )

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(system_path)
        if not isinstance(payload, dict):
            raise ValueError("state/system.yaml top-level must be a mapping")
        for key, value in updates.items():
            payload[key] = deepcopy(value)
        write_yaml_atomic(system_path, payload)

        artifact = {
            "kind": "system_projection_fields_written",
            "system_ref": ".omo/state/system.yaml",
            "updated_fields": sorted(updates.keys()),
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "state"
            / f"system-projection-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:system-projection:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"fields={','.join(sorted(updates.keys()))} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_write_system_projection_fields",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_system_projection_fields",
            target=".omo/state/system.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_system_projection_fields",
            target=".omo/state/system.yaml",
            artifact_ref=f".omo/_delivery/ingress/state/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"updated_fields": sorted(updates.keys())},
        )
        return deepcopy(payload)
