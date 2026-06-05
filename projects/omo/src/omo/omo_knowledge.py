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


def cmd_knowledge_add(omo_dir: Path, plane: str, title: str, content: str | None, stdin: bool) -> int:
    """Add a document to _knowledge/{plane}/."""
    base = omo_dir / "_knowledge" / plane
    if not base.exists():
        base.mkdir(parents=True)
        print(f"  Created _knowledge/{plane}/")
    if stdin:
        content = sys.stdin.read()
    elif not content:
        print("❌ Provide content via --content or --stdin", file=sys.stderr)
        return 1
    # Create safe filename from title
    safe_name = title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:60]
    doc_file = base / f"{safe_name}.md"
    if doc_file.exists():
        print(f"❌ {doc_file.name} already exists", file=sys.stderr)
        return 1
    doc_file.write_text(f"# {title}\n\n{content}\n")
    print(f"✅ Created _knowledge/{plane}/{doc_file.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo knowledge", description="OMO knowledge document browser")
    sub = parser.add_subparsers(dest="command")
    kl = sub.add_parser("list", help="List knowledge documents")
    kl.add_argument("--plane", "-p", help="Filter by sub-plane (management/design/decisions/etc)")
    ka = sub.add_parser("add", help="Add a document to knowledge plane")
    ka.add_argument("--plane", "-p", required=True, help="Sub-plane name (e.g. decisions, design)")
    ka.add_argument("--title", "-t", required=True, help="Document title")
    ka.add_argument("--content", "-c", help="Document content (mutually exclusive with --stdin)")
    ka.add_argument("--stdin", action="store_true", help="Read content from stdin")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_knowledge_list(omo_dir, args.plane)
    elif args.command == "add":
        return cmd_knowledge_add(omo_dir, args.plane, args.title, args.content, args.stdin)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
