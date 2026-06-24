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
from omo.omo_io import fcntl_lock, write_yaml_atomic
from omo.omo_task_schema import validate_task_data
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
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
