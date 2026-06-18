from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from omo.omo_audit import record as record_audit
from omo.omo_io import AppendOnlyLog, fcntl_lock, write_yaml_atomic
from omo.omo_io_schemas import OmoTrailRecord
from omo.omo_task_schema import validate_task_data


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _delivery_root(omo_dir: Path) -> Path:
    return omo_dir / "_delivery" / "ingress"


def _audit_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-audit.jsonl"


def _trail_log_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress-trail.jsonl"


def _lock_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "ingress.lock"


def _registry_path(omo_dir: Path) -> Path:
    return _delivery_root(omo_dir) / "registry.yaml"


def _load_registry(omo_dir: Path) -> dict[str, Any]:
    path = _registry_path(omo_dir)
    if not path.exists():
        return {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {"by_id": {}, "by_source_ref": {}},
        }
    data = _load_yaml(path)
    for key in ("goals", "tasks", "debts"):
        data.setdefault(key, {})
        data[key].setdefault("by_id", {})
        data[key].setdefault("by_source_ref", {})
    return data


def _write_registry(omo_dir: Path, registry: dict[str, Any]) -> None:
    write_yaml_atomic(_registry_path(omo_dir), registry)


def _goal_fingerprint(
    *,
    goal_id: str,
    title: str,
    description: str,
    ingress_plane: str,
    source_ref: str,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "id": goal_id,
        "title": title,
        "desc": description,
        "ingress_plane": ingress_plane,
        "source_ref": source_ref,
    }
    if extra_fields:
        payload["extra_fields"] = deepcopy(extra_fields)
    return payload


def _goal_existing_fingerprint(existing: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": existing.get("id"),
        "title": existing.get("title", ""),
        "desc": existing.get("desc", ""),
        "ingress_plane": existing.get("ingress_plane", ""),
        "source_ref": existing.get("source_ref", ""),
    }
    extra_fields = {
        key: deepcopy(value)
        for key, value in existing.items()
        if key
        not in {
            "id",
            "title",
            "desc",
            "progress",
            "status",
            "tasks",
            "ingress_plane",
            "source_ref",
            "created_at",
        }
    }
    if extra_fields:
        payload["extra_fields"] = extra_fields
    return payload


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


def _register_ingress(
    registry: dict[str, Any],
    *,
    kind: str,
    item_id: str,
    source_ref: str,
    artifact_ref: str,
    fingerprint: dict[str, Any],
    created_at: str,
) -> None:
    bucket = registry[kind]
    bucket["by_id"][item_id] = {
        "source_ref": source_ref,
        "artifact_ref": artifact_ref,
        "fingerprint": deepcopy(fingerprint),
        "created_at": created_at,
    }
    if source_ref:
        bucket["by_source_ref"][source_ref] = item_id


def _resolve_existing_goal(omo_dir: Path, goal_id: str) -> dict[str, Any] | None:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        return None
    payload = _load_yaml(goal_file)
    for goal in payload.get("goals", []):
        if goal.get("id") == goal_id:
            return goal
    return None


def _record_trail(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    parent_step_id: str,
) -> None:
    trail_record = OmoTrailRecord(
        ts=_utc_now(),
        actor=actor,
        action=action,
        target=target,
        status="ok",
        duration_ms=0,
        parent_step_id=parent_step_id,
    )
    AppendOnlyLog(_trail_log_path(omo_dir)).append(
        trail_record.model_dump(), schema=OmoTrailRecord, sort_keys=True
    )


def create_goal(
    omo_dir: Path,
    *,
    goal_id: str,
    title: str,
    description: str,
    ingress_plane: str,
    source_ref: str = "",
    extra_fields: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        raise FileNotFoundError(f"missing goals/current.yaml: {goal_file}")

    timestamp = now or _utc_now()
    fingerprint = _goal_fingerprint(
        goal_id=goal_id,
        title=title,
        description=description,
        ingress_plane=ingress_plane,
        source_ref=source_ref,
        extra_fields=extra_fields,
    )
    artifact_ref = f".omo/_delivery/ingress/goals/{goal_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        existing_goal = _resolve_existing_goal(omo_dir, goal_id)

        if source_ref:
            mapped_goal_id = registry["goals"]["by_source_ref"].get(source_ref)
            if mapped_goal_id and mapped_goal_id != goal_id:
                raise ValueError(
                    f"source_ref already mapped to different goal: {source_ref} -> {mapped_goal_id}"
                )

        if existing_goal is not None:
            existing_fingerprint = _goal_existing_fingerprint(existing_goal)
            if existing_fingerprint == fingerprint:
                _register_ingress(
                    registry,
                    kind="goals",
                    item_id=goal_id,
                    source_ref=source_ref,
                    artifact_ref=artifact_ref,
                    fingerprint=fingerprint,
                    created_at=str(existing_goal.get("created_at", timestamp)),
                )
                _write_registry(omo_dir, registry)
                return existing_goal
            raise ValueError(f"goal already exists with different payload: {goal_id}")

        payload = _load_yaml(goal_file)
        goals = payload.get("goals", [])
        new_goal: dict[str, Any] = {
            "id": goal_id,
            "title": title,
            "desc": description,
            "progress": 0.0,
            "status": "pending",
            "tasks": [],
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        if extra_fields:
            new_goal.update(deepcopy(extra_fields))

        goals.append(new_goal)
        payload["goals"] = goals
        write_yaml_atomic(goal_file, payload)

        artifact = {
            "kind": "goal_created",
            "goal_id": goal_id,
            "title": title,
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
            "goal_ref": ".omo/goals/current.yaml",
        }
        artifact_path = _delivery_root(omo_dir) / "goals" / f"{goal_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="goals",
            item_id=goal_id,
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:goal:{goal_id}:{timestamp}"
        details = (
            f"goal_id={goal_id} ingress_plane={ingress_plane} "
            f"source_ref={source_ref or '-'} artifact={artifact_path.relative_to(omo_dir.parent)}"
        )
        record_audit(
            action="ingress_create_goal",
            debt_id="",
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="create_goal",
            target=f".omo/goals/current.yaml#{goal_id}",
            parent_step_id=parent_step_id,
        )
        return new_goal


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
                        existing_payload.get("metadata", {}).get("created_at", timestamp)
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
        return payload


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
            mapped_debt_id = registry["debts"]["by_source_ref"].get(effective_source_ref)
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
            payload.get("lifecycle_state") or existing_payload.get("lifecycle_state") or "identified"
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
        debt_registry = _load_yaml(debt_registry_path) if debt_registry_path.exists() else {"version": 1}
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
