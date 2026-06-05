#!/usr/bin/env python3
"""OMO evidence CLI — list and inspect evidence documents from .omo/evidence/."""
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


def cmd_evidence_list(omo_dir: Path, category: str | None) -> int:
    """List evidence files."""
    base = omo_dir / "evidence"
    if not base.exists():
        print("⚠️  evidence/ directory not found")
        return 0
    targets = [base / category] if category else [base]
    total = 0
    for t in targets:
        if not t.exists():
            continue
        for f in sorted(t.rglob("*")):
            if f.is_file():
                size = f.stat().st_size
                rel = f.relative_to(base)
                print(f"  {rel}  ({size:,} bytes)")
                total += 1
    print(f"\nTotal: {total} evidence files")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo evidence", description="OMO evidence browser")
    sub = parser.add_subparsers(dest="command")
    el = sub.add_parser("list", help="List evidence files")
    el.add_argument("--category", "-c", help="Filter by category (divergence/phase15)")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_evidence_list(omo_dir, args.category)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
