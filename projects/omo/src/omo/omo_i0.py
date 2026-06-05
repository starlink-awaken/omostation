#!/usr/bin/env python3
"""OMO I0 CLI — query Agora integration fabric state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

OMO_HINT = ".omo"


def _agora_url(path: str) -> str:
    port = __import__("os").environ.get("AGORA_MCP_PORT", "7430")
    return f"http://localhost:{port}{path}"


def cmd_i0_status() -> int:
    """Query Agora health and registered services."""
    try:
        resp = urlopen(Request(f"{_agora_url('/health')}"), timeout=3)
        data = json.loads(resp.read())
        print("Agora Hub:       🟢 running")
        print(f"  Route count:   {data.get('routes', data.get('service_count', '?'))}")
    except Exception as e:
        print(f"Agora Hub:       🔴 unreachable ({e})")
    try:
        resp = urlopen(Request(f"{_agora_url('/api/services')}"), timeout=3)
        services = json.loads(resp.read())
        if isinstance(services, list):
            print(f"  Services:      {len(services)} total")
            for s in services[:10]:
                name = s.get("name", "?")
                st = s.get("status", "?")
                print(f"    - {name}: {st}")
            if len(services) > 10:
                print(f"    ... and {len(services) - 10} more")
    except Exception:
        print("  Services:      ⚠️  query failed")
    return 0


def cmd_i0_routes() -> int:
    """List Agora routing table."""
    try:
        resp = urlopen(Request(f"{_agora_url('/api/services')}"), timeout=3)
        services = json.loads(resp.read())
        if isinstance(services, list):
            print(f"{'SERVICE':30s} {'STATUS':12s} {'TOOLS':8s}")
            print("-" * 55)
            for s in services:
                name = s.get("name", "?")[:28]
                st = s.get("status", "?")[:10]
                tools = str(len(s.get("tools", [])))
                print(f"{name:30s} {st:12s} {tools:8s}")
            print(f"\nTotal: {len(services)} services")
    except Exception as e:
        print(f"❌ Route query failed: {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo i0", description="OMO I0 Integration Fabric query")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="Show Agora I0 fabric status")
    sub.add_parser("routes", help="List Agora routing table")
    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_i0_status()
    elif args.command == "routes":
        return cmd_i0_routes()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
