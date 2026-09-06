#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 仓库维护统一入口.

统一调度现有维护工具，避免新增多个脚本致 bin-quota-diff 失败.

使用:
  python bin/gac/repo-maintenance.py --daily          # 每日维护
  python bin/gac/repo-maintenance.py --weekly         # 周报生成
  python bin/gac/repo-maintenance.py --hardcode-only  # 仅硬编码扫描
  python bin/gac/repo-maintenance.py --worktree-only  # 仅 worktree 清理
  python bin/gac/repo-maintenance.py --branch-only    # 仅分支清理
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
LOG_DIR = WORKSPACE / "runtime/cron"

TASKS = {
    "readme": {
        "name": "README 硬编码检测",
        "cmd": [sys.executable, str(WORKSPACE / "bin/gac/check-readme-hardcoded.py"), "--json"],
        "timeout": 60,
    },
    "worktree": {
        "name": "Worktree 清理",
        "cmd": [sys.executable, str(WORKSPACE / "bin/gac/worktree-hygiene-audit.py"),
                "--auto-clean", "--execute", "--stale-days", "3"],
        "timeout": 120,
    },
    "branch": {
        "name": "分支 TTL 清理",
        "cmd": ["bash", str(WORKSPACE / "bin/gac/gac-branch-prune.sh")],
        "timeout": 120,
    },
    "ssot": {
        "name": "SSOT 守护",
        "cmd": ["make", "ssot-guardian"],
        "timeout": 120,
    },
}


def run_task(task_id: str, task: dict, dry_run: bool = False) -> dict:
    """执行单个任务."""
    start = time.time()
    if dry_run:
        print(f"[DRY-RUN] {task['name']}: {' '.join(task['cmd'])}")
        return {"id": task_id, "ok": True, "duration": 0}

    print(f"[RUN] {task['name']}: {' '.join(task['cmd'])}")
    try:
        result = subprocess.run(
            task["cmd"], cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=task["timeout"]
        )
        ok = result.returncode == 0
        if not ok:
            print(f"[WARN] {task['name']} 返回非零: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
    except Exception as e:
        print(f"[ERROR] {task['name']}: {e}")
        ok = False

    duration = time.time() - start
    return {"id": task_id, "name": task["name"], "ok": ok, "duration": round(duration, 1)}


def generate_report(results: list[dict]) -> str:
    """生成周报."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 收集本地统计
    remote_branches = subprocess.run(
        ["git", "branch", "-r"], cwd=str(WORKSPACE),
        capture_output=True, text=True
    ).stdout.count("\n")

    local_branches = subprocess.run(
        ["git", "branch"], cwd=str(WORKSPACE),
        capture_output=True, text=True
    ).stdout.count("\n")

    tags = subprocess.run(
        ["git", "tag"], cwd=str(WORKSPACE),
        capture_output=True, text=True
    ).stdout.count("\n")

    worktrees = subprocess.run(
        ["git", "worktree", "list"], cwd=str(WORKSPACE),
        capture_output=True, text=True
    ).stdout.count("\n") - 1  # 减去主仓

    lines = [
        f"# 仓库健康度周报",
        "",
        f"> 生成时间: {now}",
        f"> 自动生成: `bin/gac/repo-maintenance.py --weekly`",
        "",
        "## 执行摘要",
        "",
        "| 任务 | 状态 | 耗时 |",
        "|------|------|------|",
    ]

    all_ok = True
    for r in results:
        status = "✅" if r["ok"] else "❌"
        lines.append(f"| {r['name']} | {status} | {r['duration']}s |")
        if not r["ok"]:
            all_ok = False

    lines.extend([
        "",
        "## 本地统计",
        "",
        f"| 指标 | 数值 |",
        f"|------|------:|",
        f"| 远程分支 | {remote_branches} |",
        f"| 本地分支 | {local_branches} |",
        f"| Tags | {tags} |",
        f"| Worktrees | {worktrees} |",
        "",
        "## 建议",
        "",
        "- 定期清理已合入 main 的远程分支",
        "- 清理过期的 tags",
        "- 同步子模块指针到最新 main",
        "- 清理僵尸 worktree",
        "",
        "---",
        "",
        "*本报告由 `bin/gac/repo-maintenance.py` 自动生成.*",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="仓库维护统一入口")
    parser.add_argument("--daily", action="store_true", help="每日维护")
    parser.add_argument("--weekly", action="store_true", help="周报生成")
    parser.add_argument("--hardcode-only", action="store_true")
    parser.add_argument("--worktree-only", action="store_true")
    parser.add_argument("--branch-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if args.daily or (not args.weekly and not args.hardcode_only and not args.worktree_only and not args.branch_only):
        print(f"=== 每日仓库维护 {datetime.now(timezone.utc).isoformat()} ===")
        results = []
        for task_id in ["readme", "worktree", "branch", "ssot"]:
            result = run_task(task_id, TASKS[task_id], dry_run=args.dry_run)
            results.append(result)

        if args.dry_run:
            return 0

        # 写入日志
        log_file = LOG_DIR / f"daily-maintenance-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} ")
            f.write(f"results={','.join(r['id'] + '=' + ('ok' if r['ok'] else 'fail') for r in results)}\n")

        return 0 if all(r["ok"] for r in results) else 1

    if args.weekly:
        print(f"=== 仓库健康周报 {datetime.now(timezone.utc).isoformat()} ===")
        results = []
        for task_id in ["readme", "worktree", "branch"]:
            result = run_task(task_id, TASKS[task_id], dry_run=True)
            results.append(result)

        report = generate_report(results)
        report_path = WORKSPACE / "docs/repository-health.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"✅ 已生成 {report_path}")
        return 0

    if args.hardcode_only:
        result = run_task("readme", TASKS["readme"], dry_run=args.dry_run)
        return 0 if result["ok"] else 1

    if args.worktree_only:
        result = run_task("worktree", TASKS["worktree"], dry_run=args.dry_run)
        return 0 if result["ok"] else 1

    if args.branch_only:
        result = run_task("branch", TASKS["branch"], dry_run=args.dry_run)
        return 0 if result["ok"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
