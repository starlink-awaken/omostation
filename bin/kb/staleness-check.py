#!/usr/bin/env python3
"""staleness-check — detect stale knowledge assets.

Phase 3 of the Knowledge Indexing plan. Checks:
  1. mtime age — file not touched in > 90 days
  2. Reference validity — bin/ refs that no longer exist
  3. Frontmatter last-reviewed — older than 90 days or missing

Usage:
  python3 bin/kb/staleness-check.py                # human output
  python3 bin/kb/staleness-check.py --json         # machine output
  python3 bin/kb/staleness-check.py --summary      # just the counts
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
BIN_REF_RE = re.compile(r"\b(bin/[a-z][a-z0-9_-]*/[A-Za-z0-9_./-]+\.(?:py|sh))\b")
STALE_DAYS = 90


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mtime_age_days(path: Path) -> float:
    try:
        mtime = path.stat().st_mtime
        return (time.time() - mtime) / 86400
    except OSError:
        return -1


def _last_reviewed_age_days(text: str) -> float | None:
    for line in text.splitlines()[:20]:
        match = re.search(r"last-reviewed:\s*['\"]?(\d{4}-\d{2}-\d{2})", line)
        if match:
            from datetime import UTC, datetime
            reviewed = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
            age = (datetime.now(UTC) - reviewed).days
            return float(age)
    return None


def _broken_bin_refs(root: Path, text: str) -> list[str]:
    broken = []
    for ref in BIN_REF_RE.findall(text):
        full = root / ref
        if "_archive" in ref or "_archived" in ref:
            continue
        if not full.exists():
            broken.append(ref)
    return broken


def check_file(root: Path, f: Path) -> dict[str, Any]:
    """Check a single knowledge asset for staleness."""
    text = _read(f)
    issues: list[str] = []

    age = _mtime_age_days(f)
    if age > STALE_DAYS:
        issues.append(f"mtime {age:.0f}d old (> {STALE_DAYS}d)")

    lr_age = _last_reviewed_age_days(text)
    if lr_age is None:
        issues.append("missing last-reviewed frontmatter")
    elif lr_age > STALE_DAYS:
        issues.append(f"last-reviewed {lr_age:.0f}d ago (> {STALE_DAYS}d)")

    broken_refs = _broken_bin_refs(root, text)
    for ref in broken_refs:
        issues.append(f"broken ref: {ref}")

    return {
        "path": str(f.relative_to(root)),
        "issues": issues,
        "issue_count": len(issues),
        "mtime_age_days": round(age, 1),
        "last_reviewed_age_days": round(lr_age, 1) if lr_age is not None else None,
        "broken_refs": broken_refs,
    }


def scan_targets(root: Path) -> list[Path]:
    """Yield all .md files worth checking."""
    targets: list[Path] = []
    for pattern_dir, pattern in [
        (root / "docs" / "operations", "*.md"),
        (root / ".omo" / "_knowledge" / "decisions", "*.md"),
        (root / ".agents" / "skills", "*/SKILL.md"),
        (root / "docs" / "scene-cards", "*.yaml"),
    ]:
        if pattern_dir.is_dir():
            targets.extend(sorted(pattern_dir.glob(pattern)))
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true", help="Just counts")
    parser.add_argument("--limit", type=int, default=30, help="Max items shown")
    args = parser.parse_args(argv)

    targets = scan_targets(WORKSPACE)

    results = []
    total_issues = 0
    stale_count = 0

    for f in targets:
        r = check_file(WORKSPACE, f)
        results.append(r)
        total_issues += r["issue_count"]
        if r["issue_count"] > 0:
            stale_count += 1

    summary = {
        "checked": len(results),
        "clean": len(results) - stale_count,
        "stale": stale_count,
        "total_issues": total_issues,
        "results": results if not args.summary else None,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.summary:
        print(f"checked={summary['checked']} clean={summary['clean']} stale={summary['stale']} total_issues={total_issues}")
    else:
        print("═══ Knowledge Staleness Check ═══")
        print(f"   checked: {summary['checked']}  clean: {summary['clean']}  stale: {summary['stale']}")
        print(f"   total issues: {total_issues}")
        print()
        shown = [r for r in results if r["issue_count"] > 0][:args.limit]
        for r in shown:
            print(f"  ⚠️  {r['path']} ({r['issue_count']} issues)")
            for issue in r["issues"][:3]:
                print(f"      {issue}")
            if len(r["issues"]) > 3:
                print(f"      ... and {len(r['issues']) - 3} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())