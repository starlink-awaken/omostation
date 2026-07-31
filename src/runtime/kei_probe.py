#!/usr/bin/env python3
"""KEI 沙箱探针 CLI — X-Plane X1/K1 probe 专用。

用法:
    python -m runtime.kei_probe --count-24h
    python -m runtime.kei_probe --last-age-hours

输出:
    --count-24h:        24h 内事件数(int,exit 0 if >0 else 1)
    --last-age-hours:   距最新事件的小时数(浮点,exit 0 if < sla else 1)
    --path <path>:      自定义 kei_audit.jsonl 路径(默认 ~/runtime/data/kei_audit.jsonl)

设计: 不依赖 runtime 项目其他模块,只读 JSONL。供 X-Plane probe 在 omo 子项目
内用 `uv run --package runtime` 调用,跨子项目边界合规。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PATH = (
    Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))
    / "data"
    / "kei_audit.jsonl"
)


def count_last_24h(path: Path) -> int:
    """数 24h 内 kei 事件数。"""
    if not path.exists():
        print(f"0 (文件不存在: {path})")
        return 0
    now = datetime.now(timezone.utc)
    count = 0
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 65536))  # 读尾 64KB(够覆盖 24h)
            data = f.read().decode("utf-8", "replace")
    except OSError as e:
        print(f"0 (读失败: {e})")
        return 0
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            ts = rec.get("ts")
            if not ts:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (now - dt).total_seconds() < 86400:
                count += 1
        except (json.JSONDecodeError, ValueError):
            continue
    print(count)
    return count


def last_age_hours(path: Path) -> float:
    """返回最新事件的年龄(小时)。"""
    if not path.exists():
        return float("inf")
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 65536))
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return float("inf")
    last_ts = None
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            ts = rec.get("ts")
            if not ts:
                continue
            last_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
        except (json.JSONDecodeError, ValueError):
            continue
    if last_ts is None:
        return float("inf")
    age = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
    print(f"{age:.2f}")
    return age


def main() -> int:
    parser = argparse.ArgumentParser(prog="runtime.kei_probe")
    parser.add_argument("--count-24h", action="store_true", help="数 24h 内事件数")
    parser.add_argument("--last-age-hours", action="store_true", help="最新事件龄(h)")
    parser.add_argument(
        "--path", type=Path, default=DEFAULT_PATH, help="kei_audit.jsonl 路径"
    )
    args = parser.parse_args()

    if args.count_24h:
        return 0 if count_last_24h(args.path) > 0 else 1
    if args.last_age_hours:
        return 0 if last_age_hours(args.path) < 24 else 1
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
