#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 每日仓库维护综合窗口.
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

TASKS = [
    {"id": "hardcode", "name": "硬编码数据检测", "script": "bin/gac/check-readme-hardcoded.py", "args": ["--json"]},
    {"id": "worktree", "name": "Worktree 清理", "script": "bin/gac/prune-zombie-worktrees.py", "args": ["--apply"]},
    {"id": "branch", "name": "分支 TTL 清理", "script": "bin/gac/branch-ttl-gate.py", "args": ["--enforce", "--ttl-hours", "168"]},
    {"id": "ssot", "name": "SSOT 守护", "script": "make", "args": ["ssot-guardian"]},
]


def run_task(task: dict, dry_run: bool = False) -> dict:
    start = time.time()
    script = task["script"]
    args = task["args"]
    if dry_run:
        print(f"[DRY-RUN] {task['name']}: {script} {' '.join(args)}")
        return {"id": task["id"], "name": task["name"], "ok": True, "duration": 0}
    cmd = [sys.executable, str(WORKSPACE / script)] if script.endswith(".py") else [script] + args
    print(f"[RUN] {task['name']}: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True, timeout=300)
        ok = result.returncode == 0
        if not ok:
            print(f"[WARN] {task['name']} 返回非零: {result.returncode}")
    except Exception as e:
        print(f"[ERROR] {task['name']}: {e}")
        ok = False
    duration = time.time() - start
    return {"id": task["id"], "name": task["name"], "ok": ok, "duration": round(duration, 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description="每日仓库维护综合窗口")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    parser.add_argument("--task", choices=["hardcode", "worktree", "branch", "ssot"], help="仅执行单个任务")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== 每日仓库维护窗口 {datetime.now(timezone.utc).isoformat()} ===")
    tasks = [t for t in TASKS if t["id"] == args.task] if args.task else TASKS
    results = [run_task(t, dry_run=args.dry_run) for t in tasks]

    print("\n=== 执行摘要 ===")
    all_ok = True
    for r in results:
        status = "✅" if r["ok"] else "❌"
        print(f"  {status} {r['name']}: {r['duration']}s")
        if not r["ok"]:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
