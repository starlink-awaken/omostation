"""I0 Fabric CLI — service registry, live probes, events, protocols, dependency graph.

Usage:
    runtime i0 status           — fabric health overview
    runtime i0 services          — service list with live probes
    runtime i0 events [--limit N] — recent events from Agora SSE
    runtime i0 protocols         — protocol registry summary
    runtime i0 graph             — dependency graph
"""

from __future__ import annotations
import json
import sys
from typing import Any

from .i0 import i0_status, i0_services, i0_events, i0_protocols, i0_graph


def _json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _bool_icon(val: bool) -> str:
    return "✅" if val else "⏹️"


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_i0_status() -> int:
    try:
        status = i0_status()
    except Exception as e:
        print(f"❌ i0_status failed: {e}", file=sys.stderr)
        return 1

    layers = status.get("layers", {})
    print(f"╔════════════════════════════════════════╗")
    print(f"║     I0 Integration Fabric — Status     ║")
    print(f"╠════════════════════════════════════════╣")
    print(f"║  Timestamp:   {status['timestamp']}   ║")
    print(f"║                                        ║")
    print(f"║  Services:    {status['total_services']:3d} total               ║")
    print(f"║              {status['services_online']:3d} online               ║")
    print(f"║              {status['services_offline']:3d} offline              ║")
    print(f"║                                        ║")
    print(f"║  Protocols:   {status['total_protocols']:3d} total               ║")
    print(f"║              {status['active_protocols']:3d} active              ║")
    print(f"║                                        ║")
    print(f"║  Events:      {status['event_count']:3d} cached               ║")
    print(f"╠════════════════════════════════════════╣")
    print(f"║  Layer Breakdown:                       ║")
    for layer_key in sorted(layers):
        l = layers[layer_key]
        print(f"║    {layer_key}: {l['services']:2d} services, {l['online']:2d} online    ║")
    print(f"╚════════════════════════════════════════╝")
    return 0


def cmd_i0_services() -> int:
    try:
        services = i0_services()
    except Exception as e:
        print(f"❌ i0_services failed: {e}", file=sys.stderr)
        return 1

    print(f"{'SERVICE':20s} {'TYPE':12s} {'PORT':6s} {'LIVE':6s} {'HEALTH':12s} {'PID':8s} {'LAYER':6s}")
    print("-" * 80)
    for s in services:
        port = str(s["port"]) if s["port"] else "—"
        live = _bool_icon(s.get("port_listening", False))
        health = s.get("health", "?")
        pid = str(s["pid"]) if s.get("pid") else "—"
        print(f"{s['name']:20s} {s['type']:12s} {port:6s} {live:6s} {health:12s} {pid:8s} {s.get('layer', '?'):6s}")
    print(f"\nTotal: {len(services)} services ({sum(1 for s in services if s.get('port_listening'))} online)")
    return 0


def cmd_i0_events(limit: int = 20) -> int:
    try:
        events = i0_events(limit)
    except Exception as e:
        print(f"❌ i0_events failed: {e}", file=sys.stderr)
        return 1

    if not events:
        print("⚠️  No events retrieved. Is Agora running on :7430?")
        return 0

    print(f"{'ID':6s} {'TIME':22s} {'SOURCE':20s} {'TYPE':20s} {'PAYLOAD':40s}")
    print("-" * 110)
    for ev in events:
        eid = str(ev.get("id", ""))[:6]
        ts = str(ev.get("time", ev.get("timestamp", "")))[:22]
        src = str(ev.get("source", ""))[:20]
        etype = str(ev.get("type", ""))[:20]
        payload = str(ev.get("payload", ev.get("data", "")))[:40]
        print(f"{eid:6s} {ts:22s} {src:20s} {etype:20s} {payload:40s}")
    print(f"\nShowing {len(events)} events")
    return 0


def cmd_i0_protocols() -> int:
    try:
        protocols = i0_protocols()
    except Exception as e:
        print(f"❌ i0_protocols failed: {e}", file=sys.stderr)
        return 1

    print(f"Total protocols: {protocols['total']}")
    print()

    usage = protocols.get("by_usage", {})
    print("By Usage:")
    for u, cnt in sorted(usage.items()):
        print(f"  {u:12s}: {cnt}")
    print()

    cats = protocols.get("by_category", {})
    print("By Category:")
    for c, cnt in sorted(cats.items()):
        print(f"  {c:22s}: {cnt}")
    print()

    protos = protocols.get("protocols", [])
    print(f"{'NAME':25s} {'VERSION':10s} {'CATEGORY':22s} {'STATUS':10s} {'USAGE':10s}")
    print("-" * 85)
    for p in protos:
        print(f"{p['name']:25s} {p['version']:10s} {p['category']:22s} {p['status']:10s} {p['usage']:10s}")
    return 0


def cmd_i0_graph() -> int:
    try:
        graph = i0_graph()
    except Exception as e:
        print(f"❌ i0_graph failed: {e}", file=sys.stderr)
        return 1

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    print(f"Dependency Graph: {len(nodes)} nodes, {len(edges)} edges")
    print()

    # Print nodes grouped by layer
    by_layer: dict[str, list[str]] = {}
    for n in nodes:
        layer = n.get("layer", "?")
        by_layer.setdefault(layer, []).append(n["name"])

    print("Nodes by Layer:")
    for layer in sorted(by_layer):
        names = ", ".join(by_layer[layer])
        print(f"  {layer}: [{names}]")

    if edges:
        print(f"\nEdges ({len(edges)}):")
        for e in edges:
            print(f"  {e['from']} → {e['to']}  [{e.get('type', 'HARD')}]")
    else:
        print("\nNo dependency edges defined (no depends_on fields in matrix.yaml)")

    return 0


# ─── Parser ─────────────────────────────────────────────────────────────────

def add_i0_subparser(subparsers) -> None:
    """Add the 'i0' subcommand parser to an argparse subparsers group."""
    i0_p = subparsers.add_parser("i0", help="I0 Integration Fabric — query service registry, live probes, events, protocols, dependency graph")
    i0_sub = i0_p.add_subparsers(dest="i0_cmd")

    # status
    i0_sub.add_parser("status", help="Fabric health overview")

    # services
    i0_sub.add_parser("services", help="Service list with live port/health probes")

    # events
    ev_p = i0_sub.add_parser("events", help="Recent events from Agora SSE")
    ev_p.add_argument("--limit", type=int, default=20, help="Number of events (default: 20)")

    # protocols
    i0_sub.add_parser("protocols", help="Protocol registry summary")

    # graph
    i0_sub.add_parser("graph", help="Dependency graph")

    return i0_p


def handle_i0_command(args) -> int:
    """Route an argparse Namespace to the right i0 command."""
    cmd = args.i0_cmd
    if cmd == "status":
        return cmd_i0_status()
    elif cmd == "services":
        return cmd_i0_services()
    elif cmd == "events":
        return cmd_i0_events(limit=args.limit)
    elif cmd == "protocols":
        return cmd_i0_protocols()
    elif cmd == "graph":
        return cmd_i0_graph()
    else:
        print("i0: available subcommands: status, services, events, protocols, graph", file=sys.stderr)
        return 1
