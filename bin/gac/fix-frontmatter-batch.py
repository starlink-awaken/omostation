#!/usr/bin/env python3
"""Fix .omo frontmatter: map invalid status values to valid set + fill missing lifecycle/owner.

Run from workspace root. Edits files in-place.
"""

import re
import sys
from pathlib import Path

# Map invalid status values to valid set (per doc-governance-check.py:['active','archived','deprecated','draft','experimental','planned','stale','superseded'])
STATUS_MAP = {
    "accepted": "archived",
    "blocked": "stale",
    "candidate": "planned",
    "ready_for_human": "active",
    "in_progress": "active",
    "completed": "archived",
    "in-review": "planned",
    "superseded": "superseded",  # keep
    "deprecated": "deprecated",  # keep
}

# Per-folder lifecycle map (lifecycle must be in: contract, entry, generated, history, pattern, plan, spec, ssot)
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

# Allow CLI override so this script works inside worktrees
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/xiamingxing/Workspace")


def fix_file(path: Path) -> bool:
    """Return True if file was modified."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False

    # Extract frontmatter
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return False
    frontmatter = m.group(1)
    body = text[m.end():]

    lines = frontmatter.split("\n")
    new_lines = []
    has_status = False
    has_lifecycle = False
    has_owner = False
    status_value = None
    modified = False

    for line in lines:
        if re.match(r"^status:\s*", line):
            has_status = True
            m2 = re.match(r"^status:\s*(\S+)", line)
            if m2:
                status_value = m2.group(1)
                if status_value in STATUS_MAP:
                    new_value = STATUS_MAP[status_value]
                    if new_value != status_value:
                        line = f"status: {new_value}"
                        modified = True
        elif re.match(r"^lifecycle:\s*", line):
            has_lifecycle = True
            m3 = re.match(r"^lifecycle:\s*(\S+)", line)
            if m3:
                cur_lifecycle = m3.group(1)
                parent = path.parent.name
                target_lifecycle = LIFECYCLE_BY_PATH.get(parent, "history")
                if cur_lifecycle != target_lifecycle:
                    line = f"lifecycle: {target_lifecycle}"
                    modified = True
        elif re.match(r"^owner:\s*", line):
            has_owner = True
        new_lines.append(line)

    # Fill missing required fields
    if not has_lifecycle:
        # Pick the right lifecycle based on the parent directory
        parent = path.parent.name
        lifecycle = LIFECYCLE_BY_PATH.get(parent, "history")
        new_lines.append(f"lifecycle: {lifecycle}")
        modified = True
    if not has_owner:
        new_lines.append("owner: unassigned")
        modified = True

    if not modified:
        return False

    new_text = "---\n" + "\n".join(new_lines) + "\n---\n" + body
    path.write_text(new_text, encoding="utf-8")
    return True


def main():
    fixed = 0
    # Find all .md files in .omo/_knowledge with frontmatter issues
    targets = [
        ROOT / ".omo" / "_knowledge" / "plans",
        ROOT / ".omo" / "_knowledge" / "retros",
        ROOT / ".omo" / "_knowledge" / "audits",
        ROOT / ".omo" / "_knowledge" / "summaries",
        ROOT / ".omo" / "_knowledge" / "decisions",
    ]
    for target in targets:
        if not target.exists():
            continue
        for p in target.rglob("*.md"):
            if fix_file(p):
                fixed += 1
    print(f"Fixed {fixed} files")


if __name__ == "__main__":
    main()
