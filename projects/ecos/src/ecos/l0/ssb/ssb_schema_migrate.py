#!/usr/bin/env python3
"""
SSB Schema V1 迁移 — 幂等、安全、可回滚
"""

import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

from ecos.common.common import SSB_JSONL_PATH  # type: ignore[import-not-found]

SSB_PATH = str(SSB_JSONL_PATH)
BACKUP = SSB_PATH + f".backup.{int(time.time())}"

AGENT_TYPE_MAP = {
    "CAPTURE_WATCHER": "CAPTURE_PERCEPTION",
    "FILTER_SCORER": "FILTER_SCORED",
    "KANBAN_BRIDGE": "KANBAN_SYNC",
    "INTEGRATE_PIPELINE": "INTEGRATE_RUN",
}


def migrate():
    shutil.copy2(SSB_PATH, BACKUP)
    print(f"📦 备份: {BACKUP}")

    with open(SSB_PATH) as f:
        lines = f.readlines()

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line, "_corrupt": True})

    T0 = datetime(2026, 5, 8, 0, 0, 0)  # noqa: N806
    INTERVAL = timedelta(minutes=2)  # noqa: N806
    BASE_SEQ = 1000  # noqa: N806

    stats = {
        "total": len(events),
        "added_timestamp": 0,
        "added_event_type": 0,
        "added_schema": 0,
        "corrupt": 0,
    }
    migrated = []

    for i, event in enumerate(events):
        if event.get("_corrupt"):
            migrated.append(json.dumps(event, ensure_ascii=False))
            stats["corrupt"] += 1
            continue

        if "schema_version" not in event:
            event["schema_version"] = "1.0"
            stats["added_schema"] += 1

        if "timestamp" not in event or not event.get("timestamp"):
            seq = event.get("seq", 0)
            offset = max(0, (seq if isinstance(seq, int) else 0) - BASE_SEQ)
            event["timestamp"] = (T0 + offset * INTERVAL).timestamp()

        if not event.get("event_type") or event.get("event_type") == "?":
            event["event_type"] = AGENT_TYPE_MAP.get(event.get("agent", ""), "UNKNOWN")
            stats["added_event_type"] += 1

        migrated.append(json.dumps(event, ensure_ascii=False))

    with open(SSB_PATH, "w") as f:
        f.write("\n".join(migrated) + "\n")

    # Verify
    with open(SSB_PATH) as f:
        verify_events = [json.loads(line) for line in f if line.strip()]

    ts_count = sum(1 for e in verify_events if e.get("timestamp", 0) > 0)
    schema_count = sum(1 for e in verify_events if e.get("schema_version") == "1.0")
    print(
        f"\n📊 迁移: total={stats['total']} schema={stats['added_schema']} ts={stats['added_timestamp']}"
    )
    print(
        f"✅ 验证: ts={ts_count}/{len(verify_events)} schema={schema_count}/{len(verify_events)}"
    )


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        if os.path.exists(BACKUP):
            shutil.copy2(BACKUP, SSB_PATH)
            print(f"🔄 已从备份恢复: {BACKUP}")
        sys.exit(1)
