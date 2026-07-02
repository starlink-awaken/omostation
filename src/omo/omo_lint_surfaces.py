"""P102 refactor: omo_lint surfaces 子模块 (从 omo_lint.py 提取).

P99 ADR-0093 规划 P100-P103 4 步拆解 (P101 D3 校正后顺序):
  P100 schemas 拆 (485L) ✓ done → 800L
  P101 yaml-bypass 拆 (76L) ✓ done → 731L
  P102 surfaces 拆 (148L) → 589L, <600L ideal 接近达成
  P103 mutation-ledger 拆 (57L) → 532L, <600L ideal 完整达成

6 个 governance-surface thin wrapper (Round 14+ P0 累积):
  - cmd_lint_ingress_registry       (L366-391, 26L): ingress registry 结构 + 反向映射
  - cmd_lint_mutation_surfaces      (L393-415, 23L): mutation surface truth registry
  - cmd_lint_internal_write_profiles(L417-439, 23L): worker internal write profile registry
  - cmd_lint_state_plane_assets     (L441-464, 24L): .omo 顶层资产持久化
  - cmd_lint_c2g_omo_boundary       (L466-485, 20L): c2g → omo 接入边界
  - cmd_lint_ingress_artifacts      (L487-512, 26L): ingress registry 指向 artifact 文件存在

所有 cmd 都是 thin wrapper: 从 omo.omo_governance_surfaces 导入核心 check 函数,
组装 workspace_root 后打印结果. 核心逻辑早已外置, 拆解是把 wrapper 集中收纳.

模块依赖: Path (stdlib) + omo.omo_governance_surfaces (内部 SSOT).

向后兼容 (P88/P100/P101 模式):
  omo_lint.py 通过 `from .omo_lint_surfaces import (...)` re-export,
  保持 `from omo.omo_lint import cmd_lint_mutation_surfaces` 等不破.
"""

from __future__ import annotations

from pathlib import Path


def cmd_lint_ingress_registry(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_ingress_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_registry(root)
    # registry 未创建 (runtime cache 缺, 如 CI fresh checkout) — 合法状态, 不阻断.
    # 结构/反向映射检查只在 registry 存在时才有意义.
    if not summary.get("exists"):
        print("✅ omo lint ingress-registry pass: registry not created yet (runtime cache absent)")
        return 0
    if issues:
        print(f"❌ omo lint ingress-registry fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint ingress-registry pass: "
        f"goals={len(summary.get('goal_ids', []))} "
        f"tasks={len(summary.get('task_ids', []))} "
        f"debts={len(summary.get('debt_ids', []))} "
        f"capabilities={len(summary.get('capability_ids', []))}"
    )
    return 0


def cmd_lint_mutation_surfaces(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_mutation_surface_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_mutation_surface_registry(root)
    if issues:
        print(f"❌ omo lint mutation-surfaces fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint mutation-surfaces pass: "
            f"surfaces={len(summary.get('runtime_surface_names', []))}"
        )
    else:
        print("✅ omo lint mutation-surfaces pass: registry not created yet")
    return 0


def cmd_lint_internal_write_profiles(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_internal_write_profile_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_internal_write_profile_registry(root)
    if issues:
        print(f"❌ omo lint internal-write-profiles fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint internal-write-profiles pass: "
            f"profiles={len(summary.get('runtime_profile_names', []))}"
        )
    else:
        print("✅ omo lint internal-write-profiles pass: registry not created yet")
    return 0


def cmd_lint_state_plane_assets(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_state_plane_asset_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_state_plane_asset_registry(root)
    if issues:
        print(f"❌ omo lint state-plane-assets fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint state-plane-assets pass: "
            f"top_level_assets={summary.get('top_level_asset_count', 0)} "
            f"persistence_modes={len(summary.get('persistence_mode_counts', {}))}"
        )
    else:
        print("✅ omo lint state-plane-assets pass: registry not created yet")
    return 0


def cmd_lint_c2g_omo_boundary(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_c2g_omo_boundary,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_c2g_omo_boundary(root)
    if issues:
        print(f"❌ omo lint c2g-omo-boundary fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint c2g-omo-boundary pass: "
        f"facade={summary.get('facade_path')} violations={len(summary.get('violations', []))}"
    )
    return 0


def cmd_lint_ingress_artifacts(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_ingress_artifacts,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_artifacts(root)
    if issues:
        print(f"❌ omo lint ingress-artifacts fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint ingress-artifacts pass: "
            f"goals={summary.get('goal_artifacts', 0)} "
            f"tasks={summary.get('task_artifacts', 0)} "
            f"debts={summary.get('debt_artifacts', 0)} "
            f"capabilities={summary.get('capability_artifacts', 0)}"
        )
    else:
        print("✅ omo lint ingress-artifacts pass: registry not created yet")
    return 0
