#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 僵尸 Worktree 清理 — 封装器.
"""
import argparse
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SWARM_PRUNE = WORKSPACE / "bin/gac/swarm-prune-zombies.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="僵尸 Worktree 清理")
    parser.add_argument("--apply", action="store_true", help="实际执行清理 (默认 dry-run)")
    parser.add_argument("--stale-hours", type=int, default=72, help="超过此小时数的 run 标记为僵尸")
    args = parser.parse_args()

    cmd = [sys.executable, str(SWARM_PRUNE)]
    if args.apply:
        cmd.append("--apply")
    else:
        cmd.append("--dry-run")
    cmd.extend(["--stale-hours", str(args.stale_hours)])

    print(f"[prune-zombie-worktrees] 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(WORKSPACE))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
