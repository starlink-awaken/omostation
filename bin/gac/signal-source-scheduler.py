#!/usr/bin/env python3
"""信号源调度器 — 定时扫描日历/ inbox 并路由到场景卡。

用法:
    python3 bin/gac/signal-source-scheduler.py --calendar events.ics
    python3 bin/gac/signal-source-scheduler.py --inbox ./incoming/
    python3 bin/gac/signal-source-scheduler.py --all  # 扫描所有已知源
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIGNAL_ROUTER = REPO / "bin" / "bc-os" / "signal_router.py"
DEFAULT_INBOX = REPO / ".omo" / "_delivery" / "personal-signals" / "inbox"
CALENDAR_DIR = REPO / ".omo" / "_delivery" / "personal-signals" / "calendars"


def run_calendar(calendar_path: Path) -> dict:
    """扫描日历文件并路由。"""
    if not calendar_path.exists():
        return {"error": f"calendar not found: {calendar_path}", "routed": 0}
    result = subprocess.run(
        [sys.executable, str(SIGNAL_ROUTER), "--calendar", str(calendar_path), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        return {"error": result.stderr, "routed": 0}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "parse error", "routed": 0}


def run_inbox(inbox_path: Path) -> dict:
    """扫描 inbox 文件夹并路由。"""
    if not inbox_path.exists():
        return {"error": f"inbox not found: {inbox_path}", "routed": 0}
    result = subprocess.run(
        [sys.executable, str(SIGNAL_ROUTER), "--inbox", str(inbox_path), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        return {"error": result.stderr, "routed": 0}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "parse error", "routed": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="信号源调度器")
    parser.add_argument("--calendar", type=Path, help="Path to .ics calendar file")
    parser.add_argument("--inbox", type=Path, help="Path to inbox folder")
    parser.add_argument("--all", action="store_true", help="Scan all known sources")
    args = parser.parse_args()

    results = {}
    total_routed = 0

    if args.calendar or args.all:
        cal_path = args.calendar or (CALENDAR_DIR / "events.ics")
        if cal_path.exists() or args.calendar:
            r = run_calendar(cal_path)
            results["calendar"] = r
            total_routed += r.get("summary", {}).get("total_routed", 0)

    if args.inbox or args.all:
        inbox_path = args.inbox or DEFAULT_INBOX
        if inbox_path.exists() or args.inbox:
            r = run_inbox(inbox_path)
            results["inbox"] = r
            total_routed += r.get("summary", {}).get("total_routed", 0)

    results["total_routed"] = total_routed
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
