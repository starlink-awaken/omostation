#!/usr/bin/env python3
"""P84 W1.3 双轨指标导出器 — 能力轨(场景库) + 产能轨(真实 tasks).

🔴 红线 (P84 §0): 能力轨数据绝不能混入产能轨, 反之亦然.
   两轨数据源物理隔离, 标数据源, 禁止合并成单一"任务数".

输出: .omo/state/collab-dualtrack.yaml (SSOT 中间态, 供 generate-brief 读)

Usage:
  python3 bin/collab/export-dualtrack.py           # 写 YAML + stdout JSON
  python3 bin/collab/export-dualtrack.py --quiet   # 只写 YAML
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario_lib import load_scenario, run_scenario  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCN_DIR = REPO / ".omo" / "_delivery" / "collab-scenarios"
TASKS_DONE = REPO / ".omo" / "tasks" / "done"
TASKS_PLANNED = REPO / ".omo" / "tasks" / "planned"
OUT_YAML = REPO / ".omo" / "state" / "collab-dualtrack.yaml"

# P84 W3 产能目标 (ADR-0256) — 诚实 gap, 不可造卡冲数
W3_DONE_TARGET = 30
# planned 中不计入 "active backlog" 的终态 (仍进 planned_total 透明度字段)
INACTIVE_PLANNED_STATUS = frozenset(
    {"archived", "done", "closed", "cancelled", "deferred"}
)


def export_capability_track() -> dict:
    """能力轨: 从场景库跑批导出 (构造场景, 可批量注入加速)."""
    scenarios = []
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        r = run_scenario(sc)
        scenarios.append(r.to_dict())
    total = len(scenarios)
    passed = sum(1 for s in scenarios if s["passed"])
    adversarial = [s for s in scenarios if s["adversarial"]]
    adv_failed = sum(1 for s in adversarial if not s["passed"])
    cats: dict[str, dict] = {}
    for s in scenarios:
        c = cats.setdefault(s["category"], {"total": 0, "passed": 0})
        c["total"] += 1
        c["passed"] += 1 if s["passed"] else 0
    conflict_scenarios = [s for s in scenarios if s["category"] == "A_conflict"]
    conflict_resolved = sum(1 for s in conflict_scenarios if s["passed"])
    return {
        "data_source": "构造场景 (.omo/_delivery/collab-scenarios/, 可批量注入加速)",
        "scenario_total": total,
        "scenario_passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "category_coverage": cats,
        "adversarial_total": len(adversarial),
        "adversarial_failed": adv_failed,
        "adversarial_fail_rate": round(adv_failed / len(adversarial), 3) if adversarial else 0,
        "conflict_resolution_success_rate": (
            round(conflict_resolved / len(conflict_scenarios), 3) if conflict_scenarios else None
        ),
        "avg_resolution_rounds": (
            round(sum(s["resolution_rounds"] for s in scenarios) / total, 2) if total else 0
        ),
    }


def _parse_task_yaml(path: Path) -> dict:
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict) and ("status" in doc or "id" in doc):
            return doc
    return {}


def _list_planned_yaml() -> list[Path]:
    """planned 含子目录 (vision-roadmap/), 只计 *.yaml."""
    if not TASKS_PLANNED.exists():
        return []
    return sorted(p for p in TASKS_PLANNED.rglob("*.yaml") if p.is_file())


def export_throughput_track() -> dict:
    """产能轨: 从真实 tasks SSOT 导出 (真实 backlog, 不可造)."""
    done_files = sorted(TASKS_DONE.glob("*.yaml")) if TASKS_DONE.exists() else []
    planned_files = _list_planned_yaml()
    done = len(done_files)
    planned = len(planned_files)
    total = done + planned
    silent_loss = 0
    human_direct = 0
    agent_done = 0
    for f in done_files:
        try:
            d = _parse_task_yaml(f)
        except Exception:  # noqa: BLE001
            silent_loss += 1  # 解析失败 = 潜在静默丢失 (硬红线)
            continue
        if d.get("status") != "done" or not d.get("completed_at"):
            silent_loss += 1
        cm = d.get("collab_metrics", {}) or {}
        if cm.get("human_direct"):
            human_direct += 1
        else:
            agent_done += 1

    active_planned = 0
    inactive_planned = 0
    for f in planned_files:
        try:
            d = _parse_task_yaml(f)
        except Exception:  # noqa: BLE001
            active_planned += 1  # 解析失败按 active 计, 避免低估 backlog
            continue
        st = str(d.get("status") or "pending").lower()
        if st in INACTIVE_PLANNED_STATUS:
            inactive_planned += 1
        else:
            active_planned += 1

    gap = max(0, W3_DONE_TARGET - done)
    return {
        "data_source": "真实 backlog (.omo/tasks/done+planned/, 不可造)",
        "real_task_total": total,
        "done": done,
        "planned": planned,
        "planned_active": active_planned,
        "planned_inactive": inactive_planned,
        "completion_rate": round(done / total, 3) if total else 0,
        "w3_done_target": W3_DONE_TARGET,
        "gap_to_target": gap,
        "human_direct_count": human_direct,
        "human_direct_ratio": round(human_direct / done, 3) if done else 0,
        "agent_done_count": agent_done,
        "silent_loss": silent_loss,  # 硬红线 = 0
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="P84 W1.3 双轨指标导出")
    ap.add_argument("--quiet", action="store_true", help="只写 YAML 不输出 JSON")
    ap.add_argument(
        "--throughput-only",
        action="store_true",
        help="只导出产能轨 (跳过场景库跑批, 快速看 gap)",
    )
    args = ap.parse_args()

    cap = (
        {"skipped": True, "reason": "--throughput-only"}
        if args.throughput_only
        else export_capability_track()
    )
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "schema": "p84-dualtrack-v1",
        "capability_track": cap,
        "throughput_track": export_throughput_track(),
        "redline_note": "两轨数据源独立, 禁止合并; 构造场景计产能轨=最高级违规 (P84 §0)",
    }
    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(
        yaml.safe_dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    if not args.quiet:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
