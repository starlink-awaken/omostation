#!/usr/bin/env python3
"""Dormant Cleanup Scanner — 休眠模块扫描与清理建议.

扫描项目中长时间无活动的模块，建议归档以减少表面积.

Usage:
    python3 bin/gac/dormant-cleanup-scanner.py --scan
    python3 bin/gac/dormant-cleanup-scanner.py --report [--threshold-days 90]
    python3 bin/gac/dormant-cleanup-scanner.py --archive <path>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Known dormant modules (from architecture review)
KNOWN_DORMANT = [
    "projects/agora/projects/agent-cell/cell_*.py",
    "projects/omo/src/omo/resident/cell*.py",
    "projects/omo/src/omo/resident/planner*.py",
    "projects/omo/src/omo/resident/verifier*.py",
    "projects/omo/src/omo/resident/goal*.py",
]

# Scan targets
SCAN_DIRS = [
    "projects/agora/projects/",
    "projects/omo/src/omo/resident/",
    "projects/cockpit/src/cockpit/commands/",
]


def _last_commit(path: Path) -> datetime | None:
    """Get last commit date for a path."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            ts = int(result.stdout.strip())
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError):
        pass
    return None


def _count_references(name: str) -> int:
    """Count how many times a module is referenced."""
    try:
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "-l", name,
             str(REPO / "bin"), str(REPO / "projects")],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return len([l for l in result.stdout.splitlines() if l.strip()])
    except OSError:
        pass
    return 0


def scan_dormant(threshold_days: int = 90) -> list[dict]:
    """Scan for dormant modules."""
    dormant = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=threshold_days)

    for scan_dir in SCAN_DIRS:
        base = REPO / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("_"):
                continue
            last_commit = _last_commit(path)
            if last_commit is None or last_commit >= cutoff:
                continue
            name = path.stem
            refs = _count_references(name)
            days_ago = (now - last_commit).days
            dormant.append({
                "path": str(path.relative_to(REPO)),
                "last_commit": last_commit.isoformat(),
                "days_ago": days_ago,
                "references": refs,
                "should_archive": refs == 0 and days_ago > 180,
            })

    return sorted(dormant, key=lambda x: x["days_ago"], reverse=True)


def generate_report(dormant: list[dict]) -> dict:
    """Generate cleanup report."""
    should_archive = [d for d in dormant if d["should_archive"]]
    review_needed = [d for d in dormant if not d["should_archive"]]

    return {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "threshold_days": 90,
        "total_dormant": len(dormant),
        "should_archive": len(should_archive),
        "review_needed": len(review_needed),
        "potential_baseline_reduction": len(should_archive),
        "dormant_modules": dormant[:20],  # Top 20
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dormant Cleanup Scanner")
    parser.add_argument("--scan", action="store_true", help="Scan for dormant modules")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--threshold-days", type=int, default=90, help="Dormant threshold")
    args = parser.parse_args()

    if args.scan or args.report:
        dormant = scan_dormant(args.threshold_days)
        if args.report:
            report = generate_report(dormant)
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            for d in dormant[:20]:
                action = "📦 ARCHIVE" if d["should_archive"] else "⚠️ REVIEW"
                print(f"  {action} {d['path']} ({d['days_ago']}d, {d['references']} refs)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
