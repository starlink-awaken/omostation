"""P110 refactor: omo_ingress_task_archive 子模块 (从 omo_ingress_task_lifecycle.py 提取).

业务 (3 functions):
  - yield_task_to_planned (L1171-1262, 92L)
  - archive_done_task (L1263-1346, 84L)
  - normalize_legacy_planned_task (L1347-1530, 184L, 最大单函数)

业务: task 收尾 + 归档 + 历史 planned task 规范化.

模块依赖: (同 promotion 子模块)

向后兼容 (P88-P109 模式):
  omo_ingress_task_lifecycle.py 通过 `from .omo_ingress_task_archive import (...)` re-export.

P110 关联: ADR-0104 (本 P110 ADR).
"""

from __future__ import annotations

from copy import deepcopy
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
from omo.omo_io import fcntl_lock, write_yaml_atomic
from omo.omo_task_schema import validate_task_data


def yield_task_to_planned(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    reason: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

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
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
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
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
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
    from omo.omo_ingress import _record_mutation, _record_trail

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
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
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
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
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
    from omo.omo_ingress import _record_mutation, _record_trail

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
                    f"artifact={_workspace_relative(artifact_path)}"
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
                artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
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
                f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
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
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "task_id": task_id,
                "legacy_status": original_status,
                "normalized_status": normalized["status"],
            },
        )
        return {"action": "normalized", "task": normalized}
