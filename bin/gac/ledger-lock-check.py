#!/usr/bin/env python3
"""ledger-lock-check.py — CLI tool to check bet-ledger lock status.

Checks:
  - Lock file existence and validity
  - Lock holder identity (PID, hostname, operation)
  - Deadlock detection (lock held >60s)
  - Stale lock detection (lock held >120s and process dead)
  - Lock contention reporting

Usage:
    python3 bin/gac/ledger-lock-check.py              # Check status
    python3 bin/gac/ledger-lock-check.py --json        # JSON output
    python3 bin/gac/ledger-lock-check.py --break-stale # Force-break stale locks
    python3 bin/gac/ledger-lock-check.py --wait        # Wait for lock release
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS))

from lib.ledger_lock import (
    DEADLOCK_WARNING_S,
    LOCK_PATH,
    STALE_LOCK_S,
    LockInfo,
    break_stale_lock,
    read_lock_status,
)


def check_lock(*, as_json: bool = False, break_stale: bool = False, wait: bool = False) -> int:
    """Check lock status and report findings."""
    status = read_lock_status()

    if break_stale and status["stale"]:
        broken = break_stale_lock()
        if broken:
            if as_json:
                print(json.dumps({"action": "broke_stale_lock", "ok": True}, indent=2))
            else:
                print("🔓 Broke stale lock.")
            return 0
        else:
            if as_json:
                print(json.dumps({"action": "break_failed", "ok": False}, indent=2))
            else:
                print("❌ Failed to break stale lock.")
            return 1

    if wait and status["locked"]:
        print("⏳ Waiting for lock release...", file=sys.stderr)
        while True:
            status = read_lock_status()
            if not status["locked"]:
                break
            time.sleep(0.5)
        if as_json:
            print(json.dumps({"action": "waited", "ok": True}, indent=2))
        else:
            print("✅ Lock released.")
        return 0

    if as_json:
        print(json.dumps(status, indent=2, default=str))
    else:
        _print_human(status)

    # Exit code: 0 = ok, 1 = warning, 2 = error
    if status["stale"]:
        return 2
    if status["deadlock_warning"]:
        return 1
    return 0


def _print_human(status: dict) -> None:
    """Print human-readable lock status."""
    if not status["locked"]:
        print("✅ No lock held — bet-ledger.yaml is available for writes.")
        return

    info = status.get("info", {})
    pid = info.get("pid", "?")
    hostname = info.get("hostname", "?")
    operation = info.get("operation", "")
    age = status.get("age_seconds", 0)

    print(f"🔒 Lock HELD by PID {pid} on {hostname}")
    if operation:
        print(f"   Operation: {operation}")
    print(f"   Age: {age:.0f}s")

    if status["stale"]:
        print(f"   ⚠️  STALE: Process {pid} is dead and lock held >{STALE_LOCK_S}s")
        print(f"   Fix: python3 bin/gac/ledger-lock-check.py --break-stale")
        print(
            f"   HINT: ledger 锁被占 → bin/gac/ledger-lock-check.py --json 查看占用; 僵死锁 → --break-stale; 等待释放 → --wait"
        )
        print(f"   强约束: 台账写必须持锁, 无锁写直接阻断 (CR-LEDGER-LOCK)")
    elif status["deadlock_warning"]:
        print(f"   ⚠️  DEADLOCK WARNING: Lock held >{DEADLOCK_WARNING_S}s")
        print(f"   Check if PID {pid} is stuck: ps -p {pid}")
        print(
            f"   HINT: ledger 锁被占 → bin/gac/ledger-lock-check.py --json 查看占用; 僵死锁 → --break-stale; 等待释放 → --wait"
        )
    else:
        print(f"   Status: normal (renewed {age:.0f}s ago)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check bet-ledger lock status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--break-stale", action="store_true", help="Force-break stale locks")
    parser.add_argument("--wait", action="store_true", help="Wait for lock release")
    args = parser.parse_args()

    return check_lock(as_json=args.json, break_stale=args.break_stale, wait=args.wait)


if __name__ == "__main__":
    raise SystemExit(main())
