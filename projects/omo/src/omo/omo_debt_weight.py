#!/usr/bin/env python3
"""债务权重计算模块 — 影响 health_score 乘数因子.

在 sync_omo_state.py 中引入，使健康分反映核心债务的实际解决状态。
"""

from pathlib import Path
from typing import Optional

TIER_MULTIPLIERS: dict[str, float] = {
    "Axiom": 2.0,
    "Principle": 1.5,
    "Theory": 1.5,
    "Framework": 1.2,
    "Knowledge": 1.0,
    "Skill": 0.8,
    "Tool": 0.6,
}

_DEFAULT_TIER_MULTIPLIER: float = 1.0


def get_tier_multiplier(tier: str) -> float:
    """Return the weight multiplier for a given x3_tier value.

    Unknown or empty tier returns 1.0.
    """
    return TIER_MULTIPLIERS.get(tier, _DEFAULT_TIER_MULTIPLIER)


def get_computed_weight(item: dict) -> float:
    """Return weight * tier_multiplier for a debt item dict.

    Expects item to have 'weight' (float) and optionally 'x3_tier' (str).
    """
    weight = float(item.get("weight", 0))
    tier = item.get("x3_tier", "")
    return round(weight * get_tier_multiplier(tier), 4)


# LEGACY — use load_debt_items_from_ledger() for new code
DEBT_ITEMS: dict[str, dict] = {
    "D2_CI_E2E": {"weight": 0.15, "desc": "CI E2E 测试环境容器化", "x3_tier": "Framework"},
    "D3_EU_PRICING": {"weight": 0.15, "desc": "eu-pricing 独立测试覆盖", "x3_tier": "Framework"},
    "SB_DECOMPOSITION": {
        "weight": 0.20,
        "desc": "SharedBrain 拆解进度 (19器官→核+迁移+废弃)",
        "x3_tier": "Principle",
    },
    "SB_UNTESTED_PKGS": {
        "weight": 0.15,
        "desc": "kairon 4个untested包 (core-models, shared-lib, sharedbrain-bridge, wksp)",
        "x3_tier": "Framework",
    },
    "SB_ORPHANED_TASKS": {"weight": 0.10, "desc": "orphaned_tasks 结构化 registry", "x3_tier": "Tool"},
    "SB_ROOT_CLEANUP": {"weight": 0.05, "desc": "根目录 SharedBrain/ 空壳清理", "x3_tier": "Skill"},
    "SB_BRIDGE_FIX": {"weight": 0.10, "desc": "sharedbrain-bridge 死代码清理或重连", "x3_tier": "Tool"},
    "SB_PROJECTS_YAML": {"weight": 0.05, "desc": "PROJECTS.yaml 行数更新 (71K→824K)", "x3_tier": "Knowledge"},
    "SB_PHASE17_PLAN": {"weight": 0.05, "desc": "Phase 17 Wave 1 实施计划创建", "x3_tier": "Knowledge"},
}


def load_debt_items_from_ledger(omo_dir: Optional[Path] = None) -> dict[str, dict]:
    """Load debt items from the actual YAML files via ledger."""
    if omo_dir is None:
        omo_dir = Path(__file__).resolve().parents[2] / ".omo"
    try:
        from .omo_debt_registry import load_debt_ledger

        ledger = load_debt_ledger(omo_dir)
        return {
            item.id: {
                "weight": float(item.weight),
                "desc": item.title,
                "x3_tier": item.x3_tier or "",
                "severity": item.severity,
                "lifecycle_state": item.lifecycle_state,
                "x1_policy_ref": item.x1_policy_ref or "",
            }
            for item in ledger.items
        }
    except Exception:
        return {}


def compute_debt_weight(
    resolved_items: set[str], debt_items: Optional[dict[str, dict]] = None
) -> float:
    """计算债务权重因子.

    Uses get_computed_weight() which applies tier multipliers (x3_tier).

    resolved_items: 已解决的债务项 ID 集合.
    返回 0.30-1.0 之间的乘数.
    1.0 = 所有债务已解决, 0.30 = 最低健康保障.
    """
    items = debt_items or load_debt_items_from_ledger()
    total_weight = sum(get_computed_weight(v) for v in items.values())
    if total_weight == 0:
        return 1.0
    resolved_weight = sum(
        get_computed_weight(v) for k, v in items.items() if k in resolved_items
    )
    # Floor at 0.3 — even with zero debt resolution, system doesn't have zero health
    return max(round(resolved_weight / total_weight, 2), 0.30)


def debt_summary(
    resolved_items: set[str], debt_items: Optional[dict[str, dict]] = None
) -> dict:
    """生成债务状态摘要，用于写入 system.yaml."""
    items = debt_items or load_debt_items_from_ledger()
    return {
        k: {
            "resolved": k in resolved_items,
            "weight": v["weight"],
            "desc": v["desc"],
        }
        for k, v in items.items()
    }
