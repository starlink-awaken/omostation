"""Chaos Drill Runner — orchestrates the 12-drill chaos governance suite.

Wrapper around chaos-governance-drill.py providing batched invocation,
per-drill filtering, and structured output for CI/CI integration.

This file exists to satisfy BET-Y1Q3-T10-120::write_surfaces contract.
The actual drill logic lives in bin/ssot/chaos-governance-drill.py.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DRILL_BIN = REPO_ROOT / "bin/ssot/chaos-governance-drill.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chaos drill runner (12 drills)")
    parser.add_argument("--strict", action="store_true",
                         help="Exit non-zero on any drill failure")
    parser.add_argument("--json", action="store_true",
                         help="Machine-readable JSON output")
    parser.add_argument("--drill", type=int, default=None,
                         help="Run only drill N (1-12)")
    args = parser.parse_args(argv)

    cmd = [sys.executable, str(DRILL_BIN)]
    if args.strict:
        cmd.append("--strict")
    if args.json:
        cmd.append("--json")

    if args.drill is not None:
        # Forward only specified drill via env var (drill script reads CHS_DRILL_INDEX)
        import os
        os.environ["CHS_DRILL_INDEX"] = str(args.drill)
        cmd.append("--drill")
        cmd.append(str(args.drill))

    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
