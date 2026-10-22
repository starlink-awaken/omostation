#!/usr/bin/env python3
"""ADR-0457 历史单测遗留脏数据 7 天生命周期管理与物理清理工具.

保留期截止: 2026-10-26T00:00:00Z (7天)
范围:
  1. ~/.local/share/omostation/cards_archive/
  2. .omo/tasks/archived/dispatches_test_archive/
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEADLINE = datetime(2026, 10, 26, 0, 0, 0, tzinfo=timezone.utc)

CARDS_ARCHIVE = Path.home() / ".local/share/omostation/cards_archive"
DISPATCHES_ARCHIVE = ROOT / ".omo/tasks/archived/dispatches_test_archive"


def count_files(p: Path) -> int:
    if not p.exists():
        return 0
    return len(list(p.glob("*")))


def purge() -> None:
    deleted = 0
    if CARDS_ARCHIVE.exists():
        c_count = count_files(CARDS_ARCHIVE)
        shutil.rmtree(CARDS_ARCHIVE)
        print(f"🗑️ Purged {c_count} cards from {CARDS_ARCHIVE}")
        deleted += c_count
    if DISPATCHES_ARCHIVE.exists():
        d_count = count_files(DISPATCHES_ARCHIVE)
        shutil.rmtree(DISPATCHES_ARCHIVE)
        print(f"🗑️ Purged {d_count} tasks from {DISPATCHES_ARCHIVE}")
        deleted += d_count
    print(f"✅ Total purged: {deleted} files.")


def status() -> None:
    now = datetime.now(timezone.utc)
    cards_count = count_files(CARDS_ARCHIVE)
    dispatches_count = count_files(DISPATCHES_ARCHIVE)
    expired = now >= DEADLINE
    remaining_days = max(0.0, (DEADLINE - now).total_seconds() / 86400.0)

    print("=== ADR-0457 Test Data Archive Retention Status ===")
    print(f"Current UTC:    {now.isoformat()}")
    print(f"Deadline UTC:   {DEADLINE.isoformat()}")
    print(f"Remaining:      {remaining_days:.2f} days")
    print(f"Cards Archive:  {cards_count} files ({CARDS_ARCHIVE})")
    print(f"Dispatches:     {dispatches_count} files ({DISPATCHES_ARCHIVE})")
    print(f"Expired:        {'YES (ready to purge)' if expired else 'NO (in retention window)'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purge", action="store_true", help="Force purge archives immediately")
    parser.add_argument("--auto", action="store_true", help="Purge only if deadline expired")
    args = parser.parse_args()

    if args.purge:
        purge()
        return 0

    if args.auto:
        now = datetime.now(timezone.utc)
        if now >= DEADLINE:
            purge()
        else:
            print("Retention deadline not yet reached, keeping archive.")
        return 0

    status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
