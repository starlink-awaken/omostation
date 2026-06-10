import argparse
import time
import shutil
from pathlib import Path


def get_omo_dir(base_dir: Path) -> Path:
    current = base_dir.resolve()
    while current != current.parent:
        if (current / ".omo").is_dir():
            return current / ".omo"
        current = current.parent
    return base_dir / ".omo"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="OMO Global Garbage Collector")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without doing it",
    )
    args = parser.parse_args(argv)

    omo_dir = get_omo_dir(Path.cwd())
    if not omo_dir.exists():
        print(f"Error: {omo_dir} not found.")
        return 1

    print(f"🧹 启动 OMO 全局代谢清理机制 (Global GC) - 目标: {omo_dir}")
    now = time.time()
    thirty_days = 30 * 24 * 3600

    # 1. GC Drafts older than 30 days
    drafts_dir = omo_dir / "_knowledge" / "drafts"
    archive_dir = omo_dir / "_archive" / "stale_drafts"
    if drafts_dir.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in drafts_dir.glob("*.md"):
            if f.is_file():
                mtime = f.stat().st_mtime
                if now - mtime > thirty_days:
                    print(f"  [代谢] 草案已过期超过30天: {f.name} -> 移至 _archive")
                    if not args.dry_run:
                        shutil.move(str(f), str(archive_dir / f.name))

    # 2. GC Dead Task Locks (> 24 hours)
    locks_dir = omo_dir / "state" / "locks"
    one_day = 24 * 3600
    if locks_dir.exists():
        for f in locks_dir.glob("*.lock"):
            if f.is_file():
                mtime = f.stat().st_mtime
                if now - mtime > one_day:
                    print(f"  [清理] 发现僵死锁文件 (>24h): {f.name} -> 释放锁")
                    if not args.dry_run:
                        f.unlink()

    # 3. GC SQLite Databases (VACUUM to defragment)
    import sqlite3
    dbs_to_vacuum = [
        omo_dir.parent / "projects" / "agora" / "src" / "agora.db",
        omo_dir.parent / "projects" / "ecos" / "LADS" / "ssb" / "ecos.db",
        omo_dir.parent / "data" / "cards" / "cards.db",
        omo_dir.parent / "data" / "sharedbrain" / "data" / "db" / "core" / "event_store.db"
    ]
    
    for db_path in dbs_to_vacuum:
        if db_path.exists():
            print(f"  [碎片整理] 压缩数据库空间 (VACUUM): {db_path.name}")
            if not args.dry_run:
                try:
                    with sqlite3.connect(db_path) as conn:
                        conn.execute("VACUUM")
                except Exception as e:
                    print(f"    ❌ VACUUM 失败: {e}")

    print("✅ 代谢清理与碎片整理完成。")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
