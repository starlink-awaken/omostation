#!/usr/bin/env python3
"""OMO evidence CLI — list and inspect evidence documents from OMO evidence storage."""
from __future__ import annotations

import argparse
from pathlib import Path

from .omo_paths import find_omo_dir


def _find_omo_dir() -> Path:
    return find_omo_dir()


def _has_files(path: Path) -> bool:
    return path.exists() and any(child.is_file() for child in path.rglob("*"))


def _evidence_base(omo_dir: Path, category: str | None = None) -> Path:
    modern = omo_dir / "_delivery" / "evidence"
    legacy = omo_dir / "_delivery" / "evidence-legacy"
    alias = omo_dir / "evidence"
    if category:
        if (modern / category).exists():
            return modern
        if (legacy / category).exists():
            return legacy
        if (alias / category).exists():
            return alias
    if _has_files(modern):
        return modern
    if _has_files(legacy):
        return legacy
    if modern.exists():
        return modern
    if legacy.exists():
        return legacy
    return alias


def cmd_evidence_list(omo_dir: Path, category: str | None) -> int:
    """List evidence files."""
    base = _evidence_base(omo_dir, category)
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
    mode = "modern" if base == (omo_dir / "_delivery" / "evidence") else "legacy-alias"
    print(f"\nBase: {base.relative_to(omo_dir)} [{mode}]")
    print(f"Total: {total} evidence files")
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
