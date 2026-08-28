#!/usr/bin/env python3
"""
doc-auto-update.py — Detect stale documentation and generate update plans.

Scans docs/generated/ for files older than a configurable threshold (default 7 days)
and produces an update plan with recommended actions.

Usage:
  python3 bin/gac/doc-auto-update.py              # human-readable output
  python3 bin/gac/doc-auto-update.py --json        # JSON output
  python3 bin/gac/doc-auto-update.py --threshold 3 # custom threshold (days)

Exit codes:
  0 = all docs fresh
  1 = stale docs found
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATED_DOCS_DIR = REPO_ROOT / "docs" / "generated"
DEFAULT_STALE_THRESHOLD_DAYS = 7


def check_stale_docs(
    docs_dir: Path = GENERATED_DOCS_DIR,
    threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
    base_dir: Path = REPO_ROOT,
) -> list[dict]:
    """Scan *docs_dir* for files whose mtime is older than *threshold_days*.

    Returns a list of dicts, each with keys:
      - ``file``: relative path from *base_dir*
      - ``age_days``: integer age in days
    """
    if not docs_dir.exists():
        return []

    now = datetime.now(UTC)
    stale: list[dict] = []

    for path in sorted(docs_dir.iterdir()):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_days = (now - mtime).days
        if age_days >= threshold_days:
            stale.append(
                {
                    "file": str(path.relative_to(base_dir)),
                    "age_days": age_days,
                }
            )

    return stale


def generate_update_plan(stale_docs: list[dict]) -> list[dict]:
    """Turn a stale-docs list into an actionable update plan.

    Returns a list of dicts, each with keys:
      - ``file``: relative path
      - ``action``: recommended action string
      - ``reason``: human-readable justification
    """
    plan: list[dict] = []
    for entry in stale_docs:
        path = Path(entry["file"])
        age = entry["age_days"]
        suffix = path.suffix.lower()

        if suffix in (".yaml", ".yml", ".json"):
            action = "regenerate"
            reason = f"Data file is {age} days old; re-run the generator to refresh"
        elif suffix == ".md":
            action = "review-and-refresh"
            reason = f"Markdown doc is {age} days old; verify content still accurate then regenerate"
        else:
            action = "review"
            reason = f"File is {age} days old; manual review recommended"

        plan.append(
            {
                "file": entry["file"],
                "action": action,
                "reason": reason,
            }
        )

    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect stale documentation and generate update plans")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_STALE_THRESHOLD_DAYS,
        help=f"Stale threshold in days (default: {DEFAULT_STALE_THRESHOLD_DAYS})",
    )
    args = parser.parse_args()

    stale = check_stale_docs(threshold_days=args.threshold)
    plan = generate_update_plan(stale)

    if args.json_output:
        result = {
            "check": "doc_auto_update",
            "stale_count": len(stale),
            "stale_docs": stale,
            "update_plan": plan,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Documentation Auto-Update Detector")
        print("=" * 50)
        if stale:
            print(f"STALE: {len(stale)} file(s) older than {args.threshold} days\n")
            for item in stale:
                print(f"  - {item['file']}  ({item['age_days']}d old)")
            print("\nUpdate Plan:")
            for step in plan:
                print(f"  [{step['action']}] {step['file']}")
                print(f"    reason: {step['reason']}")
        else:
            print(f"PASS: All generated docs are fresh (< {args.threshold} days)")

    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
