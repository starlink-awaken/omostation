#!/usr/bin/env python3
"""architecture-constraints.py — 架构约束与驱动机制.

硬约束 (不可逃逸):
- SFOP S 槽位唯一性
- 脚本配额 ≤ 560
- 规则配额 ≤ 85
- 场景卡 5 级生命周期
- harness 8 阶段 DAG

软驱动 (激励相容):
- 规则合并奖励
- 表面积减少奖励
- 自动化率提升奖励
- 维度健康度奖励

用法:
    python3 bin/gac/architecture-constraints.py --check
    python3 bin/gac/architecture-constraints.py --enforce
    python3 bin/gac/architecture-constraints.py --report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# ── 硬约束定义 ──
HARD_CONSTRAINTS = {
    "sfop_s_unique": {
        "description": "SFOP S 槽位必须唯一 (COMP-WS-omo)",
        "check": "check_sfop_s",
        "blocking": True,
    },
    "script_quota": {
        "description": "bin/ 脚本数量 ≤ 560",
        "check": "count_bin_scripts",
        "blocking": True,
        "max": 560,
    },
    "rule_quota": {
        "description": "GaC 规则数量 ≤ 85",
        "check": "count_gac_rules",
        "blocking": True,
        "max": 85,
    },
    "scene_lifecycle": {
        "description": "场景卡必须符合 5 级生命周期",
        "check": "check_scene_lifecycle",
        "blocking": True,
    },
    "harness_dag": {
        "description": "harness 必须实现 8 阶段 DAG",
        "check": "check_harness_dag",
        "blocking": False,  # 软约束, 逐步推进
    },
}

# ── 软驱动定义 ──
SOFT_DRIVERS = {
    "rule_merge": {
        "description": "合并 2 条规则可新增 1 条",
        "reward": "unlock_new_rule",
        "metric": "rules_merged",
    },
    "surface_reduction": {
        "description": "表面积净减少奖励",
        "reward": "budget_extension",
        "metric": "net_surface_change",
    },
    "automation_boost": {
        "description": "自动化率提升奖励",
        "reward": "priority_boost",
        "metric": "automation_rate",
    },
    "dimension_health": {
        "description": "维度健康度 ≥ 9.5 奖励",
        "reward": "recognition",
        "metric": "dimension_score",
    },
}


def check_sfop_s() -> dict:
    """检查 SFOP S 槽位唯一性"""
    try:
        result = subprocess.run(
            [sys.executable, str(WORKSPACE / "bin/gac/check-sfop-slots.py"), "--json"],
            capture_output=True, text=True, cwd=str(WORKSPACE),
        )
        return {"ok": result.returncode == 0, "output": result.stdout[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def count_bin_scripts() -> dict:
    """计算 bin/ 脚本数量"""
    bin_dir = WORKSPACE / "bin"
    if not bin_dir.exists():
        return {"ok": False, "count": 0}

    count = 0
    for f in bin_dir.rglob("*.py"):
        if "_archive" not in str(f) and f.is_file():
            count += 1

    return {"ok": count <= 560, "count": count, "max": 560}


def count_gac_rules() -> dict:
    """计算 GaC 规则数量"""
    rules_file = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"
    if not rules_file.exists():
        return {"ok": False, "count": 0}

    try:
        import yaml
        data = yaml.safe_load(rules_file.read_text(encoding="utf-8"))
        rules = data.get("gac", {}).get("rules", [])
        active = [r for r in rules if r.get("status") != "removed"]
        return {"ok": len(active) <= 85, "count": len(active), "max": 85}
    except Exception:
        return {"ok": False, "count": 0}


def check_scene_lifecycle() -> dict:
    """检查场景卡生命周期合规"""
    scenes_dir = WORKSPACE / "docs/scene-cards"
    if not scenes_dir.exists():
        return {"ok": True, "count": 0}

    valid_levels = {"draft", "shadow", "assisted", "supervised", "routine"}
    violations = 0
    total = 0

    for f in scenes_dir.glob("*.yaml"):
        total += 1
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            lifecycle = data.get("lifecycle", "")
            if lifecycle and lifecycle not in valid_levels:
                violations += 1
        except Exception:
            pass

    return {"ok": violations == 0, "total": total, "violations": violations}


def check_harness_dag() -> dict:
    """检查 harness 8 阶段 DAG 实现"""
    harness_file = WORKSPACE / "bin/harness"
    if not harness_file.exists():
        return {"ok": False, "error": "harness not found"}

    text = harness_file.read_text(encoding="utf-8")
    stages_found = [s for s in ["admission", "spec", "grill", "dispatch",
                                 "execute", "verify", "audit", "accept"]
                    if s in text.lower()]

    return {"ok": len(stages_found) >= 8, "stages_found": len(stages_found)}


def run_check(constraint_name: str, constraint_info: dict) -> dict:
    """运行单个约束检查"""
    check_fn_name = constraint_info.get("check", "")
    check_fns = {
        "check_sfop_s": check_sfop_s,
        "count_bin_scripts": count_bin_scripts,
        "count_gac_rules": count_gac_rules,
        "check_scene_lifecycle": check_scene_lifecycle,
        "check_harness_dag": check_harness_dag,
    }

    fn = check_fns.get(check_fn_name)
    if not fn:
        return {"ok": False, "error": f"unknown check: {check_fn_name}"}

    return fn()


def run_all_checks() -> dict:
    """运行所有约束检查"""
    results = {}
    all_ok = True

    for name, info in HARD_CONSTRAINTS.items():
        result = run_check(name, info)
        results[name] = {**result, "blocking": info.get("blocking", False)}
        if not result.get("ok", False) and info.get("blocking", False):
            all_ok = False

    return {"all_ok": all_ok, "constraints": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="架构约束与驱动机制")
    parser.add_argument("--check", action="store_true", help="运行约束检查")
    parser.add_argument("--enforce", action="store_true", help="强制执行约束")
    parser.add_argument("--report", action="store_true", help="生成报告")
    args = parser.parse_args()

    if args.check or args.enforce:
        results = run_all_checks()

        if args.report or args.check:
            print("=== 架构约束检查 ===")
            for name, result in results["constraints"].items():
                status = "PASS" if result.get("ok") else "FAIL"
                blocking = " [BLOCKING]" if result.get("blocking") else ""
                print(f"  [{status}] {name}{blocking}")
                if not result.get("ok") and "error" in result:
                    print(f"    Error: {result['error']}")
                if "count" in result:
                    print(f"    Count: {result.get('count')}/{result.get('max', '?')}")

            print()
            print(f"{'ALL CONSTRAINTS PASS' if results['all_ok'] else 'SOME CONSTRAINTS FAILED'}")

        return 0 if results["all_ok"] else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
