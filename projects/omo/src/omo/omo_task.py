#!/usr/bin/env python3
"""OMO task CLI — list and inspect tasks from .omo/tasks/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _find_omo_dir() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        omo = parent / ".omo"
        if omo.is_dir():
            return omo
    print("❌ .omo/ directory not found", file=sys.stderr)
    sys.exit(1)


def cmd_task_list(omo_dir: Path, status: str | None) -> int:
    """List tasks filtered by status directory."""
    if status:
        dirs = [omo_dir / "tasks" / status]
    else:
        dirs = [omo_dir / "tasks" / s for s in ("active", "planned", "done")]
    total = 0
    for d in dirs:
        if not d.exists():
            continue
        files = sorted(d.glob("*.yaml"))
        if not files:
            continue
        label = d.relative_to(omo_dir / "tasks")
        print(f"=== {label} ({len(files)} tasks) ===")
        for f in files[:20]:
            data = f.read_text().split("\n")[:3]
            tid = ""
            for line in data:
                if line.startswith("id:") or line.startswith("title:"):
                    tid += line.strip() + " "
            print(f"  {f.stem}: {tid[:60]}")
        if len(files) > 20:
            print(f"  ... and {len(files)-20} more")
        total += len(files)
    print(f"\nTotal: {total} tasks")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo task", description="OMO task browser")
    sub = parser.add_subparsers(dest="command")
    tl = sub.add_parser("list", help="List tasks")
    tl.add_argument("--status", "-s", choices=["active", "planned", "done"], help="Filter by status")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_task_list(omo_dir, args.status)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
