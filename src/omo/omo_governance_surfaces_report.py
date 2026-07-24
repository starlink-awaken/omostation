"""P110-B: omo_governance_surfaces_report 子模块 (从 omo_governance_surfaces.py 提取).

ADR-0109 P110-B: 顶层 report 函数 (172L) 拆出, omo_governance_surfaces.py
443→~270L (<300L ideal 阈值).

业务 (1 function):
  - build_governance_surfaces_report (L245-417, 172L):
    跨多 check + report builder 调用的顶层 aggregator
    - 校验 .omo 结构
    - 调用 7 个 check_* registry (cache/mutation/ingress/...)
    - 调用 8 个 has_*_gate (gate 检查)
    - 调用 1 个 _check_goals_runtime_entry
    - 调用 1 个 _read_c2g_governance_refs
    - 调用 1 个 _candidate_roots
    - 调用 1 个 resolve_governance_workspace_root
    - 输出综合 report

模块依赖:
  - json, sys, argparse, ast (stdlib)
  - pathlib (Path)
  - .omo_shared (load_yaml_required)
  - .omo_task_policy (task_policy_registry_snapshot)
  - .omo_governance_surfaces_snapshots (4 helpers + 2 snapshot funcs)
  - .omo_governance_surfaces_ingress (2 funcs)
  - .omo_governance_surfaces_ingress_artifacts (1 func)
  - .omo_governance_surfaces_mutation_surface (1 func)
  - .omo_governance_surfaces_internal_write_profiles (1 func)
  - .omo_governance_surfaces_state_plane (1 func)
  - .omo_governance_surfaces_c2g_boundary (1 func)
  - .omo_governance_surfaces_task_policy (none, not called from build_report)
  - inline _load_yaml (P105 范式, 避免 circular import)

P107 cross-sibling import 范式应用: child → siblings, 无 circular 风险.

向后兼容 (P88-P109 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_report import build_governance_surfaces_report` re-export,
  保持 `from omo.omo_governance_surfaces import build_governance_surfaces_report` 不破.

P110-B 收益:
  - omo_governance_surfaces.py 443→~270L (理想值 <300L)
  - 8 子模块架构完成 (P104-P110 累计 9 子模块拆分)
  - build_report 作为顶层 aggregator, 独立可单测
"""

from __future__ import annotations

from pathlib import Path

# ingress / ingress_artifacts / mutation_surface / internal_write_profiles / state_plane
# (each is a sibling of report, has no dependency on report)
from omo.omo_governance_surfaces_ingress import (
    _check_ingress_registry,
)
from omo.omo_governance_surfaces_ingress_artifacts import _check_ingress_artifacts

# Cross-sibling imports (P107 范式: child → siblings, 无 circular 风险)
# snapshots: pure data, no further dependencies
from omo.omo_governance_surfaces_snapshots import (
    _worker_internal_write_profiles_snapshot,
)
from omo.omo_shared import load_yaml_required


# P105 范式: inline _load_yaml 避免 child → parent circular import
def _load_yaml(path):
    """Inline helper (P110-B): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def build_governance_surfaces_report(workspace_root: Path) -> dict[str, object]:
    from omo.omo_governance_surfaces import (
        _asset_ref_to_top_level,
        _check_c2g_omo_boundary,
        _check_goals_runtime_entry,
        _check_internal_write_profile_registry,
        _check_mutation_surface_registry,
        _check_state_plane_asset_registry,
        _check_task_policy_registry,
        _has_c2g_omo_boundary_gate,
        _has_direct_io_gate,
        _has_ingress_artifact_gate,
        _has_internal_write_profile_gate,
        _has_mutation_ledger_gate,
        _has_mutation_surface_gate,
        _has_state_plane_asset_gate,
        _has_task_policy_gate,
        _read_c2g_governance_refs,
        _top_level_entries,
    )

    omo_dir = workspace_root / ".omo"
    registry_path = omo_dir / "_truth" / "registry" / "omo-governance-surfaces.yaml"
    standard_path = omo_dir / "standards" / "omo-governance-surfaces.md"

    if not omo_dir.is_dir():
        raise FileNotFoundError(f".omo not found: {omo_dir}")
    if not registry_path.exists():
        raise FileNotFoundError(f"registry missing: {registry_path}")

    registry = _load_yaml(registry_path)

    # Runtime-generated top-level assets may be gitignored and absent on fresh clones.
    # They are still registered for schema/documentation purposes but are not enforced
    # by the top-level presence check.
    runtime_top_levels = {
        top
        for item in registry.get("assets", [])
        if item.get("runtime") and (top := _asset_ref_to_top_level(item.get("ref", "")))
    }

    registered_top_levels = sorted(
        {
            top
            for top in (
                _asset_ref_to_top_level(item.get("ref", ""))
                for item in registry.get("assets", [])
            )
            if top and top not in runtime_top_levels
        }
    )
    observed_top_levels = sorted(
        top for top in _top_level_entries(omo_dir) if top not in runtime_top_levels
    )

    missing_registered_roots = sorted(
        top for top in registered_top_levels if not (omo_dir / top).exists()
    )
    unregistered_top_levels = sorted(
        top for top in observed_top_levels if top not in registered_top_levels
    )
    constrained_present = sorted(
        item.get("ref", "")
        for item in registry.get("assets", [])
        if item.get("status") == "constrained"
        and (workspace_root / item.get("ref", "")).exists()
    )

    c2g_refs, c2g_issues = _read_c2g_governance_refs(workspace_root)
    expected_refs = [
        ".omo/standards/omo-governance-surfaces.md",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
    ]
    missing_c2g_refs = [ref for ref in expected_refs if ref not in c2g_refs]
    direct_io_gate_present = _has_direct_io_gate(workspace_root)
    task_policy_gate_present = _has_task_policy_gate(workspace_root)
    mutation_surface_gate_present = _has_mutation_surface_gate(workspace_root)
    internal_write_profile_gate_present = _has_internal_write_profile_gate(
        workspace_root
    )
    state_plane_asset_gate_present = _has_state_plane_asset_gate(workspace_root)
    c2g_omo_boundary_gate_present = _has_c2g_omo_boundary_gate(workspace_root)
    ingress_artifact_gate_present = _has_ingress_artifact_gate(workspace_root)
    mutation_ledger_gate_present = _has_mutation_ledger_gate(workspace_root)
    goals_runtime_entry, goals_runtime_entry_issues = _check_goals_runtime_entry(
        omo_dir
    )
    ingress_registry, ingress_registry_issues = _check_ingress_registry(workspace_root)
    ingress_artifacts, ingress_artifact_issues = _check_ingress_artifacts(
        workspace_root
    )
    task_policy_registry, task_policy_registry_issues = _check_task_policy_registry(
        workspace_root
    )
    c2g_omo_boundary, c2g_omo_boundary_issues = _check_c2g_omo_boundary(workspace_root)
    state_plane_asset_registry, state_plane_asset_registry_issues = (
        _check_state_plane_asset_registry(workspace_root)
    )
    mutation_surface_registry, mutation_surface_registry_issues = (
        _check_mutation_surface_registry(workspace_root)
    )
    internal_write_profile_registry, internal_write_profile_registry_issues = (
        _check_internal_write_profile_registry(workspace_root)
    )
    worker_internal_write_profiles = _worker_internal_write_profiles_snapshot()

    issues: list[str] = []
    if not standard_path.exists():
        issues.append("governance surfaces standard missing")
    issues.extend(
        f"unregistered top-level asset: {top}" for top in unregistered_top_levels
    )
    issues.extend(
        f"registered top-level asset missing on disk: {top}"
        for top in missing_registered_roots
    )
    issues.extend(
        f"c2g governance ref missing from task builder: {ref}"
        for ref in missing_c2g_refs
    )
    if not direct_io_gate_present:
        issues.append("pre-commit direct io gate missing: omo-direct-io-gate")
    if not task_policy_gate_present:
        issues.append("pre-commit task policy gate missing: omo-task-policy-gate")
    if not mutation_surface_gate_present:
        issues.append(
            "pre-commit mutation surface gate missing: omo-mutation-surface-gate"
        )
    if not internal_write_profile_gate_present:
        issues.append(
            "pre-commit internal write profile gate missing: "
            "omo-internal-write-profile-gate"
        )
    if not state_plane_asset_gate_present:
        issues.append(
            "pre-commit state plane asset gate missing: omo-state-plane-asset-gate"
        )
    if not c2g_omo_boundary_gate_present:
        issues.append(
            "pre-commit c2g/omo boundary gate missing: omo-c2g-omo-boundary-gate"
        )
    if not ingress_artifact_gate_present:
        issues.append(
            "pre-commit ingress artifact gate missing: omo-ingress-artifact-gate"
        )
    if not mutation_ledger_gate_present:
        issues.append(
            "pre-commit mutation ledger gate missing: omo-mutation-ledger-gate"
        )
    issues.extend(goals_runtime_entry_issues)
    issues.extend(c2g_issues)
    issues.extend(c2g_omo_boundary_issues)
    issues.extend(ingress_registry_issues)
    issues.extend(ingress_artifact_issues)
    issues.extend(task_policy_registry_issues)
    issues.extend(state_plane_asset_registry_issues)
    issues.extend(mutation_surface_registry_issues)
    issues.extend(internal_write_profile_registry_issues)

    warnings = [
        f"constrained legacy asset present: {ref}" for ref in constrained_present
    ]

    status = "ok"
    if issues:
        status = "error"
    elif warnings:
        status = "warn"

    return {
        "workspace_root": str(workspace_root),
        "omo_dir": str(omo_dir),
        "registry_path": str(registry_path),
        "standard_path": str(standard_path),
        "registered_top_levels": registered_top_levels,
        "observed_top_levels": observed_top_levels,
        "missing_registered_roots": missing_registered_roots,
        "unregistered_top_levels": unregistered_top_levels,
        "constrained_present": constrained_present,
        "nested_omo_present": (omo_dir / ".omo").exists(),
        "c2g_governance_refs": c2g_refs,
        "c2g_missing_governance_refs": missing_c2g_refs,
        "direct_io_gate_present": direct_io_gate_present,
        "task_policy_gate_present": task_policy_gate_present,
        "mutation_surface_gate_present": mutation_surface_gate_present,
        "internal_write_profile_gate_present": internal_write_profile_gate_present,
        "state_plane_asset_gate_present": state_plane_asset_gate_present,
        "c2g_omo_boundary_gate_present": c2g_omo_boundary_gate_present,
        "ingress_artifact_gate_present": ingress_artifact_gate_present,
        "mutation_ledger_gate_present": mutation_ledger_gate_present,
        "goals_runtime_entry": goals_runtime_entry,
        "c2g_omo_boundary": c2g_omo_boundary,
        "ingress_registry": ingress_registry,
        "ingress_artifacts": ingress_artifacts,
        "task_policy_registry": task_policy_registry,
        "state_plane_asset_registry": state_plane_asset_registry,
        "mutation_surface_registry": mutation_surface_registry,
        "internal_write_profile_registry": internal_write_profile_registry,
        "worker_internal_write_profiles": worker_internal_write_profiles,
        "issues": issues,
        "warnings": warnings,
        "status": status,
    }
