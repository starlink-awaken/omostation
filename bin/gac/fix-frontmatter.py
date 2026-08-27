#!/usr/bin/env python3
"""fix-frontmatter: 自动为 Markdown 文档补齐合规 Frontmatter.

Modes:
  - Default (positional files): insert default frontmatter if file has none
  - --batch <root>: scan .omo/_knowledge under ROOT, fix all non-conformant
    docs (invalid status values, missing lifecycle/owner, malformed
    conflict markers, missing closing ---).
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

DEFAULT_FRONTMATTER = f"""---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
---
"""

# Map invalid status values to valid set (per doc-governance-check.py allowed set)
STATUS_MAP = {
    "accepted": "archived",
    "blocked": "stale",
    "candidate": "planned",
    "ready_for_human": "active",
    "in_progress": "active",
    "completed": "archived",
    "in-review": "planned",
    "superseded": "superseded",
    "deprecated": "deprecated",
}

# Per-folder lifecycle map (must be in: contract, entry, generated, history, pattern, plan, spec, ssot)
LIFECYCLE_BY_PATH = {
    "plans": "plan",
    "retros": "history",
    "audits": "history",
    "summaries": "history",
    "decisions": "spec",
    "patterns": "pattern",
    "specs": "spec",
    "contracts": "contract",
    "ssot": "ssot",
    "generated": "generated",
    "entries": "entry",
}


def fix_file(filepath: Path) -> bool:
    """Single-file mode: insert default frontmatter if missing."""
    if not filepath.exists() or not filepath.is_file() or filepath.suffix != ".md":
        return False
    content = filepath.read_text(encoding="utf-8")
    if content.lstrip().startswith("---"):
        return False
    new_content = DEFAULT_FRONTMATTER + "\n" + content
    filepath.write_text(new_content, encoding="utf-8")
    return True


def _strip_baselines(lines: list[str]) -> list[str]:
    """Remove orphan ||||||| baseline markers (used in recursive merges)."""
    out = []
    skip = False
    for line in lines:
        if line.startswith("||||||| "):
            skip = True
            continue
        if skip:
            if line.startswith("<<<<<<< "):
                skip = False
                out.append(line)
            else:
                continue
        out.append(line)
    return out


def _ensure_closing_frontmatter_text(text: str) -> str:
    """If the file starts with --- but has no closing ---, append one."""
    if text.startswith("---") and text.count("---") == 1:
        return text + "\n---\n"
    return text


def _repair_frontmatter_close(path: Path, text: str) -> bool:
    """Repair a file that has opening --- but no closing ---."""
    new_text = _ensure_closing_frontmatter_text(text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _resolve_conflicts(path: Path) -> bool:
    """Strip git conflict markers, take HEAD side, repair missing closing ---."""
    text = path.read_text(encoding="utf-8")
    if "<<<<<<< " not in text and "||||||| " not in text:
        return _repair_frontmatter_close(path, text)
    lines = text.split("\n")
    text = "\n".join(_strip_baselines(lines))
    if "<<<<<<< " not in text:
        text = _ensure_closing_frontmatter_text(text)
        path.write_text(text, encoding="utf-8")
        return True
    for _ in range(10):
        lines = text.split("\n")
        out = []
        i = 0
        resolved_any = False
        while i < len(lines):
            line = lines[i]
            if line.startswith("<<<<<<< "):
                sep_idx = None
                j = i + 1
                while j < len(lines):
                    if lines[j] == "=======":
                        sep_idx = j
                        break
                    j += 1
                if sep_idx is None:
                    out.append(line)
                    i += 1
                    continue
                theirs_idx = None
                j = sep_idx + 1
                while j < len(lines):
                    if lines[j].startswith(">>>>>>> "):
                        theirs_idx = j
                        break
                    j += 1
                if theirs_idx is None:
                    out.append(line)
                    i += 1
                    continue
                ours_block = lines[i + 1 : sep_idx]
                out.extend(_strip_baselines(ours_block))
                resolved_any = True
                i = theirs_idx + 1
            else:
                out.append(line)
                i += 1
        text = "\n".join(out)
        if not resolved_any:
            break
        if "<<<<<<< " not in text:
            break
    text = _ensure_closing_frontmatter_text(text)
    path.write_text(text, encoding="utf-8")
    return True


def _fix_frontmatter_fields(path: Path) -> bool:
    """Update invalid status / lifecycle fields per map. Fill missing required fields."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return _repair_frontmatter_close(path, text)
    frontmatter = m.group(1)
    body = text[m.end():]
    lines = frontmatter.split("\n")
    new_lines = []
    has_status = False
    has_lifecycle = False
    has_owner = False
    modified = False
    for line in lines:
        if re.match(r"^status:\s*", line):
            has_status = True
            m2 = re.match(r"^status:\s*(\S+)", line)
            if m2 and m2.group(1) in STATUS_MAP:
                new_value = STATUS_MAP[m2.group(1)]
                if new_value != m2.group(1):
                    line = f"status: {new_value}"
                    modified = True
        elif re.match(r"^lifecycle:\s*", line):
            has_lifecycle = True
            m3 = re.match(r"^lifecycle:\s*(\S+)", line)
            if m3:
                target = LIFECYCLE_BY_PATH.get(path.parent.name, "history")
                if m3.group(1) != target:
                    line = f"lifecycle: {target}"
                    modified = True
        elif re.match(r"^owner:\s*", line):
            has_owner = True
        new_lines.append(line)
    if not has_lifecycle:
        new_lines.append(f"lifecycle: {LIFECYCLE_BY_PATH.get(path.parent.name, 'history')}")
        modified = True
    if not has_owner:
        new_lines.append("owner: unassigned")
        modified = True
    if not modified:
        return False
    new_text = "---\n" + "\n".join(new_lines) + "\n---\n" + body
    path.write_text(new_text, encoding="utf-8")
    return True


def _batch_fix(root: Path) -> int:
    """Apply both conflict resolution and field fixes to all .md files in .omo/_knowledge."""
    fixed = 0
    targets = [
        root / ".omo" / "_knowledge" / "plans",
        root / ".omo" / "_knowledge" / "retros",
        root / ".omo" / "_knowledge" / "audits",
        root / ".omo" / "_knowledge" / "summaries",
        root / ".omo" / "_knowledge" / "decisions",
    ]
    for target in targets:
        if not target.exists():
            continue
        for p in target.rglob("*.md"):
            if _resolve_conflicts(p):
                fixed += 1
            if _fix_frontmatter_fields(p):
                fixed += 1
    return fixed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="Files to fix (single-file mode)")
    parser.add_argument("--batch", metavar="ROOT", help="Batch mode: scan .omo/_knowledge under ROOT")
    args = parser.parse_args()

    fixed = 0
    if args.batch:
        fixed = _batch_fix(Path(args.batch))
        print(f"Batch fixed {fixed} files")
        return 0 if fixed > 0 else 1
    if not args.files:
        print("No files specified", file=sys.stderr)
        return 1
    for f in args.files:
        if fix_file(Path(f)):
            fixed += 1
            print(f"Fixed: {f}")
    if fixed > 0:
        return 0
    print("No files fixed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
