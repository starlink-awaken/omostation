"""cockpit.commands.debt_scoring — 债务评分 (omo-debt 收编入口)

将 omo-debt 的 Pattern 09 v2.1 评分算法直接接入 cockpit CLI,
替代独立的 omo-debt CLI (ADR-0122 F-13).

用法:
    cockpit debt score <impact> <frequency> <cost> --stage <stage>
    cockpit debt score --list-stages
"""

from __future__ import annotations

import argparse


def cmd_debt_score(args: argparse.Namespace) -> int:
    """债务评分 — 直接调用 omo-debt Pattern 09 v2.1 算法。"""
    try:
        from omo_debt.core.scoring import calculate_score_v2
        from omo_debt.core.stage import StageType
    except ImportError as e:
        print(f"⚠️  omo-debt scoring module not available: {e}", file=sys.stderr)
        print("   Run: uv sync --project projects/cockpit", file=sys.stderr)
        return 1

    if getattr(args, "list_stages", False):
        print("📊 可用项目阶段 (StageType):")
        for s in StageType.__args__:
            print(f"  - {s}")
        return 0

    impact = getattr(args, "impact", 5)
    frequency = getattr(args, "frequency", 5)
    cost = getattr(args, "cost", 5)
    stage = getattr(args, "stage", "stable_growth")

    if stage not in StageType.__args__:
        print(f"⚠️  无效阶段: {stage}", file=sys.stderr)
        print(f"   有效值: {', '.join(StageType.__args__)}", file=sys.stderr)
        return 1

    result = calculate_score_v2(impact, frequency, cost, stage)
    data = result.to_dict()

    print(f"📊 债务评分结果:")
    print(f"  影响: {data['debt_item']['impact']} | 频率: {data['debt_item']['frequency']} | 成本: {data['debt_item']['cost']}")
    print(f"  项目阶段: {data['project_stage']}")
    print(f"  基础分: {data['calculation']['base_score']}")
    print(f"  归一化分: {data['calculation']['normalized_score']}")
    print(f"  优先级: {data['calculation']['priority']}")
    print(f"  建议: {data['recommendation']}")
    return 0
