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


def cmd_standard_add(omo_dir: Path, title: str, content: str | None, stdin: bool) -> int:
    """Add a new standard document to standards/."""
    base = omo_dir / "standards"
    safe_name = title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:60] + ".md"
    std_file = base / safe_name
    if std_file.exists():
        print(f"❌ {safe_name} already exists", file=sys.stderr)
        return 1
    if stdin:
        content = sys.stdin.read()
    elif not content:
        print("❌ Provide content via --content or --stdin", file=sys.stderr)
        return 1
    std_file.write_text(f"# {title}\n\n{content}\n")
    print(f"✅ Created standards/{safe_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo standard", description="OMO standards browser")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List all standards")
    sa = sub.add_parser("add", help="Add a new standard")
    sa.add_argument("--title", "-t", required=True, help="Standard title")
    sa.add_argument("--content", "-c", help="Standard content")
    sa.add_argument("--stdin", action="store_true", help="Read content from stdin")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_standard_list(omo_dir)
    elif args.command == "add":
        return cmd_standard_add(omo_dir, args.title, args.content, args.stdin)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
