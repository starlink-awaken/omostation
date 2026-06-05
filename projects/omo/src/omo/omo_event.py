#!/usr/bin/env python3
"""OMO event CLI — inspect and subscribe to Agora event bus events."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def _agora_url(path: str) -> str:
    port = __import__("os").environ.get("AGORA_MCP_PORT", "7430")
    return f"http://localhost:{port}{path}"


def cmd_event_list(limit: int) -> int:
    """List recent events from Agora EventBus."""
    try:
        resp = urlopen(Request(f"{_agora_url('/api/events')}?limit={limit}"), timeout=3)
        events = json.loads(resp.read())
        if isinstance(events, list):
            print(f"{'TIMESTAMP':30s} {'TYPE':20s} {'DETAILS'}")
            print("-" * 80)
            for e in events[:limit]:
                ts = e.get("timestamp", e.get("ts", "?"))[:26]
                et = e.get("type", e.get("event", "?"))[:18]
                detail = json.dumps(e.get("data", e.get("payload", "")))[:40]
                print(f"{ts:30s} {et:20s} {detail}")
            print(f"\nTotal: {len(events)} events")
        else:
            print(f"EventBus returned: {events}")
    except Exception as ex:
        print(f"⚠️  EventBus unavailable ({ex})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo event", description="OMO EventBus inspector")
    sub = parser.add_subparsers(dest="command")
    el = sub.add_parser("list", help="List recent events")
    el.add_argument("--limit", "-n", type=int, default=20)
    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_event_list(args.limit)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
