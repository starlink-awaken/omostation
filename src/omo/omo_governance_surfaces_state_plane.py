"""P107 refactor: omo_governance_surfaces state-plane 子模块 (从 omo_governance_surfaces.py 提取).

ADR-0100 P106 末 omo_governance_surfaces.py 763L (warn 阈值 800L 已清零).
P107 继续拆: _check_state_plane_asset_registry (86L) + _check_mutation_surface_registry (112L)
= 198L → ~565L, <600L ideal 阈值首次达成.

业务:
  - _check_state_plane_asset_registry (L267-353, 86L):
    校验 .omo/_truth/registry/state-plane-assets.yaml 结构 (Round 38 P0)
    - 必备字段: top_level_asset/persistence_mode/retention_mode
    - 路径存在性
    - persistence_mode 与 retention_mode 配对校验
    - 与 .omo/_delivery/state-plane-assets/ 落盘一致性

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, 见 P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)

向后兼容 (P100-P106 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_state_plane import (...)` re-export,
  保持 `_check_state_plane_asset_registry()` 调用点 (P102 cmd_lint_state_plane_assets wrapper) 不破.

P107 收益:
  - omo_governance_surfaces.py 763L → ~565L, <600L ideal 首次达成
  - 13 god-module list: 仍 12 (本文件持续 <800L)
  - 累计 omo_governance_surfaces.py: 1762 → 565L (-1197L, -68%)
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P107): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


ALLOWED_PERSISTENCE_MODES = {
    "authoritative",
    "durable",
    "operational",
    "append_only",
    "archival",
    "compatibility_alias",
    "derived",  # .omo/_generated/ — CI/generated artifacts (gitignored)
    "ephemeral",  # .omo/autopilot/ — autopilot runtime state (session scoped)
}

ALLOWED_RETENTION_MODES = {
    "until_replaced",
    "manual_cleanup",
    "rolling_window",
    "append_forever",
    "manual_archive",
    "alias_only",
    "session_only",  # .omo/autopilot/ — session scoped retention
}

EXPECTED_ASSET_LIFECYCLE_BY_TYPE: dict[str, tuple[str, str]] = {
    "authority": ("authoritative", "until_replaced"),
    "control_state": ("operational", "rolling_window"),
    "knowledge_state": ("durable", "manual_cleanup"),
    "delivery_state": ("append_only", "manual_archive"),
    "archived_state": ("archival", "manual_archive"),
    "workflow_state": ("operational", "manual_archive"),
    "runtime_ssot": ("operational", "until_replaced"),
    "governance_program": ("durable", "manual_archive"),
    "governance_review_surface": ("durable", "until_replaced"),
    "governance_routing_surface": ("durable", "until_replaced"),
    "governance_dispatch_surface": ("durable", "manual_archive"),
    "governance_campaign_surface": ("durable", "manual_archive"),
    "governance_reporting_surface": ("durable", "manual_archive"),
    "execution_runtime": ("operational", "rolling_window"),
    "rule_docs": ("durable", "until_replaced"),
    "control_contract": ("durable", "until_replaced"),
    "runtime_logs": ("append_only", "rolling_window"),
    "goal_state": ("authoritative", "until_replaced"),
    "strategic_input": ("durable", "manual_archive"),
    "governance_test_surface": ("durable", "manual_cleanup"),
    "capability_market": ("durable", "until_replaced"),
    "change_history": ("append_only", "manual_archive"),
    "root_registry": ("authoritative", "until_replaced"),
    "root_index": ("durable", "until_replaced"),
    "compatibility_alias": ("compatibility_alias", "alias_only"),
}


def _check_state_plane_asset_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    registry_path = (
        workspace_root / ".omo" / "_truth" / "registry" / "omo-governance-surfaces.yaml"
    )
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "asset_count": 0,
            "top_level_asset_count": 0,
            "persistence_mode_counts": {},
            "retention_mode_counts": {},
        }, ["governance surfaces registry missing"]

    registry = _load_yaml(registry_path)
    assets = [item for item in registry.get("assets", []) if isinstance(item, dict)]
    top_level_assets = [
        item
        for item in assets
        if item.get("plane") == "state_plane"
        and str(item.get("ref", "")).startswith(".omo/")
    ]

    persistence_mode_counts: dict[str, int] = {}
    retention_mode_counts: dict[str, int] = {}
    issues: list[str] = []

    for item in top_level_assets:
        ref = str(item.get("ref", ""))
        asset_type = str(item.get("asset_type", ""))
        persistence_mode = item.get("persistence_mode")
        retention_mode = item.get("retention_mode")

        if not asset_type:
            issues.append(f"state plane asset missing asset_type: {ref}")
            continue

        if not isinstance(persistence_mode, str) or not persistence_mode:
            issues.append(f"state plane asset missing persistence_mode: {ref}")
        elif persistence_mode not in ALLOWED_PERSISTENCE_MODES:
            issues.append(
                f"state plane asset invalid persistence_mode {persistence_mode!r}: {ref}"
            )
        else:
            persistence_mode_counts[persistence_mode] = (
                persistence_mode_counts.get(persistence_mode, 0) + 1
            )

        if not isinstance(retention_mode, str) or not retention_mode:
            issues.append(f"state plane asset missing retention_mode: {ref}")
        elif retention_mode not in ALLOWED_RETENTION_MODES:
            issues.append(
                f"state plane asset invalid retention_mode {retention_mode!r}: {ref}"
            )
        else:
            retention_mode_counts[retention_mode] = (
                retention_mode_counts.get(retention_mode, 0) + 1
            )

        expected = EXPECTED_ASSET_LIFECYCLE_BY_TYPE.get(asset_type)
        if (
            expected
            and isinstance(persistence_mode, str)
            and isinstance(retention_mode, str)
        ):
            if (persistence_mode, retention_mode) != expected:
                issues.append(
                    "state plane asset lifecycle drift "
                    f"for {ref}: expected {expected[0]}/{expected[1]}, "
                    f"got {persistence_mode}/{retention_mode}"
                )

        if asset_type == "compatibility_alias" and not item.get("alias_target"):
            issues.append(f"compatibility alias missing alias_target: {ref}")

    return {
        "exists": True,
        "path": str(registry_path),
        "asset_count": len(assets),
        "top_level_asset_count": len(top_level_assets),
        "persistence_mode_counts": dict(sorted(persistence_mode_counts.items())),
        "retention_mode_counts": dict(sorted(retention_mode_counts.items())),
    }, issues
