#!/usr/bin/env python3
"""
机制 22d (2026-09-06): README 硬编码数据检测 — 封装器.
"""
import argparse
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HARDCODE_SCAN = WORKSPACE / "bin/gac/hardcode-scan.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="README 硬编码数据检测")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    cmd = [sys.executable, str(HARDCODE_SCAN)]
    if args.json:
        cmd.append("--json")

    print(f"[check-readme-hardcoded] 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(WORKSPACE))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
