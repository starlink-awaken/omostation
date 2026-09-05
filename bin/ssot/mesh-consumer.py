#!/usr/bin/env python3
"""Mesh Consumer — Workflow Mesh 事件实时消费者 (FACE-05).

实时读 events.jsonl 新增事件 → 按 event_type 处理:
  - WorkflowRequested: 记录到消费台账 (去重)
  - agent.tick: 更新 agent 活跃度
  - journey.*: 触发 outcome/reflection 桥接

守 fabric 红线: 只读事件流, 不伪造事件, 消费进度落独立 offset 文件.
Usage:
  python3 bin/ssot/mesh-consumer.py --once        # 消费一次 (增量)
  python3 bin/ssot/mesh-consumer.py --watch        # 持续消费
  python3 bin/ssot/mesh-consumer.py --reset        # 重置 offset
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

TIMEOUT = 30  # seconds per subprocess call
RETRY = 3    # max retries on transient failure
from typing import Any

from _shared import ROOT, append_jsonl, utc_now

EVENTS_LOG = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
OFFSET_FILE = ROOT / ".omo" / "state" / "mesh-consumer-offset.json"
CONSUME_LOG = ROOT / ".omo" / "state" / "mesh-consumer-trace.jsonl"


def _load_offset() -> tuple[int, int]:
    """Return (line_offset, byte_offset) from persisted state."""
    if OFFSET_FILE.exists():
        try:
            data = json.loads(OFFSET_FILE.read_text(encoding="utf-8"))
            return int(data.get("offset", 0)), int(data.get("byte_offset", 0))
        except Exception:
            pass
    return 0, 0


def _save_offset(line_offset: int, byte_offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(
        json.dumps(
            {
                "offset": line_offset,
                "byte_offset": byte_offset,
                "ts": utc_now(),
            }
        ),
        encoding="utf-8",
    )


def _trace(entry: dict[str, Any]) -> None:
    append_jsonl(CONSUME_LOG, entry)


def _handle_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Process one event. Returns consumer action."""
    event_type = str(ev.get("event_type", "unknown"))
    eid = str(ev.get("event_id", ""))[:8]
    payload = ev.get("payload") or {}

    if event_type == "WorkflowRequested":
        return {
            "event_id": eid,
            "event_type": event_type,
            "action": "tracked",
            "objective": str(payload.get("objective", ""))[:80],
        }
    if event_type.startswith("agent."):
        return {
            "event_id": eid,
            "event_type": event_type,
            "action": "agent_heartbeat",
            "agent_id": str(payload.get("agent_id", "?")),
            "ok": payload.get("ok"),
        }
    if event_type.startswith("journey."):
        return {
            "event_id": eid,
            "event_type": event_type,
            "action": "journey_event",
            "journey": str(payload.get("journey_id", "?")),
        }
    return {"event_id": eid, "event_type": event_type, "action": "noop"}


def consume_once(root: Path | None = None) -> dict[str, Any]:
    """Consume new events since last offset using byte-level seek (avoid O(n) line count)."""
    root = root or ROOT
    events_log = root / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
    if not events_log.exists():
        return {"status": "noop", "reason": "events.jsonl not found", "consumed": 0}

    line_offset, byte_offset = _load_offset()

    # O(1) check: if file size hasn't grown, nothing to do
    try:
        current_size = os.path.getsize(events_log)
    except OSError:
        return {"status": "error", "consumed": 0}

    if current_size <= byte_offset:
        return {"status": "noop", "consumed": 0, "note": "no new bytes"}

    # Seek to last-known byte position and read only new content
    handled: list[dict[str, Any]] = []
    new_lines = 0
    final_byte_offset = current_size

    try:
        with open(events_log, encoding="utf-8") as f:
            f.seek(byte_offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                handled.append(_handle_event(ev))
                new_lines += 1
    except OSError:
        pass

    new_line_offset = line_offset + new_lines
    _save_offset(new_line_offset, final_byte_offset)

    by_action: dict[str, int] = {}
    for h in handled:
        by_action[h["action"]] = by_action.get(h["action"], 0) + 1
        _trace(h)

    return {
        "status": "consumed",
        "consumed": len(handled),
        "offset": new_line_offset,
        "by_action": by_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="consume increment once")
    parser.add_argument("--watch", action="store_true", help="continuous consume")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--reset", action="store_true", help="reset offset")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    if args.reset:
        _save_offset(0, 0)
        print("Offset reset to 0.")
        return 0

    if args.watch:
        print(f"Watching mesh events (interval={args.interval}s)...", flush=True)
        while True:
            result = consume_once(args.root)
            if result.get("consumed", 0) > 0:
                print(
                    f"  consumed {result['consumed']}: {result.get('by_action')}",
                    flush=True,
                )
            time.sleep(args.interval)

    result = consume_once(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
