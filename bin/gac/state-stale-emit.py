#!/usr/bin/env python3
"""Emit a state_stale event without refreshing runtime projections directly."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit OMO state_stale event")
    parser.add_argument("--source", default="state-stale-emit", help="Event source")
    parser.add_argument("--trigger", default="manual", help="Trigger reason")
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Changed source surface; may be passed multiple times",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    args = parser.parse_args()

    payload = {
        "trigger": args.trigger,
        "surfaces": args.surface,
        "recommended_sync": "uv run --project projects/omo omo state sync",
    }
    command = [
        "uv",
        "run",
        "--project",
        "projects/omo",
        "omo",
        "event",
        "emit",
        "--type",
        "state_stale",
        "--source",
        args.source,
        "--payload",
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    ]
    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if not args.quiet and result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
