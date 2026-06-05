#!/usr/bin/env python3
"""OMO standard CLI — list and show standards/ documents."""
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


def cmd_standard_list(omo_dir: Path) -> int:
    base = omo_dir / "standards"
    if not base.exists():
        print("⚠️  standards/ directory not found")
        return 0
    files = sorted(base.iterdir())
    md_files = [f for f in files if f.suffix == ".md"]
    yaml_files = [f for f in files if f.suffix in (".yaml", ".yml")]
    print(f"Standards: {len(md_files)} markdown, {len(yaml_files)} YAML")
    print()
    for f in md_files:
        print(f"  📄 {f.name}")
    for f in yaml_files:
        print(f"  📋 {f.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo standard", description="OMO standards browser")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List all standards")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_standard_list(omo_dir)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
