#!/usr/bin/env python3
"""Batch Frontmatter - batch add frontmatter to submodule docs.

Usage:
    python3 bin/ssot/batch-frontmatter.py --scan
    python3 bin/ssot/batch-frontmatter.py --apply --dry-run
    python3 bin/ssot/batch-frontmatter.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".worktrees", "dist", "kos"}

TYPE_RULES = [
    (lambda p: p.name in ("AGENTS.md", "CLAUDE.md"), "ssot", "governance-team"),
    (lambda p: p.name == "README.md" and len(p.parts) > 2, "derived", "governance-team"),
    (lambda p: "tests/" in str(p), "ephemeral", "governance-team"),
    (lambda p: p.suffix == ".md", "ssot", "governance-team"),
]


def get_type_for_file(path: Path) -> tuple[str, str]:
    for predicate, doc_type, owner in TYPE_RULES:
        if predicate(path):
            return doc_type, owner
    return "ssot", "governance-team"


def scan_files() -> list[Path]:
    files = []
    projects_dir = REPO / "projects"
    if not projects_dir.exists():
        return files
    for submodule in sorted(projects_dir.iterdir()):
        if not submodule.is_dir() or submodule.name.startswith("."):
            continue
        for md in submodule.rglob("*.md"):
            if any(part in SKIP_DIRS for part in md.parts):
                continue
            try:
                content = md.read_text(encoding="utf-8", errors="replace")
                if content.startswith("---"):
                    continue
            except Exception:
                continue
            files.append(md)
    return files


def apply_frontmatter(files: list[Path], dry_run: bool = False) -> int:
    count = 0
    for md in files:
        doc_type, owner = get_type_for_file(md)
        content = md.read_text(encoding="utf-8", errors="replace")
        fm = f"""---
type: {doc_type}
owner: {owner}
last_updated: 2026-09-03
---

"""
        if not dry_run:
            md.write_text(fm + content, encoding="utf-8")
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Batch Frontmatter")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = scan_files()

    if args.scan or (not args.apply):
        print(f"Found {len(files)} files without frontmatter")
        by_submodule = {}
        for f in files:
            parts = f.relative_to(REPO).parts
            key = "/".join(parts[:2]) if len(parts) > 1 else str(f)
            by_submodule.setdefault(key, []).append(f)
        for sub, items in sorted(by_submodule.items()):
            print(f"  {sub}: {len(items)} files")
        return 0

    if args.apply:
        dry = args.dry_run
        count = apply_frontmatter(files, dry_run=dry)
        mode = "DRY RUN" if dry else "APPLIED"
        print(f"{mode}: Added frontmatter to {count} files")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
