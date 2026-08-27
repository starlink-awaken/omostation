#!/usr/bin/env python3
"""Resolve unmerged conflict markers in committed files.

For .md files in .omo/_knowledge/retros/: keep the first non-conflict block.
For .jsonl files: drop conflict lines.
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/xiamingxing/Workspace")


def resolve_markdown(path: Path) -> bool:
    """For each conflict region, take the HEAD (ours) side.

    Handles nested conflict markers (<<<<<  / |||||||  / =======  / >>>>>>>  /
    and re-conflicts during a rebase). Iteratively removes from the deepest
    outward so a triple-nested conflict collapses cleanly. Ensures the
    closing `---` of any frontmatter is preserved.
    """
    text = path.read_text(encoding="utf-8")
    if "<<<<<<< " not in text and "||||||| " not in text:
        # Even without conflict markers, may need to repair a missing closing ---
        return _ensure_closing_frontmatter(path, text)

    # Iteratively strip all conflict regions
    # First pass: remove any orphan ||||||| blocks (no matching <<<<<<<)
    lines = text.split("\n")
    text = "\n".join(strip_baselines(lines))

    if "<<<<<<< " not in text:
        text = _ensure_closing_frontmatter_text(text)
        path.write_text(text, encoding="utf-8")
        return True

    for _ in range(10):  # bounded loop to avoid infinite re-entry
        lines = text.split("\n")
        out = []
        i = 0
        resolved_any = False
        while i < len(lines):
            line = lines[i]
            if line.startswith("<<<<<<< "):
                # Find matching ======= at SAME depth (skip ||||||| blocks)
                sep_idx = None
                j = i + 1
                while j < len(lines):
                    if lines[j] == "=======":
                        sep_idx = j
                        break
                    j += 1
                if sep_idx is None:
                    # Malformed — keep as-is, advance
                    out.append(line)
                    i += 1
                    continue
                # Find matching >>>>>>> at SAME depth
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
                # Ours side: lines[i+1..sep_idx], skipping any ||||||| + inner conflicts
                ours_block = lines[i + 1 : sep_idx]
                # Strip any nested ||||||| sections inside ours
                clean_ours = strip_baselines(ours_block)
                out.extend(clean_ours)
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


def strip_baselines(lines: list[str]) -> list[str]:
    """Remove ||||||| baseline markers (used in recursive merges).

    Strips any leading ||||||| section that has no preceding <<<<<<<,
    plus any ||||||| section that DOES have a preceding <<<<<<< (handled
    by the outer pass).
    """
    out = []
    skip = False
    for line in lines:
        if line.startswith("||||||| "):
            skip = True
            continue
        if skip:
            if line.startswith("<<<<<<< "):
                # Re-entered a nested conflict: stop skipping
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


def _ensure_closing_frontmatter(path: Path, text: str) -> bool:
    """Return True if the file was repaired."""
    new_text = _ensure_closing_frontmatter_text(text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def resolve_jsonl(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "<<<<<<< " not in text:
        return False
    new_lines = []
    skip = False
    for line in text.split("\n"):
        if line.startswith("<<<<<<< "):
            skip = True
            continue
        if skip:
            if line.startswith(">>>>>>> "):
                skip = False
            continue
        if not skip:
            new_lines.append(line)
    path.write_text("\n".join(new_lines), encoding="utf-8")
    return True


def main():
    fixed = 0
    for p in ROOT.rglob("*.md"):
        if ".omo/_knowledge" in str(p) and resolve_markdown(p):
            fixed += 1
            print(f"  fixed md: {p.relative_to(ROOT)}")
    for p in ROOT.rglob("*.jsonl"):
        if ".omo/_knowledge" in str(p) and resolve_jsonl(p):
            fixed += 1
            print(f"  fixed jsonl: {p.relative_to(ROOT)}")
    print(f"Total fixed: {fixed}")


if __name__ == "__main__":
    main()
