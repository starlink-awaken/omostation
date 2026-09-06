#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 分支 TTL 过期清理 — 封装器.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BRANCH_PRUNE = WORKSPACE / "bin/gac/gac-branch-prune.sh"


def main() -> int:
    parser = argparse.ArgumentParser(description="分支 TTL 过期清理")
    parser.add_argument("--enforce", action="store_true", help="实际执行清理 (默认 dry-run)")
    parser.add_argument("--ttl-hours", type=int, default=168, help="超过此小时数的分支标记为过期 (默认 7 天)")
    args = parser.parse_args()

    cmd = ["bash", str(BRANCH_PRUNE)]
    if not args.enforce:
        cmd.append("--dry-run")

    print(f"[branch-ttl-gate] 执行: PASW_TTL_HOURS={args.ttl_hours} {' '.join(cmd)}")
    env = os.environ.copy()
    env["PASW_TTL_HOURS"] = str(args.ttl_hours)
    result = subprocess.run(cmd, cwd=str(WORKSPACE), env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
