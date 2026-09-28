#!/usr/bin/env python3
"""FM Schema Migration Script v2 — migrate .omo/_knowledge/ .md files to md/v1 standard.

Uses regex to reliably match FM blocks, avoiding split("---") bugs.

Usage:
    python bin/ssot/fm_schema_migrate.py --dry-run          # Preview changes
    python bin/ssot/fm_schema_migrate.py --apply            # Apply changes
    python bin/ssot/fm_schema_migrate.py --subdir decisions # Limit to subdirectory
    python bin/ssot/fm_schema_migrate.py --skip-archived    # Skip archived files
"""
import argparse
import os
import re
import sys
from pathlib import Path
from datetime import date

# Regex to match FM block: starts with ---, ends with ---, non-greedy
FM_PATTERN = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)

def parse_fm(content: str) -> dict:
    """Parse frontmatter from content using regex."""
    match = FM_PATTERN.match(content)
    if not match:
        return {}
    fm_text = match.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm

def has_fm(content: str) -> bool:
    """Check if content has a frontmatter block."""
    return bool(FM_PATTERN.match(content))

def infer_type(filepath: str, content: str) -> str:
    path_lower = filepath.lower()
    if "adr" in path_lower or "decision" in path_lower:
        return "ssot"
    if "pattern" in path_lower:
        return "pattern"
    if "retro" in path_lower:
        return "retrospective"
    if "audit" in path_lower:
        return "audit"
    if "plan" in path_lower or "design" in path_lower:
        return "plan"
    if "pitfall" in path_lower:
        return "pitfall"
    if "summary" in path_lower:
        return "summary"
    if "spec" in path_lower:
        return "spec"
    if "review" in path_lower:
        return "review"
    if "analysis" in path_lower:
        return "analysis"
    if "roadmap" in path_lower:
        return "roadmap"
    if "index" in path_lower:
        return "documentation"
    return "documentation"

def infer_lifecycle(status: str) -> str:
    mapping = {
        "active": "entry",
        "accepted": "contract",
        "ACCEPTED": "contract",
        "superseded": "history",
        "archived": "history",
        "draft": "planning",
        "DEPRECATED": "history",
    }
    return mapping.get(status, "entry")

def infer_owner(content: str) -> str:
    if "夏明星" in content:
        return "夏明星"
    if "governance-team" in content:
        return "governance-team"
    if "product-architecture" in content:
        return "product-architecture"
    if "kems-team" in content:
        return "kems-team"
    return "governance-team"

def generate_fm(filepath: str, content: str, existing_fm: dict) -> str:
    """Generate md/v1 frontmatter."""
    status = existing_fm.get("status", "active")
    if status == "ACCEPTED":
        status = "accepted"
    elif status == "DEPRECATED":
        status = "archived"

    lifecycle = existing_fm.get("lifecycle", infer_lifecycle(status))
    if lifecycle == "plan":
        lifecycle = "planning"

    owner = existing_fm.get("owner", infer_owner(content))
    doc_type = existing_fm.get("type", infer_type(filepath, content))
    last_reviewed = existing_fm.get("last-reviewed", existing_fm.get("last_updated", str(date.today())))

    fm_lines = [
        "---",
        "schema: md/v1",
        f"status: {status}",
        f"lifecycle: {lifecycle}",
        f"owner: {owner}",
        f"type: {doc_type}",
        f"last-reviewed: {last_reviewed}",
    ]

    for key in ["title", "related", "created", "updated", "last_updated", "bet_id", "id"]:
        if key in existing_fm:
            fm_lines.append(f"{key}: {existing_fm[key]}")

    fm_lines.append("---")
    return "\n".join(fm_lines)

def replace_fm(content: str, new_fm: str) -> str:
    """Replace existing FM or prepend new FM."""
    match = FM_PATTERN.match(content)
    if match:
        # Replace existing FM
        return new_fm + "\n" + content[match.end():].lstrip("\n")
    else:
        # Prepend new FM
        return new_fm + "\n" + content

def main():
    parser = argparse.ArgumentParser(description="FM Schema Migration v2")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--subdir", type=str, help="Limit to subdirectory")
    parser.add_argument("--skip-archived", action="store_true", help="Skip archived files")
    args = parser.parse_args()

    knowledge_dir = Path(".omo/_knowledge")
    if args.subdir:
        knowledge_dir = knowledge_dir / args.subdir

    if not knowledge_dir.exists():
        print(f"Directory not found: {knowledge_dir}")
        sys.exit(1)

    md_files = list(knowledge_dir.rglob("*.md"))
    print(f"Found {len(md_files)} .md files in {knowledge_dir}")

    no_schema = []
    has_md_v1 = []
    has_other_schema = []

    for f in md_files:
        content = f.read_text(encoding="utf-8")
        fm = parse_fm(content)
        schema = fm.get("schema", "")

        if not schema:
            if args.skip_archived and fm.get("status") == "archived":
                continue
            no_schema.append(f)
        elif schema == "md/v1":
            has_md_v1.append(f)
        else:
            has_other_schema.append(f)

    print(f"\n=== FM Schema Distribution ===")
    print(f"  No schema:    {len(no_schema)}")
    print(f"  md/v1:        {len(has_md_v1)}")
    print(f"  Other schema: {len(has_other_schema)}")

    if has_other_schema:
        print(f"\n=== Other Schema Variants ===")
        variant_counts = {}
        for f in has_other_schema:
            content = f.read_text(encoding="utf-8")
            fm = parse_fm(content)
            schema = fm.get("schema", "unknown")
            variant_counts[schema] = variant_counts.get(schema, 0) + 1
        for schema, count in sorted(variant_counts.items(), key=lambda x: -x[1]):
            print(f"  {schema}: {count}")

    if no_schema:
        print(f"\n=== Migration Preview (first 5 no-schema files) ===")
        for f in no_schema[:5]:
            content = f.read_text(encoding="utf-8")
            fm = parse_fm(content)
            new_fm = generate_fm(str(f), content, fm)
            print(f"\n--- {f} ---")
            print(f"  Current FM keys: {list(fm.keys()) if fm else '(none)'}")
            print(f"  New FM: {new_fm[:150]}...")

    if args.apply and no_schema:
        print(f"\n=== Applying Migration to {len(no_schema)} files ===")
        migrated = 0
        for f in no_schema:
            content = f.read_text(encoding="utf-8")
            fm = parse_fm(content)
            new_fm = generate_fm(str(f), content, fm)
            new_content = replace_fm(content, new_fm)
            f.write_text(new_content, encoding="utf-8")
            migrated += 1
        print(f"  Migrated {migrated} files")
    elif args.apply and not no_schema:
        print("\nNo files to migrate.")

    print("\nDone.")

if __name__ == "__main__":
    main()
