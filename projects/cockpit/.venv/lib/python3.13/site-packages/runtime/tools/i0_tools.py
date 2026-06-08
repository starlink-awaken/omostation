import json

def _i0_status() -> str:
    from runtime.i0 import i0_status as _i0_status_fn
    try:
        status = _i0_status_fn()
        return json.dumps(status, indent=2, default=str)
    except Exception as e:
        return f"❌ i0_status failed: {e}"

def _i0_services() -> str:
    from runtime.i0 import i0_services as _i0_services_fn
    try:
        services = _i0_services_fn()
        parts = [f"{'SERVICE':20s} {'TYPE':12s} {'PORT':6s} {'LIVE':6s} {'HEALTH':12s} {'LAYER':6s}", "-" * 65]
        for s in services:
            port = str(s["port"]) if s["port"] else "—"
            live = "✅" if s.get("port_listening") else "⏹️"
            parts.append(f"{s['name']:20s} {s['type']:12s} {port:6s} {live:6s} {s.get('health','?'):12s} {s.get('layer','?'):6s}")
        parts.append(f"\nTotal: {len(services)} services ({sum(1 for s in services if s.get('port_listening'))} online)")
        return "\n".join(parts)
    except Exception as e:
        return f"❌ i0_services failed: {e}"

def _i0_events(limit: int = 20) -> str:
    from runtime.i0 import i0_events as _i0_events_fn
    try:
        events = _i0_events_fn(limit)
        if not events:
            return "⚠️  No events retrieved. Is Agora running on :7430?"
        parts = [f"{'ID':6s} {'TIME':22s} {'SOURCE':20s} {'TYPE':20s} {'PAYLOAD':40s}", "-" * 110]
        for ev in events:
            eid = str(ev.get("id", ""))[:6]
            ts = str(ev.get("time", ev.get("timestamp", "")))[:22]
            src = str(ev.get("source", ""))[:20]
            etype = str(ev.get("type", ""))[:20]
            payload = str(ev.get("payload", ev.get("data", "")))[:40]
            parts.append(f"{eid:6s} {ts:22s} {src:20s} {etype:20s} {payload:40s}")
        parts.append(f"\nShowing {len(events)} events")
        return "\n".join(parts)
    except Exception as e:
        return f"❌ i0_events failed: {e}"

def _i0_protocols() -> str:
    from runtime.i0 import i0_protocols as _i0_protocols_fn
    try:
        protocols = _i0_protocols_fn()
        lines = [f"Total protocols: {protocols['total']}", ""]
        usage = protocols.get("by_usage", {})
        lines.append("By Usage:")
        for u, cnt in sorted(usage.items()):
            lines.append(f"  {u:12s}: {cnt}")
        lines.append("")
        protos = protocols.get("protocols", [])
        lines.append(f"{'NAME':25s} {'VERSION':10s} {'CATEGORY':22s} {'STATUS':10s} {'USAGE':10s}")
        lines.append("-" * 85)
        for p in protos:
            lines.append(f"{p['name']:25s} {p['version']:10s} {p['category']:22s} {p['status']:10s} {p['usage']:10s}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ i0_protocols failed: {e}"

def _i0_graph() -> str:
    from runtime.i0 import i0_graph as _i0_graph_fn
    try:
        graph = _i0_graph_fn()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        lines = [f"Dependency Graph: {len(nodes)} nodes, {len(edges)} edges", ""]
        by_layer: dict[str, list[str]] = {}
        for n in nodes:
            layer = n.get("layer", "?")
            by_layer.setdefault(layer, []).append(n["name"])
        lines.append("Nodes by Layer:")
        for layer in sorted(by_layer):
            names = ", ".join(by_layer[layer])
            lines.append(f"  {layer}: [{names}]")
        if edges:
            lines.append(f"\nEdges ({len(edges)}):")
            for e in edges:
                lines.append(f"  {e['from']} → {e['to']}  [{e.get('type', 'HARD')}]")
        else:
            lines.append("\nNo dependency edges defined")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ i0_graph failed: {e}"

TOOLS = [
    {
        "name": "i0_status",
        "description": "I0 Fabric health overview — total/online/offline services, protocols, events, layer breakdown.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _i0_status(),
    },
    {
        "name": "i0_services",
        "description": "List all services with live port and health probes.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _i0_services(),
    },
    {
        "name": "i0_events",
        "description": "Fetch recent events from Agora SSE endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of events to return", "default": 20}
            },
        },
        "handler": lambda args: _i0_events(args.get("limit", 20)),
    },
    {
        "name": "i0_protocols",
        "description": "Protocol registry summary.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _i0_protocols(),
    },
    {
        "name": "i0_graph",
        "description": "Dependency graph.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _i0_graph(),
    }
]
