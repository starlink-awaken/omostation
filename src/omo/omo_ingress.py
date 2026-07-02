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
    _workspace_relative,
)
from omo.omo_ingress_registry import (
    _record_mutation,
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
from omo.omo_ingress_debt import (  # noqa: F401  (public re-export, 调用方 `from omo.omo_ingress import` 不变)
    remove_debt_item,
    upsert_debt_item,
)


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
