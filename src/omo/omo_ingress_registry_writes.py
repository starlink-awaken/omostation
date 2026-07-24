"""omo_ingress registry 写入 (从 God Module 拆出, SRP · P60+ 第六步前 4).

write_capability_registry_bundle / write_manual_capabilities /
create_skill_manifest / write_discovery_registry.
写 .omo/capabilities/* + .omo/_truth/task-center/* + delivery artifacts.
依赖 paths + registry (_load_registry/_write_registry/_register_ingress/_record_mutation)
     + trail (_record_trail) + omo_io + omo_audit — 无循环.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_ingress_paths import (
    _audit_log_path,
    _delivery_root,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic


def write_capability_registry_bundle(
    omo_dir: Path,
    *,
    bundle: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import (
        _load_registry,
        _record_mutation,
        _record_trail,
        _register_ingress,
        _write_registry,
    )

    timestamp = now or _utc_now()
    capabilities_dir = omo_dir / "capabilities"
    index_content = str(bundle["index_content"])
    registries = deepcopy(bundle.get("registries") or {})
    if not isinstance(registries, dict) or not registries:
        raise ValueError("capability registries missing")
    artifact_ref = f"runtime/omo/_delivery/ingress/capabilities/bundle-{_timestamp_slug(timestamp)}.yaml"
    fingerprint = {
        "kind": "bundle",
        "registry_files": sorted(registries.keys()),
        "source_ref": source_ref,
    }

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        capabilities_dir.mkdir(parents=True, exist_ok=True)
        write_text_atomic(capabilities_dir / "INDEX.md", index_content)
        registry_refs: list[str] = [".omo/capabilities/INDEX.md"]
        for filename, payload in sorted(registries.items()):
            if not filename.endswith(".yaml"):
                raise ValueError(f"invalid capability registry filename: {filename}")
            write_yaml_atomic(capabilities_dir / filename, payload)
            registry_refs.append(f".omo/capabilities/{filename}")
        artifact = {
            "kind": "capability_registry_bundle_written",
            "capability_registry_id": "bundle",
            "registry_refs": registry_refs,
            "ingress_plane": "projects/omo",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "capabilities"
            / f"bundle-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="capabilities",
            item_id="bundle",
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)
        parent_step_id = f"ingress:capability-bundle:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"registry_count={len(registry_refs)} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_write_capability_registry_bundle",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_capability_registry_bundle",
            target=".omo/capabilities/",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_capability_registry_bundle",
            target=".omo/capabilities/",
            artifact_ref=artifact_ref,
            source_ref=source_ref,
            created_at=timestamp,
            extra={"registry_refs": registry_refs},
        )
        return artifact


def write_manual_capabilities(
    omo_dir: Path,
    *,
    payload: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import (
        _load_registry,
        _record_mutation,
        _record_trail,
        _register_ingress,
        _write_registry,
    )

    timestamp = now or _utc_now()
    registry_path = omo_dir / "capabilities" / "manual-capabilities.yaml"
    artifact_ref = f"runtime/omo/_delivery/ingress/capabilities/manual-capabilities-{_timestamp_slug(timestamp)}.yaml"
    fingerprint = {
        "kind": "manual-capabilities",
        "capability_count": len(payload.get("capabilities", []))
        if isinstance(payload, dict)
        else 0,
        "source_ref": source_ref,
    }

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)
        write_yaml_atomic(registry_path, payload)
        artifact = {
            "kind": "manual_capabilities_written",
            "capability_registry_id": "manual-capabilities",
            "registry_ref": ".omo/capabilities/manual-capabilities.yaml",
            "ingress_plane": "projects/omo",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "capabilities"
            / f"manual-capabilities-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="capabilities",
            item_id="manual-capabilities",
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)
        parent_step_id = f"ingress:manual-capabilities:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_write_manual_capabilities",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_manual_capabilities",
            target=".omo/capabilities/manual-capabilities.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_manual_capabilities",
            target=".omo/capabilities/manual-capabilities.yaml",
            artifact_ref=artifact_ref,
            source_ref=source_ref,
            created_at=timestamp,
            extra={
                "capability_count": len(payload.get("capabilities", []))
                if isinstance(payload, dict)
                else 0
            },
        )
        return deepcopy(payload)


def create_skill_manifest(
    omo_dir: Path,
    *,
    manifest: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    skill_id = str(manifest["id"])
    timestamp = now or _utc_now()
    manifest_path = omo_dir / "_truth" / "task-center" / "skills" / f"{skill_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(manifest_path, manifest)
        artifact = {
            "kind": "skill_manifest_written",
            "skill_id": skill_id,
            "manifest_ref": f".omo/_truth/task-center/skills/{skill_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir) / "task-center" / "skills" / f"{skill_id}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:skill-manifest:{skill_id}:{timestamp}"
        details = (
            f"skill_id={skill_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_skill_manifest",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_skill_manifest",
            target=f".omo/_truth/task-center/skills/{skill_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_skill_manifest",
            target=f".omo/_truth/task-center/skills/{skill_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/task-center/skills/{skill_id}.yaml",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"skill_id": skill_id},
        )
        return deepcopy(manifest)


def write_discovery_registry(
    omo_dir: Path,
    *,
    registry: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    registry_path = omo_dir / "_truth" / "task-center" / "discovery-registry.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(registry_path, registry)
        artifact = {
            "kind": "discovery_registry_written",
            "registry_ref": ".omo/_truth/task-center/discovery-registry.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / "discovery"
            / f"discovery-registry-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:discovery-registry:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_write_discovery_registry",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_discovery_registry",
            target=".omo/_truth/task-center/discovery-registry.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_discovery_registry",
            target=".omo/_truth/task-center/discovery-registry.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/task-center/discovery/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return deepcopy(registry)


def write_usage_accounting(
    omo_dir: Path,
    *,
    registry: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    registry_path = omo_dir / "_truth" / "task-center" / "usage-accounting.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(registry_path, registry)
        artifact = {
            "kind": "task_center_usage_accounting_written",
            "registry_ref": ".omo/_truth/task-center/usage-accounting.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"usage-accounting-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:usage-accounting:{timestamp}"
        details = (
            f"actor={actor} registry_ref=.omo/_truth/task-center/usage-accounting.yaml "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_write_usage_accounting",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_usage_accounting",
            target=".omo/_truth/task-center/usage-accounting.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_usage_accounting",
            target=".omo/_truth/task-center/usage-accounting.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/task-center/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return artifact


def write_task_center_freshness(
    omo_dir: Path,
    *,
    report: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    report_path = omo_dir / "_delivery" / "task-center" / "freshness" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(report_path, report)
        artifact = {
            "kind": "task_center_freshness_written",
            "report_ref": ".omo/_delivery/task-center/freshness/current.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"freshness-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:freshness:{timestamp}"
        details = (
            f"actor={actor} report_ref=.omo/_delivery/task-center/freshness/current.yaml "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_write_task_center_freshness",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_task_center_freshness",
            target=".omo/_delivery/task-center/freshness/current.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_task_center_freshness",
            target=".omo/_delivery/task-center/freshness/current.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/task-center/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
        )
        return artifact


def write_task_center_control_decision(
    omo_dir: Path,
    *,
    artifact: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    artifact_path = omo_dir / "_delivery" / "task-center" / "control" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(artifact_path, artifact)
        delivery_artifact = {
            "kind": "task_center_control_decision_written",
            "decision_ref": ".omo/_delivery/task-center/control/current.yaml",
            "decision": artifact.get("decision"),
            "actor": actor,
            "source_ref": source_ref,
            "written_at": timestamp,
        }
        ingress_artifact_path = (
            _delivery_root(omo_dir)
            / "task-center"
            / f"control-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(ingress_artifact_path, delivery_artifact)
        parent_step_id = f"ingress:control:{timestamp}"
        details = (
            f"actor={actor} decision={artifact.get('decision')} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(ingress_artifact_path)}"
        )
        record_audit(
            action="ingress_write_task_center_control_decision",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="write_task_center_control_decision",
            target=".omo/_delivery/task-center/control/current.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="write_task_center_control_decision",
            target=".omo/_delivery/task-center/control/current.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/task-center/{ingress_artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"decision": artifact.get("decision")},
        )
        return delivery_artifact


def update_governance_overlay_state(
    omo_dir: Path,
    *,
    roadmap: dict[str, Any],
    actor: str,
    control: dict[str, Any] | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    roadmap_path = omo_dir / "_truth" / "governance-overlay" / "roadmap.yaml"
    control_path = omo_dir / "_control" / "governance-overlay" / "current.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        write_yaml_atomic(roadmap_path, roadmap)
        if control is not None:
            write_yaml_atomic(control_path, control)
        artifact = {
            "kind": "governance_overlay_state_updated",
            "roadmap_ref": ".omo/_truth/governance-overlay/roadmap.yaml",
            "control_ref": ".omo/_control/governance-overlay/current.yaml"
            if control is not None
            else None,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "governance-overlay"
            / f"state-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:governance-overlay:{timestamp}"
        details = (
            f"actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_update_governance_overlay_state",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_governance_overlay_state",
            target=".omo/_truth/governance-overlay/roadmap.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_governance_overlay_state",
            target=".omo/_truth/governance-overlay/roadmap.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/governance-overlay/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"control_written": control is not None},
        )
        return artifact


def apply_baseline_patches(
    omo_dir: Path,
    *,
    patches: dict[str, str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_trail

    """Broker: patch dependency-baseline.yaml 的 mismatched baseline 值 (C2 方案 C).

    gen-dependency-baseline 算 drift (业务), 本函数合规应用 patch
    (write_text_atomic + audit + trail). 文本 patch (保留 yaml 格式/注释),
    只改 patches 里 name 的 baseline 值. 路径 src/omo/ 豁免 direct_omo_io.
    """
    import re

    timestamp = now or _utc_now()
    baseline_path = omo_dir / "_truth" / "registry" / "dependency-baseline.yaml"
    if not baseline_path.is_file():
        raise FileNotFoundError(f"dependency-baseline.yaml not found: {baseline_path}")
    with fcntl_lock(_lock_path(omo_dir)):
        text = baseline_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        applied: list[dict[str, str]] = []
        i = 0
        while i < len(lines):
            m = re.match(r"(\s*)-\s*name:\s*(\S+)", lines[i])
            if m and m.group(2).lower() in patches:
                new_b = patches[m.group(2).lower()]
                for j in range(i + 1, min(i + 6, len(lines))):
                    bm = re.match(r"(\s*baseline:\s*)(.*)", lines[j])
                    if bm:
                        old = bm.group(2).strip().strip("'\"")
                        lines[j] = f"{bm.group(1)}'{new_b}'"
                        applied.append({"name": m.group(2), "old": old, "new": new_b})
                        i = j
                        break
            i += 1
        if not applied:
            return {
                "applied": 0,
                "patches": [],
                "note": "no patch targets matched in baseline yaml",
            }
        write_text_atomic(baseline_path, "\n".join(lines))
        record_audit(
            action="apply_dependency_baseline_patches",
            debt_id="",
            actor=actor,
            details={
                "applied": applied,
                "source_ref": source_ref,
                "timestamp": timestamp,
            },
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="apply_dependency_baseline_patches",
            target="runtime/omo/_truth/registry/dependency-baseline.yaml",
            parent_step_id="dependency-baseline",
        )
    return {"applied": len(applied), "patches": applied, "source_ref": source_ref}
