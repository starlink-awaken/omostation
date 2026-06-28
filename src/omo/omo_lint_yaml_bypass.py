"""P101 refactor: omo_lint yaml-bypass 子模块 (从 omo_lint.py 提取).

P99 ADR-0093 规划 P100-P103 4 步拆解 (校正后):
  P100 schemas 拆 (485L) ✓ done → 800L
  P101 yaml-bypass 拆 (74L) → 726L, <800L warn 阈值达成
  P102 surfaces 拆 (~140L) → 586L
  P103 mutation-ledger 拆 (57L) → 529L, <600L ideal

2 个 yaml-bypass 维度 (Round 43 P0):
  - _check_yaml_bypass: 扫 .omo/debt/items/*.yaml 检测 status/lifecycle_state 越权
  - cmd_lint_yaml_bypass: 汇总入口

业务独立性: yaml-bypass 仅依赖 Path + yaml, 零内部 helper, 零 omo_xxx 依赖.

向后兼容 (P88 + P100 模式):
  omo_lint.py 通过 `from .omo_lint_yaml_bypass import (...)` re-export,
  保持 `from omo.omo_lint import cmd_lint_yaml_bypass` 不破.
"""

from __future__ import annotations

from pathlib import Path


def _check_yaml_bypass(omo_dir: Path = Path(".omo")) -> list[tuple[str, str]]:
    """扫 .omo/debt/items/*.yaml 检测非 OMO CLI 写入的越权字段 (Round 43 P0).

    OMO 用 lifecycle_state 字段管理债务状态. fix_debts.py 这种越权
    脚本错改 status 字段 (OMO 不读 status 字段). 此 lint 拦截未来再发生.

    检测规则:
      R1: yaml 有 status 字段但没有 lifecycle_state 字段 → 越权 (非 OMO 写)
      R2: yaml 有 status 字段值是 closed/resolved 但 lifecycle_state 不一致 → 越权
      R4: yaml 解析失败 → 警告

    注: 不检查 history 字段 (R3 删了, 防误报 — fresh yaml seed 时无 history 是合法初始态).

    Returns:
        list of (yaml_filename, violation_message) tuples. 空 list = 合规.
    """
    items_dir = omo_dir / "debt" / "items"
    if not items_dir.is_dir():
        return []

    import yaml as _yaml

    issues: list[tuple[str, str]] = []
    for path in sorted(items_dir.glob("*.yaml")):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, _yaml.YAMLError) as exc:
            issues.append((path.name, f"R4: parse error: {exc}"))
            continue
        if not isinstance(data, dict):
            issues.append((path.name, "R4: yaml 不是 dict 结构"))
            continue

        has_status = "status" in data
        has_lifecycle = "lifecycle_state" in data
        status = data.get("status", "")
        lifecycle = data.get("lifecycle_state", "")

        if has_status and not has_lifecycle:
            issues.append(
                (
                    path.name,
                    f"R1: yaml 有 status={status!r} 字段但无 lifecycle_state (OMO 用 "
                    f"lifecycle_state, 改 status 是越权写入, OMO 不认)",
                )
            )
        elif has_status and status in ("closed", "resolved") and lifecycle != status:
            issues.append(
                (
                    path.name,
                    f"R2: status={status!r} 但 lifecycle_state={lifecycle!r} 不一致 "
                    f"(越权写入, OMO 以 lifecycle_state 为准)",
                )
            )

    return issues


def cmd_lint_yaml_bypass(omo_dir: Path = Path(".omo")) -> int:
    """omo lint yaml-bypass — Round 43 P0 拦截 .omo/debt/items/ 越权写入."""
    issues = _check_yaml_bypass(omo_dir)
    if issues:
        print(f"❌ omo lint yaml-bypass fail: {len(issues)} 处越权 (X1 审计风险)")
        for name, msg in issues:
            print(f"   - {name}: {msg}")
        print()
        print(
            "修复方法: 走 omo-debt close/reopen CLI 正路, 不要直接 yaml.safe_load + yaml.dump 改字段."
        )
        return 1
    print(
        "✅ omo lint yaml-bypass pass: 0 处越权 (所有 .omo/debt/items/*.yaml 走 OMO CLI 正路)"
    )
    return 0
