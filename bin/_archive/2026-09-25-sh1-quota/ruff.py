#!/usr/bin/env python3
"""Run ruff's safe fix loop until diagnostics stabilize."""

import argparse
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--unsafe-fixes", action="store_true")
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def main() -> int:
    args = parse_args()
    base = ["uv", "run", "ruff", "check", str(args.path)]
    previous = ""
    for round_number in range(1, args.max_rounds + 1):
        command = [*base, "--fix"]
        if args.unsafe_fixes:
            command.append("--unsafe-fixes")
        fixed = run(command)
        checked = run(base)
        output = checked.stdout + checked.stderr
        print(f"round={round_number} returncode={checked.returncode}")
        if checked.returncode == 0:
            return 0
        if output == previous or fixed.returncode not in (0, 1):
            print(output, end="")
            return checked.returncode
        previous = output
    print(previous, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
