#!/usr/bin/env python3
"""Check freshness staleness of all debt items.

Categorizes items by how stale their x2_freshness is:
- FRESH: < 7 days
- STALE: 7-30 days
- ANCIENT: > 30 days or empty

Exit code: 0 = all fresh/stale clean, 1 = ancient items found
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src/ to path so the package is importable from the repo root
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from omo.omo_debt_registry import load_debt_ledger


def _now():
    return datetime.now(timezone.utc)


def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check freshness staleness of all debt items."
    )
    parser.add_argument(
        "--omo-dir",
        default=".omo",
        help="Path to .omo directory (default: .omo)",
    )
    parser.add_argument(
        "--output",
        default=".omo/reports/freshness-report-latest.md",
        help="Path to output report (default: .omo/reports/freshness-report-latest.md)",
    )
    args = parser.parse_args()

    omo_dir = Path(args.omo_dir)
    ledger = load_debt_ledger(omo_dir)
    now = _now()

    fresh: list = []
    stale: list = []
    ancient: list = []

    for item in ledger.items:
        if not item.x2_freshness:
            ancient.append((item, "no timestamp"))
            continue
        ts = _parse_ts(item.x2_freshness)
        if ts is None:
            ancient.append((item, f"invalid: {item.x2_freshness}"))
            continue
        days = (now - ts).days
        if days < 7:
            fresh.append((item, days))
        elif days < 30:
            stale.append((item, days))
        else:
            ancient.append((item, f"{days}d"))

    # Generate report
    report = f"# Freshness Report\n\nGenerated: {now.isoformat()}\n\n"
    report += "## Summary\n\n| Category | Count |\n|----------|-------|\n"
    report += f"| 🟢 FRESH (<7d) | {len(fresh)} |\n"
    report += f"| 🟡 STALE (7-30d) | {len(stale)} |\n"
    report += f"| 🔴 ANCIENT (>30d/missing) | {len(ancient)} |\n"
    report += f"| **Total** | {len(fresh) + len(stale) + len(ancient)} |\n\n"

    if fresh:
        report += "## Fresh Items\n\n| ID | Title | Status | Age (days) |\n|----|-------|--------|------------|\n"
        for item, days in fresh:
            report += f"| {item.id} | {item.title} | {item.lifecycle_state} | {days} |\n"
        report += "\n"

    if stale:
        report += "## Stale Items\n\n| ID | Title | Status | Age (days) |\n|----|-------|--------|------------|\n"
        for item, days in stale:
            report += f"| {item.id} | {item.title} | {item.lifecycle_state} | {days} |\n"
        report += "\n"

    if ancient:
        report += "## Ancient Items\n\n| ID | Title | Status | Reason |\n|----|-------|--------|--------|\n"
        for item, reason in ancient:
            report += f"| {item.id} | {item.title} | {item.lifecycle_state} | {reason} |\n"
        report += "\n"

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)

    if ancient:
        print(f"\n⚠️  Found {len(ancient)} ancient items — returning exit code 1")
        return 1

    print("\n✅ All items fresh or stale clean — returning exit code 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
