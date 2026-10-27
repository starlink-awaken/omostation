#!/usr/bin/env python3
"""ADR-0466 历史单测遗留脏数据 7 天生命周期管理与物理清理工具 (法条 2 第三层防线).

保留期: **逐条目** 7 天 (RETENTION_DAYS) —— 按条目自身落位时间 (卡片取 created_at,
否则取文件 mtime) 逐个判定, 不是按批次一次性到期。这样:
  - 新一轮污染归档进来后有完整 7 天缓冲, 不会被刚落地就销毁;
  - `--auto` 是幂等的周期巡检语义: 到期的删, 没到期的留。

范围:
  1. ~/.local/share/omostation/cards_archive/
  2. .omo/tasks/archived/dispatches_test_archive/

空目录保留 (作为后续轮次的落位区), 不整目录 rmtree。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))
from repo_root import code_root  # noqa: E402

ROOT = code_root()
RETENTION_DAYS = 7

CARDS_ARCHIVE = Path.home() / ".local/share/omostation/cards_archive"
DISPATCHES_ARCHIVE = ROOT / ".omo/tasks/archived/dispatches_test_archive"

ARCHIVES = (
    ("cards", CARDS_ARCHIVE),
    ("dispatches", DISPATCHES_ARCHIVE),
)


def _entry_timestamp(path: Path) -> datetime:
    """条目落位时间。卡片优先用自身 created_at (语义落位时间), 否则回退文件 mtime。"""
    if path.suffix == ".json":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            created = raw.get("created_at")
            if isinstance(created, str):
                try:
                    stamp = datetime.fromisoformat(created)
                except ValueError:
                    stamp = None
                else:
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    return stamp
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _age_days(path: Path, now: datetime) -> float:
    return (now - _entry_timestamp(path)).total_seconds() / 86400.0


def _entries(archive: Path) -> list[Path]:
    if not archive.exists():
        return []
    return sorted(p for p in archive.iterdir() if p.is_file())


def _collect(now: datetime) -> list[tuple[str, Path, float]]:
    rows: list[tuple[str, Path, float]] = []
    for label, archive in ARCHIVES:
        for entry in _entries(archive):
            rows.append((label, entry, _age_days(entry, now)))
    return rows


def purge(*, retention_days: int = RETENTION_DAYS, force: bool = False) -> int:
    """删除到期条目。force=True 时删除全部 (人工显式指令)。"""
    now = datetime.now(timezone.utc)
    deleted = 0
    for label, entry, age in _collect(now):
        if not force and age < retention_days:
            continue
        entry.unlink()
        deleted += 1
        print(f"🗑️ Purged {label} entry: {entry.name} (age {age:.2f}d)")
    print(f"✅ Total purged: {deleted} entries.")
    return deleted


def status(*, retention_days: int = RETENTION_DAYS) -> None:
    now = datetime.now(timezone.utc)
    rows = _collect(now)
    due = [r for r in rows if r[2] >= retention_days]
    oldest = max((r[2] for r in rows), default=0.0)

    print("=== ADR-0466 Test Data Archive Retention Status ===")
    print(f"Current UTC:      {now.isoformat()}")
    print(f"Retention:        {retention_days} days (per entry, since landing)")
    print(f"Cards Archive:    {CARDS_ARCHIVE}")
    print(f"Dispatches:       {DISPATCHES_ARCHIVE}")
    for label, archive in ARCHIVES:
        count = len(_entries(archive))
        print(f"  {label}: {count} entries ({archive})")
    print(f"Total entries:    {len(rows)}")
    print(f"Due for purge:    {len(due)}")
    print(f"Oldest entry age: {oldest:.2f} days")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purge", action="store_true", help="Force purge all archive entries immediately")
    parser.add_argument("--auto", action="store_true", help="Purge only entries past the retention window")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=RETENTION_DAYS,
        help="Retention window in days (default: 7)",
    )
    args = parser.parse_args()

    if args.purge:
        purge(retention_days=args.retention_days, force=True)
        return 0

    if args.auto:
        purge(retention_days=args.retention_days, force=False)
        return 0

    status(retention_days=args.retention_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
