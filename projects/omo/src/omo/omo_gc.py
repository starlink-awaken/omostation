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

    print("✅ 代谢清理完成。")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
