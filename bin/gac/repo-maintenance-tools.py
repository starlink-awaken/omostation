#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 仓库维护工具集.
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
    p1 = sub.add_parser("prune-zombie-worktrees")
    p1.add_argument("--apply", action="store_true")
    p1.add_argument("--stale-hours", type=int, default=72)
    p2 = sub.add_parser("branch-ttl-gate")
    p2.add_argument("--enforce", action="store_true")
    p2.add_argument("--ttl-hours", type=int, default=168)
    p3 = sub.add_parser("check-readme-hardcoded")
    p3.add_argument("--json", action="store_true")
    p4 = sub.add_parser("repo-health-metrics")
    p4.add_argument("--json", action="store_true")
    p4.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    tool = TOOL_MAP[args.tool]
    cmd = [sys.executable, str(WORKSPACE / tool["script"])] if tool["script"].endswith(".py") else ["bash", str(WORKSPACE / tool["script"])]
    cmd.extend(tool["args"](args))
    print(f"[{args.tool}] 执行: {' '.join(cmd)}")
    env = os.environ.copy()
    if "env" in tool:
        env.update(tool["env"](args))
    result = subprocess.run(cmd, cwd=str(WORKSPACE), env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
