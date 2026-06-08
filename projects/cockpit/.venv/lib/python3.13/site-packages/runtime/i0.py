"""I0 Integration Fabric — query surface for eCOS integration layer.

I0 provides unified access to service registry, protocol registry,
live health probes, and event streams. It is a QUERY surface, not
an EXECUTION surface. Execution is delegated to Agora (routing),
cron-service (scheduling), and OMO (governance).

Usage:
    from runtime.i0 import i0_status, i0_services, i0_events
    status = i0_status()
"""

from __future__ import annotations
import json
import os
import socket
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", os.path.expanduser("~/runtime")))
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ─── Layer Mapping ──────────────────────────────────────────────────────────
# Categorize services by layer:
#   L0 = protocol/transport services
#   L1 = runtime services
#   L2 = kernel services
#   I0 = fabric/infrastructure services
_SERVICE_LAYER: dict[str, str] = {
    # I0 — Fabric/Infrastructure (core daemons)
    "hermes-gateway": "I0",
    "agent-runtime": "I0",
    "cron-service": "I0",
    "agora": "I0",
    "runtime-mcp": "I0",
    # L0 — Protocol
    "ollama": "L0",
    # L1 — Runtime / Knowledge
    "kos": "L1",
    "gbrain-index": "L1",
    # L2 — Kernel (stateful backends)
    "sharedbrain-bos": "L2",
    "gbrain": "L2",
}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_yaml(path: Path) -> dict:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data or {}
    return {}


def _probe_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is listening."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def _health_check(url: str, timeout: float = 3.0) -> str:
    """Probe a health endpoint. Returns 'healthy', 'unreachable', or 'unknown'."""
    if not url:
        return "unknown"
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        if r.status < 500:
            return "healthy"
        return "unreachable"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return "unreachable"


def _get_pid_for_port(port: int) -> Optional[int]:
    """Try to find PID listening on a port using lsof."""
    if not port:
        return None
    try:
        r = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.stdout.strip():
            return int(r.stdout.strip().split("\n")[0])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, OSError):
        pass
    return None


def _fetch_events_from_agora(limit: int = 20) -> list[dict]:
    """Fetch recent events from Agora event-log endpoint."""
    url = "http://127.0.0.1:7430/api/event-log"
    events: list[dict] = []
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        # Read up to ~64KB to get recent events
        raw = resp.read(65536).decode("utf-8")
        # Parse SSE format: "data: {...}\n\n"
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                    events.append(event)
                except json.JSONDecodeError:
                    pass
    except (urllib.error.URLError, OSError, ConnectionRefusedError):
        pass
    # Return most recent events (last N)
    return events[-limit:] if len(events) > limit else events


# ─── Query Functions ────────────────────────────────────────────────────────

def i0_status() -> dict:
    """Fabric health overview."""
    services = i0_services()
    protocols = i0_protocols()
    events = _fetch_events_from_agora(limit=50)

    total_svc = len(services)
    online = sum(1 for s in services if s.get("port_listening"))
    offline = total_svc - online

    total_proto = protocols.get("total", 0)
    active_proto = protocols.get("by_usage", {}).get("active", 0)

    # Per-layer breakdown
    layers: dict[str, dict] = {}
    for s in services:
        layer = s.get("layer", "L0")
        if layer not in layers:
            layers[layer] = {"services": 0, "online": 0}
        layers[layer]["services"] += 1
        if s.get("port_listening"):
            layers[layer]["online"] += 1

    return {
        "timestamp": _utc_now(),
        "total_services": total_svc,
        "services_online": online,
        "services_offline": offline,
        "total_protocols": total_proto,
        "active_protocols": active_proto,
        "event_count": len(events),
        "layers": dict(sorted(layers.items())),
    }


def i0_services() -> list[dict]:
    """All services with live probe data."""
    from runtime.matrix import list_services, resolve_path

    try:
        matrix_services = list_services()
    except FileNotFoundError:
        return []

    results: list[dict] = []
    for svc in matrix_services:
        layer = _SERVICE_LAYER.get(svc.name, "L1")
        has_port = svc.port is not None and svc.port > 0
        if svc.type == "scheduled":
            # Scheduled jobs (e.g. daily batch) aren't always running — skip port probe
            port_listening = True
            pid = None
        elif has_port:
            port_listening = _probe_port("127.0.0.1", svc.port)
            pid = _get_pid_for_port(svc.port) if port_listening else None
        else:
            # No port — trust matrix.yaml status (running/active = online)
            port_listening = svc.status in ("running", "active", "idle")
            pid = None

        # Health check
        health = "unknown"
        if svc.health_url:
            health = _health_check(svc.health_url)
        elif port_listening:
            health = "healthy"
        elif has_port:
            health = "unreachable"

        results.append({
            "name": svc.name,
            "type": svc.type,
            "port": svc.port,
            "status": svc.status,
            "port_listening": port_listening,
            "health": health,
            "pid": pid,
            "layer": layer,
        })

    return results


def i0_events(limit: int = 20) -> list[dict]:
    """Recent events from Agora SSE endpoint."""
    return _fetch_events_from_agora(limit)


def i0_protocols() -> dict:
    """Protocol registry summary from L0-registry.yaml."""
    proto_file = PROJECT_ROOT / "protocols" / "L0-registry.yaml"
    if not proto_file.exists():
        return {"total": 0, "by_usage": {}, "by_category": {}, "protocols": []}

    data = _read_yaml(proto_file)
    protocols = data.get("protocols", [])

    by_usage: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for p in protocols:
        usage = p.get("usage", "unknown")
        by_usage[usage] = by_usage.get(usage, 0) + 1
        cat = p.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total": len(protocols),
        "by_usage": by_usage,
        "by_category": by_category,
        "protocols": [
            {
                "name": p.get("name", ""),
                "version": p.get("version", ""),
                "category": p.get("category", ""),
                "status": p.get("status", ""),
                "usage": p.get("usage", ""),
                "transport": p.get("transport", []),
                "implementations": p.get("implementations", []),
            }
            for p in protocols
        ],
    }


def i0_graph() -> dict:
    """Dependency graph from matrix.yaml's depends_on field."""
    from runtime.matrix import list_services

    try:
        matrix_services = list_services()
    except FileNotFoundError:
        return {"nodes": [], "edges": []}

    nodes: list[dict] = []
    edges: list[dict] = []

    for svc in matrix_services:
        layer = _SERVICE_LAYER.get(svc.name, "L1")
        nodes.append({"name": svc.name, "layer": layer})
        for dep in svc.depends_on:
            if dep:
                edges.append({
                    "from": svc.name,
                    "to": dep,
                    "type": "HARD",
                })

    return {"nodes": nodes, "edges": edges}
