#!/usr/bin/env python3
"""C3 (ADR-0367): backfill missing/invalid `id: ADR-NNNN` frontmatter on historical ADRs.

Idempotent. Only touches the `id` line:
  - missing id  -> insert `id: ADR-NNNN` right after the opening `---`
  - mismatched id -> replace value with the canonical `ADR-NNNN`
Files without a YAML frontmatter (`---` first line) are skipped with a warning.

Usage:
  python3 bin/adr/adr-frontmatter-backfill.py [--dry-run] [--json] [--strict]

Modes:
  (default)         : idempotent — only writes when id missing or mismatched
  --strict          : exit 1 when any change would have been required (CI gate, D3 ADR-0373).
                       Same idempotent semantics, but treated as a merge blocker.
  --json            : emit machine-readable {changed, skipped, dry_run, strict}
  --dry-run         : never write (advisory preview)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _lib import list_adrs

DEFAULT_DIR = ".omo/_knowledge/decisions"
ID_LINE_RE = re.compile(r"^id:\s*(.*)$", re.MULTILINE)


def frontmatter_id(path: Path) -> str:
    """Extract `id:` value from the frontmatter block (regex only, no yaml dep)."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return ""
    for line in lines[1:]:
        if line == "---":
            break
        m = ID_LINE_RE.match(line)
        if m:
            return m.group(1).strip()
    return ""


def canonical_id(number: str) -> str:
    return f"ADR-{int(number):04d}"


def backfill(path: Path, number: str, dry_run: bool) -> str | None:
    """Return a human note when the file was (or would be) changed."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None  # 无 frontmatter, 跳过
    expected = canonical_id(str(number))
    current = frontmatter_id(path)

    if current and current.upper() == expected.upper():
        return None  # 已规范

    lines = text.split("\n")
    id_idx = None
    for idx, line in enumerate(lines[1:], start=1):
        if line == "---":
            break
        if id_idx is None and ID_LINE_RE.match(line):
            id_idx = idx
    if id_idx is not None:
        lines[id_idx] = f"id: {expected}"
    else:
        lines.insert(1, f"id: {expected}")

    rendered = "\n".join(lines)
    if rendered != text:
        if not dry_run:
            path.write_text(rendered, encoding="utf-8")
        return f"{path.name}: {current or '<missing>'} -> {expected}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="D3 (ADR-0373): ADR frontmatter id backfill + strict CI gate")
    parser.add_argument("--decisions", default=DEFAULT_DIR, help="ADR 目录")
    parser.add_argument("--dry-run", action="store_true", help="只报告不改写")
    parser.add_argument("--strict", action="store_true", help="CI 模式: 需要变更则 exit 1 (D3)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    decisions = Path(args.decisions)
    adrs = list_adrs(decisions)
    changed: list[str] = []
    skipped: list[str] = []
    for number, path in adrs:
        note = backfill(path, str(number), args.dry_run)
        if note:
            changed.append(note)
        elif not path.read_text(encoding="utf-8").startswith("---"):
            skipped.append(path.name)

    payload = {
        "dry_run": args.dry_run,
        "strict": args.strict,
        "changed": len(changed),
        "skipped_no_frontmatter": skipped,
        "files": changed,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for note in changed[:10]:
            print(note)
        if len(changed) > 10:
            print(f"... 还有 {len(changed) - 10} 个")
        print(
            f"changed={len(changed)} skipped_no_frontmatter={len(skipped)} "
            f"dry_run={args.dry_run} strict={args.strict}"
        )

    if args.strict and changed:
        # D3 (ADR-0373): CI 入口必须 exit 1 — 等价于阻断 gate
        if not args.json:
            print(f"❌ --strict: {len(changed)} 个 ADR 缺 id, 请先跑 backfill", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
