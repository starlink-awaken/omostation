#!/usr/bin/env python3
"""Dormant 代码扫描器 — 识别并建议归档 dormant 模块."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")

SCAN_TARGETS = [
    "projects/agora/projects/agent-cell/",
    "projects/omo/src/omo/resident/",
]

DORMANT_DAYS = 180


def _last_commit(path: Path) -> datetime | None:
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


def scan_dormant() -> list[dict]:
    dormant = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DORMANT_DAYS)

    for target in SCAN_TARGETS:
        base = REPO / target
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
            dormant.append({
                "path": str(path.relative_to(REPO)),
                "last_commit": last_commit.isoformat(),
                "days_ago": (now - last_commit).days,
                "references": refs,
                "should_archive": refs == 0,
            })

    return sorted(dormant, key=lambda x: x["days_ago"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dormant 代码扫描器")
    parser.add_argument("--scan", action="store_true", help="Scan")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    if args.scan or args.report:
        dormant = scan_dormant()
        if not dormant:
            print("未发现 dormant 代码")
            return 0

        should_archive = [d for d in dormant if d["should_archive"]]
        print(f"Dormant 代码扫描: {len(dormant)} 发现, {len(should_archive)} 建议归档")
        for d in should_archive[:20]:
            print(f"  📦 {d['path']} ({d['days_ago']}天前, {d['references']}引用)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
