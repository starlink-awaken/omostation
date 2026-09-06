#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 仓库健康度量 — 封装器.
"""
import argparse
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
AUDIT_HEALTH = WORKSPACE / "bin/ssot/audit-repo-health.sh"


def main() -> int:
    parser = argparse.ArgumentParser(description="仓库健康度量")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--limit", type=int, default=5, help="每仓库最大 workflow 检查数")
    args = parser.parse_args()

    cmd = ["bash", str(AUDIT_HEALTH)]
    if args.json:
        cmd.append("--json")
    cmd.extend(["--limit", str(args.limit)])

    print(f"[repo-health-metrics] 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(WORKSPACE))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
