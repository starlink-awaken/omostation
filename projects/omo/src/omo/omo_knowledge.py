#!/usr/bin/env python3
"""OMO knowledge CLI — list and search _knowledge/ documents."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

OMO_HINT = ".omo"


def _find_omo_dir() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        omo = parent / OMO_HINT
        if omo.is_dir():
            return omo
    print("❌ .omo/ directory not found", file=sys.stderr)
    sys.exit(1)


def cmd_knowledge_list(omo_dir: Path, plane: str | None) -> int:
    """List knowledge documents, optionally filtered by sub-plane."""
    base = omo_dir / "_knowledge"
    if not base.exists():
        print("⚠️  _knowledge/ directory not found")
        return 0
    targets = [base / plane] if plane else [base]
    total = 0
    for t in targets:
        if not t.exists():
            print(f"⚠️  {t.name} not found")
            continue
        files = sorted(t.rglob("*.md")) if plane else sorted(t.iterdir())
        if not plane:
            print(f"\n=== {t.name} ===")
            for sub in sorted(t.iterdir()):
                if sub.is_dir():
                    count = len(list(sub.rglob("*.md")))
                    print(f"  {sub.name}/  ({count} files)")
            total += len(list(t.rglob("*.md")))
        else:
            for f in files:
                size = len(f.read_text().split("\n"))
                print(f"  {f.relative_to(base)}  ({size} lines)")
            total += len(files)
    print(f"\nTotal: {total} documents")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo knowledge", description="OMO knowledge document browser")
    sub = parser.add_subparsers(dest="command")
    kl = sub.add_parser("list", help="List knowledge documents")
    kl.add_argument("--plane", "-p", help="Filter by sub-plane (management/design/decisions/etc)")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_knowledge_list(omo_dir, args.plane)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
