#!/usr/bin/env python3
"""
bin/gac/omo_debt_synthesizer.py — CSES 债务自动升维与 C2G Bet 聚类研判引擎 (标准 Python 模块)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from omo.omo_paths import WORKSPACE_ROOT
from omo.omo_shared import load_yaml_value

WS = WORKSPACE_ROOT


def load_debts() -> list[dict[str, Any]]:
    debt_dir = WS / ".omo" / "debt" / "items"
    debts = []
    if not debt_dir.exists():
        return debts
    for f in debt_dir.glob("*.yaml"):
        val = load_yaml_value(f)
        if isinstance(val, dict):
            debts.append(val)
    return debts


def synthesize_debts(debts: list[dict[str, Any]]) -> dict[str, Any]:
    """将微观 Debt 升维合成 Macro Vision Bet"""
    categories: dict[str, list[dict[str, Any]]] = {}
    for d in debts:
        cat = d.get("category") or d.get("domain") or "general"
        categories.setdefault(cat, []).append(d)

    goals_file = WS / ".omo" / "goals" / "current.yaml"
    default_goal_id = "GOAL-GOV-EVOLUTION"
    if goals_file.exists():
        gdata = load_yaml_value(goals_file) or {}
        active_goals = gdata.get("active_goals") or []
        if active_goals and isinstance(active_goals[0], dict):
            default_goal_id = active_goals[0].get("id", default_goal_id)

    proposed_bets = []
    for idx, (cat, items) in enumerate(categories.items(), 1):
        bet_id = f"BET-AUTO-CSES-{idx:02d}"
        title = f"[{cat.upper()}] 综合消除 {len(items)} 项技术债务与架构漂移"
        goal = f"治理并消灭 {cat} 领域的微观债务 ({', '.join([i.get('id', 'debt') for i in items[:3]])})"
        proposed_bets.append({
            "id": bet_id,
            "goal_id": default_goal_id,
            "track": "T1-GOVERNANCE",
            "window": "Y1Q1",
            "title": title,
            "appetite": "3 days",
            "priority": "P1",
            "status": "candidate",
            "goal": goal,
            "included_debts": [i.get("id") for i in items],
        })

    return {
        "total_debts_scanned": len(debts),
        "clusters_count": len(categories),
        "proposed_bets": proposed_bets,
    }


def save_bets_as_planned_tasks(bets: list[dict[str, Any]]) -> list[Path]:
    """将研判出的 Candidate Bet 保存为 .omo/tasks/planned/ 任务规范"""
    planned_dir = WS / ".omo" / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    for bet in bets:
        file_name = f"{bet['id']}.yaml"
        file_path = planned_dir / file_name
        import yaml
        content = yaml.dump(bet, allow_unicode=True, sort_keys=False)
        file_path.write_text(content, encoding="utf-8")
        saved_files.append(file_path)

    # 联动状态落盘强一致
    try:
        from omo.omo_state_sync import run_state_sync
        run_state_sync(WS / ".omo", apply=True)
    except Exception:
        pass

    return saved_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OMO Debt Synthesizer")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument("--save", action="store_true", help="Save candidate bets to .omo/tasks/planned/")
    args = parser.parse_args(argv)

    debts = load_debts()
    result = synthesize_debts(debts)

    if args.save:
        saved = save_bets_as_planned_tasks(result["proposed_bets"])
        print(f"✅ 已保存 {len(saved)} 个研判 Bet 至 {WS / '.omo/tasks/planned'}")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("═══ CSES 债务升维研判 ═══")
    print(f"扫描到微观 Debt: {result['total_debts_scanned']} 个")
    print(f"合成宏观 Bet 建议: {result['clusters_count']} 个\n")
    for b in result["proposed_bets"]:
        print(f"  • [{b['id']}] {b['title']}")
        print(f"    包含债务: {', '.join(b['included_debts'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
