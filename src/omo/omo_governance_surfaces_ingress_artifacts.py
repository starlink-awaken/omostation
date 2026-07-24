"""P106 refactor: omo_governance_surfaces ingress-artifacts 子模块 (从 omo_governance_surfaces.py 提取).

业务:
  - _check_ingress_artifacts (L487-632, 145L):
    校验 ingress registry 指向的 artifact 文件存在且元数据与 registry 对齐
    - 4 类 artifact: goal/task/debt/capability
    - 路径存在性 + frontmatter 完整性
    - 反向映射 (artifact_ref ↔ registry entry)

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, 见 P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)

向后兼容 (P100-P105 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_ingress_artifacts import (...)` re-export,
  保持 `_check_ingress_artifacts()` 调用点 (P102 cmd_lint_ingress_artifacts wrapper) 不破.

P106 收益:
  - 与 task_policy 子模块合拆, omo_governance_surfaces.py 1022L → ~786L
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_ingress_paths import _registry_path
from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P106): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


INGRESS_ARTIFACT_RULES: dict[str, dict[str, object]] = {
    "goals": {
        "kind": "goal_created",
        "id_field": "goal_id",
        "target_field": "goal_ref",
        "target_ref": ".omo/goals/current.yaml",
    },
    "tasks": {
        "kind": "planned_task_created",
        "id_field": "task_id",
        "target_field": "task_ref",
        "target_prefix": ".omo/tasks/",
    },
    "debts": {
        "kind": "debt_upserted",
        "id_field": "debt_id",
        "target_field": "debt_ref",
        "target_prefix": ".omo/debt/items/",
    },
    "capabilities": {
        "kind_by_id": {
            "bundle": "capability_registry_bundle_written",
            "manual-capabilities": "manual_capabilities_written",
        },
        "id_field": "capability_registry_id",
        "target_field_by_id": {
            "bundle": "registry_refs",
            "manual-capabilities": "registry_ref",
        },
        "target_expected_by_id": {
            "bundle": [
                ".omo/capabilities/INDEX.md",
                ".omo/capabilities/projects-capabilities.yaml",
                ".omo/capabilities/sharedwork-sample.yaml",
                ".omo/capabilities/system-packages.yaml",
                ".omo/capabilities/agent-clis.yaml",
            ],
            "manual-capabilities": ".omo/capabilities/manual-capabilities.yaml",
        },
    },
}


def _check_ingress_artifacts(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    omo_dir = workspace_root / ".omo"
    registry_path = _registry_path(omo_dir)
    if not registry_path.exists():
        # Runtime cache absent on fresh clones is ok; missing registry under an
        # initialized ingress directory is a real issue.
        if not registry_path.parent.exists():
            return {
                "exists": False,
                "path": str(registry_path),
                "goal_artifacts": 0,
                "task_artifacts": 0,
                "debt_artifacts": 0,
                "capability_artifacts": 0,
            }, []
        return {
            "exists": False,
            "path": str(registry_path),
            "goal_artifacts": 0,
            "task_artifacts": 0,
            "debt_artifacts": 0,
            "capability_artifacts": 0,
        }, [
            f"ingress artifacts: required registry missing: {registry_path.relative_to(workspace_root)}"
        ]

    registry = _load_yaml(registry_path)
    issues: list[str] = []
    summary = {
        "exists": True,
        "path": str(registry_path),
        "goal_artifacts": 0,
        "task_artifacts": 0,
        "debt_artifacts": 0,
        "capability_artifacts": 0,
    }

    for bucket_name, summary_key in (
        ("goals", "goal_artifacts"),
        ("tasks", "task_artifacts"),
        ("debts", "debt_artifacts"),
        ("capabilities", "capability_artifacts"),
    ):
        bucket = registry.get(bucket_name, {})
        by_id = bucket.get("by_id", {}) if isinstance(bucket, dict) else {}
        if not isinstance(by_id, dict):
            issues.append(
                f"ingress artifacts: {bucket_name}.by_id missing or not a mapping"
            )
            continue
        summary[summary_key] = len(by_id)
        rules = INGRESS_ARTIFACT_RULES[bucket_name]
        for item_id, meta in by_id.items():
            if not isinstance(meta, dict):
                issues.append(
                    f"ingress artifacts: {bucket_name}.by_id.{item_id} not a mapping"
                )
                continue
            artifact_ref = meta.get("artifact_ref")
            if not isinstance(artifact_ref, str) or not artifact_ref:
                issues.append(
                    f"ingress artifacts: {bucket_name}.by_id.{item_id} missing artifact_ref"
                )
                continue
            artifact_path = workspace_root / artifact_ref
            if not artifact_path.exists():
                issues.append(
                    f"ingress artifacts: artifact file missing for {bucket_name}.{item_id}: {artifact_ref}"
                )
                continue
            payload = _load_yaml(artifact_path)
            expected_kind = (
                (rules.get("kind_by_id") or {}).get(item_id)
                if isinstance(rules.get("kind_by_id"), dict)
                else rules.get("kind")
            ) or rules.get("kind")
            if payload.get("kind") != expected_kind:
                issues.append(
                    f"ingress artifacts: {artifact_ref} kind mismatch "
                    f"(expected {expected_kind}, got {payload.get('kind')!r})"
                )
            if payload.get(rules["id_field"]) != item_id:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {rules['id_field']} mismatch for {item_id}"
                )
            if not payload.get("created_at"):
                issues.append(f"ingress artifacts: {artifact_ref} missing created_at")
            if payload.get("source_ref", "") != meta.get("source_ref", ""):
                issues.append(
                    f"ingress artifacts: {artifact_ref} source_ref mismatch for {item_id}"
                )
            if not payload.get("ingress_plane"):
                issues.append(
                    f"ingress artifacts: {artifact_ref} missing ingress_plane"
                )
            target_field = (
                (rules.get("target_field_by_id") or {}).get(item_id)
                if isinstance(rules.get("target_field_by_id"), dict)
                else rules.get("target_field")
            )
            if not isinstance(target_field, str) or not target_field:
                issues.append(
                    f"ingress artifacts: {bucket_name}.{item_id} missing target_field rule"
                )
                continue
            target_value = payload.get(target_field)
            expected_target = (
                (rules.get("target_expected_by_id") or {}).get(item_id)
                if isinstance(rules.get("target_expected_by_id"), dict)
                else rules.get("target_ref")
            )
            if isinstance(expected_target, list):
                if not isinstance(target_value, list) or not target_value:
                    issues.append(
                        f"ingress artifacts: {artifact_ref} missing {target_field}"
                    )
                else:
                    missing_refs = [
                        ref for ref in expected_target if ref not in target_value
                    ]
                    if missing_refs:
                        issues.append(
                            f"ingress artifacts: {artifact_ref} {target_field} missing refs {missing_refs}"
                        )
            elif not isinstance(target_value, str) or not target_value:
                issues.append(
                    f"ingress artifacts: {artifact_ref} missing {target_field}"
                )
            elif "target_ref" in rules and target_value != rules["target_ref"]:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} mismatch "
                    f"(expected {rules['target_ref']}, got {target_value!r})"
                )
            elif expected_target and target_value != expected_target:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} mismatch "
                    f"(expected {expected_target}, got {target_value!r})"
                )
            elif "target_prefix" in rules and not target_value.startswith(
                str(rules["target_prefix"])
            ):
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} must start with {rules['target_prefix']}"
                )

    return summary, issues


# P104 R1: snapshots 子模块 (extracted 553L from omo_governance_surfaces.py)
# Re-export 保持向后兼容 (内部 call sites: L1157, L1223, L1636)
from .omo_governance_surfaces_snapshots import (
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
)
