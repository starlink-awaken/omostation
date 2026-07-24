"""omo manage — .omo 目录管理工具集.

从 bin/omo-manage 迁移.

提供:
  - status: 显示 .omo 目录状态 (文件统计、关键文件检查)
  - health: 检查 .omo 目录健康度 (stale 文件、broken references)
  - tasks: 列出任务状态 (active/planned/done/blocked)
"""

from __future__ import annotations

import argparse
import time

from omo.omo_paths import OMO_ROOT, TASKS_DIR
from omo.omo_shared import load_yaml

KEY_FILES = [
    "state/system.yaml",
    "state/health.yaml",
    "goals/current.yaml",
    "_truth/INDEX.md",
    "_truth/registry/mof-capabilities.yaml",
    "standards/omo-governance-surfaces.md",
]


def cmd_status() -> int:
    """显示 .omo 目录状态."""
    print("OMO 目录状态\n")

    # Count files by directory
    print("目录统计:")
    for subdir in sorted(OMO_ROOT.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            count = sum(1 for f in subdir.rglob("*") if f.is_file())
            if count > 0:
                print(f"  {subdir.name}: {count} files")
    print()

    # Count by file type
    print("文件类型:")
    for ext in [".yaml", ".md", ".json", ".py", ".sh"]:
        count = sum(1 for f in OMO_ROOT.rglob(f"*{ext}") if f.is_file())
        if count > 0:
            print(f"  {ext}: {count}")
    print()

    # Key files
    print("关键文件:")
    for f in KEY_FILES:
        path = OMO_ROOT / f
        if path.exists():
            print(f"  [OK] {f}")
        else:
            print(f"  [MISSING] {f}")

    return 0


def cmd_health() -> int:
    """检查 .omo 目录健康度."""
    print("OMO 健康检查\n")

    issues: list[str] = []

    # Check for stale files
    system_yaml = OMO_ROOT / "state" / "system.yaml"
    if system_yaml.exists():
        mtime = system_yaml.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        if age_hours > 24:
            issues.append(f"system.yaml is {age_hours:.1f}h old (>24h)")

    # Check for broken references
    goals = OMO_ROOT / "goals" / "current.yaml"
    if goals.exists():
        data = load_yaml(goals)
        if data and "goals" in data:
            for goal in data["goals"]:
                if goal.get("status") == "active" and goal.get("progress", 0) < 100 or goal.get("status") == "done" and goal.get("progress", 0) == 100:
                    pass  # OK
                else:
                    issues.append(
                        f"Goal {goal.get('id', '')} has inconsistent status/progress"
                    )

    if not issues:
        print("No issues found.")
    else:
        print(f"{len(issues)} issues found:")
        for issue in issues:
            print(f"  - {issue}")

    return 0


def cmd_tasks() -> int:
    """列出任务状态."""
    print("任务状态\n")

    for subdir in ["active", "planned", "done", "blocked"]:
        task_dir = TASKS_DIR / subdir
        if task_dir.exists():
            count = sum(1 for f in task_dir.glob("*.yaml") if f.is_file())
            print(f"  {subdir}: {count}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo manage",
        description="OMO 目录管理工具集",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "status",
        help="显示 .omo 目录状态 (文件统计、关键文件检查)",
    )
    sub.add_parser(
        "health",
        help="检查 .omo 目录健康度 (stale 文件、broken references)",
    )
    sub.add_parser(
        "tasks",
        help="列出任务状态 (active/planned/done/blocked)",
    )

    args = parser.parse_args(argv)

    if args.command == "status":
        return cmd_status()
    if args.command == "health":
        return cmd_health()
    if args.command == "tasks":
        return cmd_tasks()

    parser.print_help()
    return 1
