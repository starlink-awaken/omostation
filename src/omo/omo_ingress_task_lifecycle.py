"""omo_ingress task lifecycle (从 God Module 拆出, SRP · P60+ 第七步第一批).

_task_payload_with_metadata / create_planned_task / create_blocked_task.
task 创建 (planned/blocked) + metadata 注入. 依赖 paths + registry + trail
+ omo_io + omo_audit + task_schema — 无循环.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic
from omo.omo_promotion_request import (
    build_promotion_approval_request,
    promotion_approval_ref,
)
from omo.omo_task_schema import validate_task_data
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
    _audit_log_path,
    _delivery_root,
    _find_task_path,
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


def _task_payload_with_metadata(
    task_data: dict[str, Any],
    *,
    ingress_plane: str,
    source_ref: str,
) -> dict[str, Any]:
    payload = deepcopy(task_data)
    metadata = payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("ingress_plane", ingress_plane)
        metadata.setdefault("broker", "projects/omo/src/omo/omo_ingress.py")
        if source_ref:
            metadata.setdefault("source_ref", source_ref)
    return payload


def create_planned_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    ingress_plane: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    errors = validate_task_data(task_data, group="planned")
    if errors:
        raise ValueError("invalid planned task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    timestamp = now or _utc_now()
    payload = _task_payload_with_metadata(
        task_data, ingress_plane=ingress_plane, source_ref=source_ref
    )
    artifact_ref = f".omo/_delivery/ingress/tasks/{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)

        if source_ref:
            mapped_task_id = registry["tasks"]["by_source_ref"].get(source_ref)
            if mapped_task_id and mapped_task_id != task_id:
                raise ValueError(
                    f"source_ref already mapped to different task: {source_ref} -> {mapped_task_id}"
                )

        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == payload:
                _register_ingress(
                    registry,
                    kind="tasks",
                    item_id=task_id,
                    source_ref=source_ref,
                    artifact_ref=artifact_ref,
                    fingerprint=payload,
                    created_at=str(
                        existing_payload.get("metadata", {}).get(
                            "created_at", timestamp
                        )
                    ),
                )
                _write_registry(omo_dir, registry)
                return existing_payload
            raise ValueError(
                f"planned task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_created",
            "task_id": task_id,
            "title": payload.get("title", ""),
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "evidence_required": payload.get("evidence_required", []),
            "source_docs": payload.get("source_docs", []),
            **_artifact_lifecycle_fields(artifact_ref=artifact_ref),
        }
        artifact_path = _delivery_root(omo_dir) / "tasks" / f"{task_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="tasks",
            item_id=task_id,
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=payload,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:task:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} ingress_plane={ingress_plane} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_planned_task",
            debt_id="",
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "ingress_plane": ingress_plane},
        )
        return payload


def create_blocked_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    errors = validate_task_data(task_data, group="blocked")
    if errors:
        raise ValueError("invalid blocked task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_filename = f"{task_id.lower()}.yaml"
    task_path = omo_dir / "tasks" / "blocked" / task_filename
    timestamp = now or _utc_now()

    with fcntl_lock(_lock_path(omo_dir)):
        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == task_data:
                return existing_payload
            raise ValueError(
                f"blocked task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, task_data)

        artifact = {
            "kind": "blocked_task_created",
            "task_id": task_id,
            "task_ref": f".omo/tasks/blocked/{task_filename}",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-blocked-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-blocked:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_blocked_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(task_data)


def record_task_consensus(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    message: str,
    task_status: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    resolved = _find_task_path(omo_dir, task_id, groups=("active", "blocked", "done"))
    if resolved is None:
        raise ValueError(f"task not found in active/blocked/done: {task_id}")
    group, task_path = resolved
    evidence_filename = f"{task_id.lower()}-{_timestamp_slug(timestamp)}.yaml"
    evidence_path = (
        omo_dir / "_delivery" / "task-center" / "consensus" / evidence_filename
    )

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        evidence = {
            "task_id": task_id,
            "classification": "positive_confirmation",
            "message": message,
            "confirmed_at": timestamp,
            "task_status": task_status or payload.get("status"),
        }
        evidence_ref = f".omo/_delivery/task-center/consensus/{evidence_filename}"
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and evidence_ref not in handoff_refs:
            handoff_refs.append(evidence_ref)

        errors = validate_task_data(payload, group=group)
        if errors:
            raise ValueError(
                "invalid task after consensus update: " + "; ".join(errors)
            )

        write_yaml_atomic(evidence_path, evidence)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_consensus_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/{group}/{task_path.name}",
            "evidence_ref": evidence_ref,
            "actor": actor,
            "source_ref": source_ref,
            "recorded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-consensus-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-consensus:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} evidence_ref={evidence_ref} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_record_task_consensus",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_consensus",
            target=evidence_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_consensus",
            target=evidence_ref,
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "task_group": group},
        )
        return artifact


def complete_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_roots = {
        "active": omo_dir / "tasks" / "active" / f"{task_id}.yaml",
        "planned": omo_dir / "tasks" / "planned" / f"{task_id}.yaml",
    }
    done_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        src_group: str | None = None
        src_path: Path | None = None
        for group, candidate in task_roots.items():
            if candidate.exists():
                src_group = group
                src_path = candidate
                break

        if src_path is None:
            if done_path.exists():
                existing_payload = _load_yaml(done_path)
                metadata = existing_payload.get("metadata", {})
                metadata_completed_at = (
                    metadata.get("completed_at") if isinstance(metadata, dict) else None
                )
                if not existing_payload.get("completed_at") and metadata_completed_at:
                    existing_payload["completed_at"] = metadata_completed_at
                    write_yaml_atomic(done_path, existing_payload)
                return existing_payload
            raise ValueError(f"task not found in active/planned/done: {task_id}")

        payload = _load_yaml(src_path)
        payload["status"] = "done"
        payload["completed_at"] = timestamp
        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["completed_at"] = timestamp
            metadata["completed_via"] = "omo task done"
            metadata["completion_actor"] = actor
            if source_ref:
                metadata["completion_source_ref"] = source_ref

        errors = validate_task_data(payload, group="done")
        if errors:
            raise ValueError("invalid completed task: " + "; ".join(errors))

        write_yaml_atomic(done_path, payload)
        src_path.unlink()

        artifact = {
            "kind": "task_completed",
            "task_id": task_id,
            "source_group": src_group,
            "task_ref_before": f".omo/tasks/{src_group}/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/done/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "completed_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-done-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-done:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} from={src_group} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_complete_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "source_group": src_group},
        )
        return payload


def update_done_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"
    if not task_path.exists():
        raise ValueError(f"done task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "done_task_evidence_paths_updated",
            "task_ref": f".omo/tasks/done/{task_id}.yaml",
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-refresh-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-refresh:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_done_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)


def update_planned_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Add evidence_paths to a planned/active task (未归档, done 前补 evidence).

    解决归档 gap: done 需 evidence, refresh-evidence 只查 done/, planned 无加 evidence 命令.
    """
    timestamp = now or _utc_now()
    task_path: Path | None = None
    for sub in ("planned", "active"):
        candidate = omo_dir / "tasks" / sub / f"{task_id}.yaml"
        if candidate.exists():
            task_path = candidate
            break
    if task_path is None:
        raise ValueError(f"planned/active task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_evidence_paths_added",
            "task_ref": str(task_path.relative_to(omo_dir)),
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-add-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-add:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_update_planned_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir)),
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir.parent)),
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)


def promote_task_to_active(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    handoff_ref: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
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
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
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
            artifact_ref=f".omo/_delivery/ingress/tasks/{artifact_path.name}",
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
                artifact_ref=f".omo/_delivery/ingress/tasks/{task_id}-approval-repair-{_timestamp_slug(timestamp)}.yaml"
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
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
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
