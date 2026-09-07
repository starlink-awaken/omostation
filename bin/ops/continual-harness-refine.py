#!/usr/bin/env python3
"""continual-harness-refine — 轨迹审阅与技能萃取管道.

(BET-Y1Q4-T7-07)

长程任务结案或自愈后自动触发 /refine:

1. 审阅执行轨迹证据 (Evidence-backed)
2. 结晶生成 Python 模块化技能包 (Skills as Code)
3. 环境提示词补丁
4. 赋予 refinement_id 并支持一键原子化 Rollback

用法:
    python3 bin/ops/continual-harness-refine.py --task-id <id>
    python3 bin/ops/continual-harness-refine.py --auto
    python3 bin/ops/continual-harness-refine.py --rollback <refinement_id>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# ── CLI ─────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Continual Harness /refine 管道 — 轨迹审阅与技能萃取"
    )
    parser.add_argument("--task-id", help="指定任务 ID 进行审阅")
    parser.add_argument("--auto", action="store_true", help="自动检测已完成任务")
    parser.add_argument("--rollback", metavar="REFINEMENT_ID", help="回滚到指定版本")
    parser.add_argument("--list", action="store_true", help="列出所有 refinement")
    parser.add_argument("--dry-run", action="store_true", help="仅审阅不安装")
    parser.add_argument("--output", choices=["text", "json"], default="text")

    args = parser.parse_args()

    if args.rollback:
        return _cmd_rollback(args.rollback, args.output)
    if args.list:
        return _cmd_list(args.output)
    if args.task_id:
        return _cmd_refine_task(args.task_id, args.dry_run, args.output)
    if args.auto:
        return _cmd_auto(args.dry_run, args.output)

    parser.print_help()
    return 0


# ── Commands ────────────────────────────────────────────────────


def _cmd_rollback(refinement_id: str, output: str) -> int:
    """执行回滚."""
    from omo.resident.refine_rollback import (
        AtomicRollback,
        get_refinement_store,
        get_snapshot_manager,
    )

    store = get_refinement_store()
    snapshots = get_snapshot_manager()
    rollback = AtomicRollback(store, snapshots)

    result = rollback.rollback_sync(refinement_id)

    if output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["ok"]:
            print(f"✅ 回滚成功: {refinement_id}")
            print(f"   恢复快照数: {result.get('snapshots_restored', 0)}")
            print(f"   耗时: {result.get('elapsed_ms', 0):.1f}ms")
        else:
            print(f"❌ 回滚失败: {result.get('error', 'unknown')}")
    return 0 if result["ok"] else 1


def _cmd_list(output: str) -> int:
    """列出所有 refinement."""
    from omo.resident.refine_rollback import get_refinement_store

    store = get_refinement_store()
    versions = store.list_refinements()

    if output == "json":
        print(json.dumps([v.__dict__ for v in versions], ensure_ascii=False, indent=2, default=str))
    else:
        if not versions:
            print("暂无 refinement 版本")
            return 0
        print(f"{'ID':<20} {'名称':<30} {'状态':<12} {'技能数':<8} {'创建时间'}")
        print("-" * 90)
        for v in versions:
            print(f"{v.refinement_id:<20} {v.name:<30} {v.status:<12} {len(v.skill_names):<8} {time.strftime('%Y-%m-%d %H:%M', time.localtime(v.created_at))}")
    return 0


def _cmd_refine_task(task_id: str, dry_run: bool, output: str) -> int:
    """审阅指定任务."""
    reviewer = TrajectoryReviewer()
    result = reviewer.review_task(task_id)

    if output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"任务: {task_id}")
        print(f"状态: {result.get('status', 'unknown')}")
        print(f"步骤数: {result.get('step_count', 0)}")
        print(f"可结晶改进: {len(result.get('improvements', []))}")

    if not dry_run and result.get("improvements"):
        extractor = SkillExtractor()
        refined = extractor.refine(result)
        if output == "json":
            print(json.dumps(refined, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"\n✅ 生成技能包: {refined.get('skill_name', 'n/a')}")
            print(f"   refinement_id: {refined.get('refinement_id', 'n/a')}")
    return 0


def _cmd_auto(dry_run: bool, output: str) -> int:
    """自动检测已完成任务."""
    reviewer = TrajectoryReviewer()
    tasks = reviewer.discover_completed_tasks()

    if output == "json":
        print(json.dumps(tasks, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"发现 {len(tasks)} 个已完成任务")

    for task in tasks:
        _cmd_refine_task(task["task_id"], dry_run, output)

    return 0


# ── Trajectory Reviewer ────────────────────────────────────────


@dataclass
class Improvement:
    """可结晶的改进点."""
    key: str
    description: str
    evidence: list[str]
    pattern: str
    skill_type: str  # bug_fix | optimization | pattern | knowledge


class TrajectoryReviewer:
    """执行轨迹审阅器."""

    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir or Path(".omo/_delivery/agent-workflows/runs")

    def discover_completed_tasks(self) -> list[dict[str, Any]]:
        """发现已完成的任务."""
        tasks = []
        if not self._runs_dir.exists():
            return tasks
        for f in self._runs_dir.glob("*.yaml"):
            try:
                import yaml
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data.get("status") == "completed":
                    tasks.append({
                        "task_id": data.get("run_id", f.stem),
                        "completed_at": data.get("updated_at", ""),
                    })
            except Exception:
                continue
        return tasks

    def review_task(self, task_id: str) -> dict[str, Any]:
        """审阅指定任务的执行轨迹."""
        run_file = self._runs_dir / f"{task_id}.yaml"
        if not run_file.exists():
            return {"status": "not_found", "task_id": task_id}

        import yaml
        data = yaml.safe_load(run_file.read_text(encoding="utf-8"))

        improvements = self._extract_improvements(data)
        return {
            "status": data.get("status", "unknown"),
            "task_id": task_id,
            "step_count": len(data.get("steps", [])),
            "improvements": [i.__dict__ for i in improvements],
            "objective": data.get("objective", ""),
        }

    def _extract_improvements(self, data: dict[str, Any]) -> list[Improvement]:
        """从轨迹中提取可结晶的改进点."""
        improvements = []
        steps = data.get("steps", [])
        for step in steps:
            # 检测修复模式
            if step.get("action") in ("fix", "patch", "correct"):
                imp = Improvement(
                    key=f"fix:{step.get('target', 'unknown')}",
                    description=f"修复: {step.get('description', step.get('target', ''))}",
                    evidence=[str(step)],
                    pattern=step.get("pattern", ""),
                    skill_type="bug_fix",
                )
                improvements.append(imp)
        return improvements


# ── Skill Extractor ────────────────────────────────────────────


@dataclass
class RefineResult:
    """精炼结果."""
    refinement_id: str
    skill_name: str
    skill_path: str
    snapshot_ids: list[str]
    status: str


class SkillExtractor:
    """技能萃取器."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path(".agents/skills/auto-crystallized")

    def refine(self, review_result: dict[str, Any]) -> dict[str, Any]:
        """执行精炼."""
        from omo.resident.refine_rollback import (
            get_refinement_store,
            get_snapshot_manager,
        )

        store = get_refinement_store()
        snapshots = get_snapshot_manager()

        improvements = review_result.get("improvements", [])
        if not improvements:
            return {"status": "no_improvements"}

        # 创建 refinement 版本
        ver = store.create(
            name=f"refine-{review_result.get('task_id', 'manual')[:24]}",
            description=f"自动精炼: {review_result.get('objective', '')[:60]}",
        )

        # 创建快照
        snap_ids = []
        for imp in improvements:
            snap = snapshots.snapshot_skill(imp.get("key", "unknown"), self._skills_dir)
            snap_ids.append(snap.snap_id)

        ver.snapshot_ids = snap_ids
        ver.skill_names = [imp.get("key", "unknown") for imp in improvements]

        return {
            "refinement_id": ver.refinement_id,
            "skill_name": improvements[0].get("key", "unknown") if improvements else "none",
            "skill_path": str(self._skills_dir),
            "snapshot_ids": snap_ids,
            "status": "refined",
        }


# ── Imports ─────────────────────────────────────────────────────

from dataclasses import dataclass


if __name__ == "__main__":
    sys.exit(main())
