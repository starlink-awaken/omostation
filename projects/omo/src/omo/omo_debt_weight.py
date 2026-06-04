#!/usr/bin/env python3
"""债务权重计算模块 — 影响 health_score 乘数因子.

在 sync_omo_state.py 中引入，使健康分反映核心债务的实际解决状态。
"""

from typing import Optional


DEBT_ITEMS: dict[str, dict] = {
    "D2_CI_E2E": {"weight": 0.15, "desc": "CI E2E 测试环境容器化"},
    "D3_EU_PRICING": {"weight": 0.15, "desc": "eu-pricing 独立测试覆盖"},
    "SB_DECOMPOSITION": {
        "weight": 0.20,
        "desc": "SharedBrain 拆解进度 (19器官→核+迁移+废弃)",
    },
    "SB_UNTESTED_PKGS": {
        "weight": 0.15,
        "desc": "kairon 4个untested包 (core-models, shared-lib, sharedbrain-bridge, wksp)",
    },
    "SB_ORPHANED_TASKS": {"weight": 0.10, "desc": "orphaned_tasks 结构化 registry"},
    "SB_ROOT_CLEANUP": {"weight": 0.05, "desc": "根目录 SharedBrain/ 空壳清理"},
    "SB_BRIDGE_FIX": {"weight": 0.10, "desc": "sharedbrain-bridge 死代码清理或重连"},
    "SB_PROJECTS_YAML": {"weight": 0.05, "desc": "PROJECTS.yaml 行数更新 (71K→824K)"},
    "SB_PHASE17_PLAN": {"weight": 0.05, "desc": "Phase 17 Wave 1 实施计划创建"},
}


def compute_debt_weight(
    resolved_items: set[str], debt_items: Optional[dict[str, dict]] = None
) -> float:
    """计算债务权重因子.

    resolved_items: 已解决的债务项 ID 集合.
    返回 0.0-1.0 之间的乘数.
    1.0 = 所有债务已解决, 0.0 = 全部未解决.
    """
    items = debt_items or DEBT_ITEMS
    total_weight = sum(v["weight"] for v in items.values())
    if total_weight == 0:
        return 1.0
    resolved_weight = sum(v["weight"] for k, v in items.items() if k in resolved_items)
    # Floor at 0.3 — even with zero debt resolution, system doesn't have zero health
    return max(round(resolved_weight / total_weight, 2), 0.30)


def debt_summary(
    resolved_items: set[str], debt_items: Optional[dict[str, dict]] = None
) -> dict:
    """生成债务状态摘要，用于写入 system.yaml."""
    items = debt_items or DEBT_ITEMS
    return {
        k: {
            "resolved": k in resolved_items,
            "weight": v["weight"],
            "desc": v["desc"],
        }
        for k, v in items.items()
    }
