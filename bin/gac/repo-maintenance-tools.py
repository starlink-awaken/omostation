#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 仓库维护工具集.

合并 4 个 wrapper 脚本为 1 个, 满足 bin-quota-diff 要求:
- prune-zombie-worktrees → swarm-prune-zombies.py
- branch-ttl-gate → gac-branch-prune.sh
- check-readme-hardcoded → hardcode-scan.py
- repo-health-metrics → audit-repo-health.sh
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

TOOL_MAP = {
    "prune-zombie-worktrees": {
        "script": "bin/gac/swarm-prune-zombies.py",
        "args": lambda args: (["--apply"] if args.apply else ["--dry-run"]) + ["--stale-hours", str(args.stale_hours)],
        "default_stale_hours": 72,
    },
    "branch-ttl-gate": {
        "script": "bin/gac/gac-branch-prune.sh",
        "args": lambda args: ([] if args.enforce else ["--dry-run"]),
        "env": lambda args: {"PASW_TTL_HOURS": str(args.ttl_hours)},
    },
    "check-readme-hardcoded": {
        "script": "bin/gac/hardcode-scan.py",
        "args": lambda args: ["--json"] if args.json else [],
    },
    "repo-health-metrics": {
        "script": "bin/ssot/audit-repo-health.sh",
        "args": lambda args: (["--json"] if args.json else []) + ["--limit", str(args.limit)],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="仓库维护工具集")
    sub = parser.add_subparsers(dest="tool", required=True)

    # prune-zombie-worktrees
    p1 = sub.add_parser("prune-zombie-worktrees", help="僵尸 Worktree 清理")
    p1.add_argument("--apply", action="store_true")
    p1.add_argument("--stale-hours", type=int, default=72)

    # branch-ttl-gate
    p2 = sub.add_parser("branch-ttl-gate", help="分支 TTL 清理")
    p2.add_argument("--enforce", action="store_true")
    p2.add_argument("--ttl-hours", type=int, default=168)

    # check-readme-hardcoded
    p3 = sub.add_parser("check-readme-hardcoded", help="硬编码检测")
    p3.add_argument("--json", action="store_true")

    # repo-health-metrics
    p4 = sub.add_parser("repo-health-metrics", help="健康度量")
    p4.add_argument("--json", action="store_true")
    p4.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    tool_name = args.tool
    tool = TOOL_MAP[tool_name]

    cmd = [sys.executable, str(WORKSPACE / tool["script"])] if tool["script"].endswith(".py") else ["bash", str(WORKSPACE / tool["script"])]
    cmd.extend(tool["args"](args))

    print(f"[{tool_name}] 执行: {' '.join(cmd)}")
    env = os.environ.copy()
    if "env" in tool:
        env.update(tool["env"](args))
    result = subprocess.run(cmd, cwd=str(WORKSPACE), env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
