#!/usr/bin/env python3
"""Bounded ruff fix loop with convergence check."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded ruff fix loop")
    parser.add_argument("path", nargs="?", default=".", help="Target path")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max fix rounds")
    parser.add_argument("--unsafe-fixes", action="store_true", help="Allow unsafe fixes")
    return parser.parse_args()


def run_ruff(path: Path, unsafe: bool) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "ruff", "check", str(path), "--fix"]
    if unsafe:
        cmd.append("--unsafe-fixes")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    args = parse_args()
    path = Path(args.path)

    for round_num in range(1, args.max_rounds + 1):
        code, output = run_ruff(path, args.unsafe_fixes)
        if code == 0:
            print(f"round={round_num} status=converged diagnostics=0")
            return 0
        if code != 1:
            print(f"round={round_num} status=error code={code}")
            return code

    code, output = run_ruff(path, args.unsafe_fixes)
    diagnostics = output.count("\n") if output else 0
    print(f"round={args.max_rounds} status=remaining diagnostics={diagnostics}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
