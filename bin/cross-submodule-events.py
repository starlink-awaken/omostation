#!/usr/bin/env python3
"""P80 R2: 跨子仓 omo event 联动订阅器.

实时订阅 .omo/_knowledge/omo-events.jsonl 事件流,
按 event kind 触发跨子仓反应 (ecos 治理检查 / agora 通知 / cockpit dashboard 同步).

类似 P74 p0-event-listener 但更通用 (按 kind路由).

使用:
  python3 bin/cross-submodule-events.py --watch
  python3 bin/cross-submodule-events.py --kind governance_alert
  python3 bin/cross-submodule-events.py --stats  # 统计历史
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# kind → 路由 (P80 R2 路由表)
ROUTES = {
    "governance_alert": "ecos:audit-check",
    "governance_alert_aggregated": "ecos:audit-batch",
    "ssot_audit_divergence_found": "ecos:flag",
    "ssot_guardian_run": "ecos:heartbeat",
    "tasks_registry_index_updated": "agora:registry-sync",
    "agent_mutation_complete": "agora:notify",
    "agent_ssb_update": "cockpit:event-bus",
}


def load_events(log: Path) -> list[dict]:
    """读 omo-events.jsonl."""
    if not log.exists():
        return []
    records = []
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P80: 跨子仓 omo event 联动订阅器"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--kind", help="仅显示指定 kind 事件")
    parser.add_argument("--stats", action="store_true", help="仅统计")
    parser.add_argument("--watch", action="store_true", help="实时 tail 模式")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    events_log = root / ".omo" / "_knowledge" / "omo-events.jsonl"
    if not events_log.parent.exists():
        print(f"❌ {events_log.parent} 不存在")
        return 1

    if args.stats:
        records = load_events(events_log)
        kind_counter: Counter = Counter()
        for rec in records:
            kind_counter[rec.get("kind", "?")] += 1
        print("=" * 60)
        print("📊 P80 omo event 统计")
        print("=" * 60)
        print(f"📁 总事件: {len(records)}")
        print()
        print("按 kind:")
        for kind, count in kind_counter.most_common():
            route = ROUTES.get(kind, "(no route)")
            print(f"  {kind:<35s} {count:>3d}  →  {route}")
        return 0

    if args.watch:
        print(f"👁️  P80 跨子仓 omo event 实时订阅 (Ctrl+C 退出)")
        last_pos = events_log.stat().st_size if events_log.exists() else 0
        last_inode = events_log.stat().st_ino if events_log.exists() else 0
        while True:
            try:
                if events_log.exists():
                    cur_inode = events_log.stat().st_ino
                    cur_pos = events_log.stat().st_size
                    if cur_inode != last_inode:
                        last_inode = cur_inode
                        last_pos = 0
                    if cur_pos > last_pos:
                        with open(events_log, encoding="utf-8") as f:
                            f.seek(last_pos)
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    rec = json.loads(line)
                                except Exception:
                                    continue
                                kind = rec.get("kind", "?")
                                if args.kind and kind != args.kind:
                                    continue
                                route = ROUTES.get(kind, "(no route)")
                                ts = rec.get("ts", "?")
                                src = rec.get("source", "?")
                                print(f"  📡 [{ts}] {kind} → {route} (src={src})")
                        last_pos = cur_pos
                time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n👁️  P80 watch 退出")
                return 0

    # 默认: 列出最近 10 事件
    records = load_events(events_log)
    print("=" * 60)
    print(f"📊 P80 omo event 最近 {min(10, len(records))} 个")
    print("=" * 60)
    for rec in records[-10:]:
        kind = rec.get("kind", "?")
        ts = rec.get("ts", "?")
        route = ROUTES.get(kind, "(no route)")
        if args.kind and kind != args.kind:
            continue
        print(f"  [{ts}] {kind:<35s} → {route}")
    return 0


if __name__ == "__main__":
    sys.exit(main())