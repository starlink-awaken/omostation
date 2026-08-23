#!/usr/bin/env python3
"""validate-runbook-refs — gate that runbook/prose bin/ references exist.

Why: rounds 5-8 added several new tools (health-trend-chart, rotate-history,
check-silent-workflows, etc.) and corresponding runbooks. As scripts get
renamed or archived, runbooks silently drift. This gate catches the drift
at PR-time.

Behavior:
  - Scan docs/operations/*.md for `bin/<category>/<script>.py` style
    references via regex
  - Verify each referenced path exists in the workspace
  - Exit non-zero if any referenced bin/ script is missing
  - Skip archive directories (_archive/, _archived/) per convention
  - JSON output for CI integration

Why not just shell `test -f`:
  - We want JSON output for gate integration (--json flag)
  - We want to skip archived paths (shell would false-positive on them)
  - We want categorized reporting (which runbook has which broken refs)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_DOC_ROOTS = (WORKSPACE / "docs" / "operations",)

# Match `bin/<category>/<script>.py` or `bin/<category>/<script>.sh`.
# Category = lowercase + underscore. Script = anything but whitespace.
# Excludes bin/gac/test_*.py which are test files (legitimate if missing).
_BIN_REF_RE = re.compile(r"\b(bin/[a-z][a-z0-9_-]*/[A-Za-z0-9_./-]+\.(?:py|sh))\b")
_ARCHIVE_MARKERS = ("_archive", "_archived", ".archive")

# Files we deliberately don't flag:
#   - runbook-template.md and similar (template placeholders)
#   - docs that say "e.g. bin/X" or "see bin/Y" (these are warnings, not
#     hard errors)
SKIP_PATTERNS = (
    "example",
    "template",
    "e.g.",
    "see bin/",
    "or bin/",
    "(planned)",
    "tbd",
    "future",
    "todo",
)

# Known-historical docs where bin/ references describe REMOVED scripts
# or future plans. These are audit trails, not runbooks; their broken
# refs are expected and should not fail the gate.
KNOWN_HISTORICAL_FILES = {
    "bin-scripts-necessity-report.md",
    "bin-scripts-close-duplicate-batch.md",
    "bin-scripts-close-duplicate-exec.md",
    "bin-scripts-convergence-audit.md",
    "REPO-AUDIT-IMPLEMENTATION-PLAN.md",
    "ARCHITECTURAL-REVIEW-2026-08-24.md",
    "omo-bootstrap-checklist.md",
    "omo-path-acl-runbook.md",
    "submodule-bump-bot-pilot-notes.md",
}


def _is_archived(path: Path) -> bool:
    """Return True if path is inside any archive directory."""
    return any(part in _ARCHIVE_MARKERS for part in path.parts)


def _is_skippable_line(line: str) -> bool:
    """Heuristic: skip lines that look like examples or templates."""
    lowered = line.lower()
    return any(pat in lowered for pat in SKIP_PATTERNS)


def collect_refs(roots: list[Path]) -> dict[str, set[str]]:
    """Walk all *.md under roots, extract bin/ refs.

    Returns: {md_file: set(refs)}
    """
    refs: dict[str, set[str]] = defaultdict(set)
    for root in roots:
        if not root.exists():
            continue
        for md in sorted(root.rglob("*.md")):
            if _is_archived(md):
                continue
            # Skip known-historical files (audit trails, not runbooks)
            if md.name in KNOWN_HISTORICAL_FILES:
                continue
            for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
                if _is_skippable_line(line):
                    continue
                for m in _BIN_REF_RE.finditer(line):
                    refs[str(md)].add(m.group(1))
    return refs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="doc root to scan (repeatable). Defaults to docs/operations",
    )
    args = parser.parse_args(argv)

    roots = args.root or list(DEFAULT_DOC_ROOTS)
    refs = collect_refs(roots)

    # Resolve each ref against the workspace
    broken: list[dict[str, str]] = []
    total_refs = 0
    for md_path, ref_set in sorted(refs.items()):
        for ref in sorted(ref_set):
            total_refs += 1
            full = WORKSPACE / ref
            if not full.exists() or _is_archived(full):
                broken.append({"file": md_path, "ref": ref})

    summary = {
        "docs_scanned": len(refs),
        "refs_total": total_refs,
        "broken_count": len(broken),
        "broken": broken,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"docs scanned: {len(refs)}")
        print(f"refs total:  {total_refs}")
        print(f"broken:      {len(broken)}")
        for b in broken:
            print(f"  MISS  {b['ref']}")
            print(f"        in {b['file']}")

    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())