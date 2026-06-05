#!/usr/bin/env python3
"""OMO delivery CLI — list and view _delivery/ artifacts."""
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


def cmd_delivery_list(omo_dir: Path, phase: str | None) -> int:
    """List delivery artifacts, optionally filtered by phase prefix."""
    base = omo_dir / "_delivery"
    if not base.exists():
        print("⚠️  _delivery/ directory not found")
        return 0
    files = sorted(base.rglob("*")) if not phase else sorted(base.glob(f"{phase}*"))
    count = 0
    for f in files:
        if f.is_file() and f.suffix in (".md", ".json", ".yaml"):
            size = f.stat().st_size
            label = f.relative_to(base)
            print(f"  {label}  ({size:,} bytes)")
            count += 1
    print(f"\nTotal: {count} delivery artifacts")
    return 0


def cmd_delivery_archive(omo_dir: Path, phase_prefix: str) -> int:
    """Move old delivery artifacts to _archive/."""
    base = omo_dir / "_delivery"
    archive_dir = omo_dir / "_archive" / "delivery" / phase_prefix
    if not base.exists():
        print("⚠️  _delivery/ directory not found")
        return 0
    files = list(base.glob(f"{phase_prefix}*"))
    if not files:
        print(f"No delivery artifacts matching '{phase_prefix}'")
        return 0
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in files:
        if f.is_file():
            dest = archive_dir / f.name
            f.rename(dest)
            moved += 1
            print(f"  Archived: {f.name}")
    print(f"\nArchived {moved} artifacts to _archive/delivery/{phase_prefix}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo delivery", description="OMO delivery artifact browser")
    sub = parser.add_subparsers(dest="command")
    dl = sub.add_parser("list", help="List delivery artifacts")
    dl.add_argument("--phase", "-p", help="Filter by phase prefix (e.g. phase28)")
    da = sub.add_parser("archive", help="Archive old delivery artifacts")
    da.add_argument("--phase", "-p", required=True, help="Phase prefix to archive (e.g. phase27)")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_delivery_list(omo_dir, args.phase)
    elif args.command == "archive":
        return cmd_delivery_archive(omo_dir, args.phase)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
