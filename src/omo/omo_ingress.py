from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


from omo.omo_audit import record as record_audit
from omo.omo_io import fcntl_lock, write_yaml_atomic
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
    archive_done_task,
    complete_task,
    create_blocked_task,
    create_planned_task,
    normalize_legacy_planned_task,
    promote_task_to_active,
    record_task_consensus,
    record_task_contract_request,
    repair_task_promotion_approval,
    request_task_promotion_approval,
    revert_task_to_planned,
    route_self_evolution_to_remediation,
    update_done_task_evidence_paths,
    update_planned_task_evidence_paths,
    yield_task_to_planned,
)


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
