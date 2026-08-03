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
    _mutation_log_path,
    _registry_path,
    _timestamp_slug,
    _trail_log_path,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import AppendOnlyLog, fcntl_lock, write_yaml_atomic
from omo.omo_io_schemas import OmoTrailRecord


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
        status="ok",  # type: ignore[reportArgumentType]
        duration_ms=0,
        parent_step_id=parent_step_id,
    )
    AppendOnlyLog(_trail_log_path(omo_dir)).append(
        trail_record.model_dump(), schema=OmoTrailRecord, sort_keys=True
    )


def _load_registry(omo_dir: Path) -> dict[str, Any]:
    path = _registry_path(omo_dir)
    if not path.exists():
        return {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {"by_id": {}, "by_source_ref": {}},
            "capabilities": {"by_id": {}, "by_source_ref": {}},
        }
    data = _load_yaml(path)
    for key in ("goals", "tasks", "debts", "capabilities"):
        data.setdefault(key, {})
        data[key].setdefault("by_id", {})
        data[key].setdefault("by_source_ref", {})
    return data


def _write_registry(omo_dir: Path, registry: dict[str, Any]) -> None:
    write_yaml_atomic(_registry_path(omo_dir), registry)


def _record_mutation(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    artifact_ref: str,
    source_ref: str,
    broker_ref: str = "projects/omo/src/omo/omo_ingress.py",
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    record: dict[str, Any] = {
        "created_at": created_at or _utc_now(),
        "actor": actor,
        "action": action,
        "target": target,
        "artifact_ref": artifact_ref,
        "source_ref": source_ref,
        "broker_ref": broker_ref,
        "result": "committed",
    }
    if extra:
        record.update(deepcopy(extra))
    AppendOnlyLog(_mutation_log_path(omo_dir)).append(record, sort_keys=False)


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
            f"artifact={_workspace_relative(artifact_path)}"
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
            artifact_ref=f"runtime/omo/_delivery/ingress/state/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"updated_fields": sorted(updates.keys())},
        )
        return deepcopy(payload)


# Lazy re-exports for the historical omo.omo_ingress public API.
# Sibling domain modules (omo_ingress_doc, omo_ingress_task_lifecycle, etc.)
# contain the actual implementations; this __getattr__ keeps the public
# surface intact while breaking the cycle that would arise from a static
# `from omo.omo_ingress_doc import X` at module load.
_RE_EXPORTS: dict[str, str] = {
    "_load_registry": "omo_metacognition",
    "_record_mutation": "omo_ingress_registry_writes",
    "_record_trail": "omo_ingress_registry_writes",
    "_register_ingress": "omo_ingress",
    "_write_registry": "omo_ingress",
    "archive_done_task": "omo_ingress_task_archive",
    "complete_task": "omo_ingress_task_lifecycle",
    "create_audit_report": "omo_ingress_doc",
    "create_blocked_task": "omo_ingress_task_lifecycle",
    "create_goal": "omo_ingress_goal",
    "create_knowledge_doc": "omo_ingress_doc",
    "create_planned_task": "omo_ingress_task_lifecycle",
    "create_skill_manifest": "omo_ingress_registry_writes",
    "create_standard_doc": "omo_ingress_doc",
    "execute_controlled_task": "omo_ingress_task_lifecycle",
    "get_controlled_process_status": "omo_ingress_task_lifecycle",
    "normalize_legacy_planned_task": "omo_ingress_task_archive",
    "promote_task_to_active": "omo_ingress_task_promotion",
    "reconcile_goals": "omo_ingress_goal",
    "record_task_consensus": "omo_ingress_task_lifecycle",
    "record_task_contract_request": "omo_ingress_task_contract",
    "remove_debt_item": "omo_ingress_debt",
    "repair_task_promotion_approval": "omo_ingress_task_promotion",
    "request_task_promotion_approval": "omo_ingress_task_promotion",
    "restart_controlled_task": "omo_ingress_task_lifecycle",
    "revert_task_to_planned": "omo_ingress_task_promotion",
    "route_self_evolution_to_remediation": "omo_ingress_task_contract",
    "start_controlled_task": "omo_ingress_task_lifecycle",
    "stop_controlled_task": "omo_ingress_task_lifecycle",
    "update_done_task_evidence_paths": "omo_ingress_task_lifecycle",
    "update_goal_progress": "omo_ingress_goal",
    "update_governance_overlay_state": "omo_ingress_registry_writes",
    "update_planned_task_evidence_paths": "omo_ingress_task_lifecycle",
    "upsert_debt_item": "omo_ingress_debt",
    "write_capability_registry_bundle": "omo_ingress_registry_writes",
    "write_discovery_registry": "omo_ingress_registry_writes",
    "write_manual_capabilities": "omo_ingress_registry_writes",
    "write_system_projection_fields": "omo_ingress",
    "write_task_center_control_decision": "omo_ingress_registry_writes",
    "write_task_center_freshness": "omo_ingress_registry_writes",
    "write_usage_accounting": "omo_ingress_registry_writes",
    "yield_task_to_planned": "omo_ingress_task_archive",
}


def __getattr__(name: str):
    module = _RE_EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    mod = import_module(f"omo.{module}")
    value = getattr(mod, name)
    globals()[name] = value  # cache
    return value


# Eagerly resolve all re-exported syms so that sibling modules
# (`from omo.omo_ingress import _record_trail` style) succeed at first use.
# This avoids the cycle: omo.ingress loads, then each re-export __getattr__
# runs once, which triggers the sibling module's import (no cycle since
# omo.ingress is now fully loaded).
for _sym in list(_RE_EXPORTS.keys()):
    globals().get(_sym)  # noqa: PLE1117  trigger __getattr__

__all__ = sorted(_RE_EXPORTS)


# --- Post-load rebind hook: omo.ingress_doc, _task_lifecycle, etc. captured
# our private helpers at module load via sys.modules lookup that returned a
# partial omo.omo_ingress (cycle). After our full body runs, walk all
# loaded omo.ingress_* siblings and inject the helper symbols directly into
# their module dicts so function-local LOAD_GLOBAL resolves them.
import sys as _sys


def _rebind_siblings() -> None:
    _helpers = (
        "_record_trail",
        "_record_mutation",
        "_load_registry",
        "_register_ingress",
        "_write_registry",
    )
    for _mod_name, _mod in list(_sys.modules.items()):
        if _mod is None:
            continue
        if not (
            _mod_name == "omo.omo_ingress"
            or _mod_name.startswith("omo.omo_ingress_")
            or _mod_name == "omo.omo_ingress_paths"
        ):
            continue
        for _h in _helpers:
            if _h in globals() and _h not in _mod.__dict__:
                _mod.__dict__[_h] = globals()[_h]


_rebind_siblings()
