#!/usr/bin/env python3
"""
eCOS v5 I0 — Agora 事件发布 (ecos-event)
===========================================
Phase 8.4 / DEBT-I0-001 修复
支持双格式: JSON lines (v1) + MCP Event (v2)

用法:
    python3 ecos-event.py --type freshness.alert --payload '{"files":3}'
    python3 ecos-event.py --tail 10
    python3 ecos-event.py --mcp  # MCP 协议格式输出
"""

import sys, json, argparse
from datetime import datetime, timezone
from pathlib import Path

EVENT_LOG = Path.home() / ".ecos" / "events" / "event-stream.jsonl"
MCP_LOG = Path.home() / ".ecos" / "events" / "mcp-stream.jsonl"
EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


def publish(event_type: str, payload: dict, source: str = "ecos-daemon", mcp: bool = False):
    now = datetime.now(timezone.utc).isoformat()
    evt = {
        "id": f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "type": event_type, "source": source,
        "timestamp": now, "payload": payload,
    }

    if mcp:
        # MCP 协议格式: 符合 Agora event 规范
        mcp_evt = {
            "jsonrpc": "2.0",
            "method": "event.publish",
            "params": {
                "event": event_type,
                "source": source,
                "timestamp": now,
                "data": payload,
            },
        }
        with open(MCP_LOG, "a") as f:
            f.write(json.dumps(mcp_evt, ensure_ascii=False) + "\n")
        return mcp_evt

    with open(EVENT_LOG, "a") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    return evt


def tail(n: int = 10, event_type: str = None, mcp: bool = False):
    log = MCP_LOG if mcp else EVENT_LOG
    if not log.exists():
        return []
    events = []
    with open(log, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if event_type and evt.get("type") != event_type:
                    continue
                events.append(evt)
            except json.JSONDecodeError:
                continue
    return events[-n:]


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 I0 Agora 事件")
    parser.add_argument("--type", type=str)
    parser.add_argument("--payload", type=str, default="{}")
    parser.add_argument("--source", type=str, default="ecos-daemon")
    parser.add_argument("--tail", type=int, default=0)
    parser.add_argument("--filter", type=str)
    parser.add_argument("--mcp", action="store_true", help="MCP 协议格式")
    args = parser.parse_args()

    if args.tail > 0:
        events = tail(args.tail, args.filter, args.mcp)
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return

    if not args.type:
        print("❌ 需要 --type 或 --tail", file=sys.stderr)
        sys.exit(2)

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError:
        print(f"❌ 无效 JSON: {args.payload}", file=sys.stderr)
        sys.exit(2)

    event = publish(args.type, payload, args.source, args.mcp)
    print(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
