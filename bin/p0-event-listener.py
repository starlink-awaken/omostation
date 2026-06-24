#!/usr/bin/env python3
"""P74 R1: 事件驱动 P0 检测 (omo event listener).

监听 .omo/_knowledge/omo-events.jsonl 新事件, 检测 governance_alert_aggregated:
- 解析 payload.level
- 若 P0 → 调 alert-mock-p0-notify
- 替代 P73 polling 模式 (步骤 2.6.5)

使用:
  # 后台守护进程模式
  python3 bin/p0-event-listener.py --daemon
  # 单次轮询 (cron 或 cron-less 测试)
  python3 bin/p0-event-listener.py --once
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def get_last_ts(log: Path) -> str:
    """读最后一行 ts 字段."""
    if not log.exists():
        return ""
    try:
        with open(log, encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                rec = json.loads(line.strip())
                return rec.get("ts", "")
            except Exception:
                continue
    except Exception:
        pass
    return ""


def process_events(root: Path, since_ts: str = "") -> list[dict]:
    """处理 since_ts 之后的 governance_alert_aggregated P0 事件.

    返回: 处理的事件列表.
    """
    log = root / ".omo" / "_knowledge" / "omo-events.jsonl"
    if not log.exists():
        return []
    processed = []
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = rec.get("ts", "")
                # 时间过滤 (严格大于 since_ts, 同 ts 也算新)
                if since_ts and ts < since_ts:
                    continue
                kind = rec.get("kind", "")
                if kind != "governance_alert_aggregated":
                    continue
                # 解析 payload
                payload_str = rec.get("payload", "{}")
                if isinstance(payload_str, str):
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        payload = {}
                else:
                    payload = payload_str
                # 检查 level
                if payload.get("level") != "P0":
                    continue
                # 触发 P0 mock 通知
                message = payload.get("level_reason", "P0 触发")
                subprocess.run([
                    "python3", str(root / "bin" / "alert-mock-p0-notify.py"),
                    "--message", message, "--all-channels"
                ], capture_output=True, timeout=10, cwd=str(root))
                processed.append(rec)
    except Exception as e:
        print(f"⚠️  process_events 错误: {e}")
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P74: 事件驱动 P0 检测 (omo event listener)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--once", action="store_true", help="单次轮询 (不后台)")
    parser.add_argument("--daemon", action="store_true", help="后台守护 (每 60s 轮询)")
    parser.add_argument("--interval", type=int, default=60, help="守护间隔 (秒)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    last_ts = get_last_ts(root / ".omo" / "_knowledge" / "omo-events.jsonl")

    if args.once:
        processed = process_events(root, last_ts)
        print(f"📡 P74 事件驱动 P0 检测: 处理 {len(processed)} 个 P0 事件")
        for rec in processed:
            print(f"  - {rec.get('ts', '?')} P0 → mock 通知已触发")
        return 0

    if args.daemon:
        print(f"🔄 P74 事件驱动 P0 守护 (每 {args.interval}s)")
        while True:
            processed = process_events(root, last_ts)
            if processed:
                ts_now = datetime.now(timezone.utc).isoformat()
                print(f"[{ts_now}] 处理 {len(processed)} 个 P0")
                for rec in processed:
                    print(f"  - {rec.get('ts', '?')} P0")
            last_ts = get_last_ts(root / ".omo" / "_knowledge" / "omo-events.jsonl") or last_ts
            time.sleep(args.interval)

    # 默认行为: 打印用法
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())