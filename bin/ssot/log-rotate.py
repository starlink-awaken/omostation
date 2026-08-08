#!/usr/bin/env python3
"""日志轮转 — 可观测性 P1.2 (design: docs/observability-unified-architecture.md).

轮转分散的 launchd 守护日志 (此前无 logrotate/RotatingFileHandler, 无限增长).
规则:
  - 超过 --max-bytes (默认 5MB) 的文件 → 轮转 (保留 --keep 份 .1/.2/...)
  - 保留份数 (--keep, 默认 3)
  - 轮转 = rename 链 (log → log.1 → log.2 → ...), 与 logrotate 语义一致

用法:
  python3 bin/ssot/log-rotate.py --dry-run     # 只看不动
  python3 bin/ssot/log-rotate.py               # 执行轮转
  python3 bin/ssot/log-rotate.py --max-bytes 10485760 --keep 5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HOME = Path.home()
WORKSPACE = Path(__file__).resolve().parents[2]

# 已知日志路径 (launchd StandardOut/ErrorPath + 守护输出)
LOG_PATHS = [
    HOME / ".agora" / "logs",
    WORKSPACE / ".omo" / "_delivery",
    WORKSPACE / ".omo" / "_log",
    WORKSPACE / "runtime" / "logs",
    HOME / ".local" / "state" / "omostation",
    Path("/tmp"),
]

LOG_PATTERNS = ("*.log", "*.out.log", "*.err.log", "*.jsonl")
SKIP_NAMES = {"agora-events.json", "agora-proxy-services.json", "agora-audit.db"}


def _candidate_files() -> list[Path]:
    out: list[Path] = []
    for base in LOG_PATHS:
        if not base.is_dir():
            continue
        for pattern in LOG_PATTERNS:
            for p in base.glob(pattern):
                if p.name in SKIP_NAMES:
                    continue
                if p.name.startswith("."):
                    continue
                out.append(p)
    # 去重 (可能有重叠 glob)
    return sorted(set(out))


def _rotate_one(path: Path, keep: int, dry_run: bool) -> bool:
    size = path.stat().st_size
    if size == 0:
        return False
    # rename 链: log.keep-1 → 删; log.N → log.N+1; log → log.1
    for i in range(keep - 1, 0, -1):
        src = path.with_name(f"{path.name}.{i}")
        dst = path.with_name(f"{path.name}.{i + 1}")
        if src.exists():
            if dry_run:
                print(f"  [dry-run] {src.name} -> {dst.name}")
            else:
                dst.unlink(missing_ok=True)
                src.rename(dst)
    if dry_run:
        print(f"  [dry-run] {path.name} ({size} bytes) -> {path.name}.1")
    else:
        path.with_name(f"{path.name}.1").unlink(missing_ok=True)
        path.rename(path.with_name(f"{path.name}.1"))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=5 * 1024 * 1024, help="轮转阈值 (默认 5MB)")
    parser.add_argument("--keep", type=int, default=3, help="保留份数 (默认 3)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = _candidate_files()
    over = [p for p in candidates if p.stat().st_size > args.max_bytes]
    print(f"log-rotate: {len(candidates)} candidate(s), {len(over)} over {args.max_bytes} bytes")
    rotated = 0
    for p in over:
        print(f"  rotate: {p} ({p.stat().st_size} bytes)")
        if _rotate_one(p, args.keep, args.dry_run):
            rotated += 1
    print(f"log-rotate: {'[dry-run] ' if args.dry_run else ''}{rotated} rotated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
