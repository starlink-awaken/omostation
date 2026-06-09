"""
L0 Registry Loader — replace hardcoded agora-routes.json / agora-services.json
               and mcp_bootstrap.KNOWN_SERVICES with dynamic L0 M1 nodes.

Design:
  - Loads BOSRoute M1 nodes → route mappings (tool → service)
  - Loads Component M1 nodes with BOS_URI → service definitions
  - Falls back to static override YAML for non-derivable data (command/args)
  - Memoized per process, TTL 300s

Usage:
    from agora.l0_registry_loader import L0RegistryLoader
    routes = L0RegistryLoader.load_routes()   # {tool_name: service_name}
    services = L0RegistryLoader.load_services() # [service_defs] for mcp_bootstrap
"""

from __future__ import annotations

import time
import yaml
from pathlib import Path

HOME = Path.home()
L0_M1 = (
    HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
)
OVERRIDE_PATH = Path(__file__).parent / "l0_registry_overrides.yaml"
CACHE_TTL = 300  # seconds


class _Cache:
    _routes: list[dict] | None = None
    _services: list[dict] | None = None
    _known: dict[str, dict] | None = None
    _ts: float = 0


def _load_overrides() -> dict:
    """Load static overrides for non-derivable service configs."""
    if OVERRIDE_PATH.exists():
        with open(OVERRIDE_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _scan_bosroute_nodes() -> list[dict]:
    """Scan BOSRoute M1 nodes and yield route entries."""
    routes = []
    bos_dir = L0_M1 / "bosroute"
    if not bos_dir.exists():
        return routes
    for f in sorted(bos_dir.glob("*.yaml")):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if (
                not data
                or data.get("type") != "Component"
                or data.get("subtype") != "BOSRoute"
            ):
                continue
            uri = data.get("name", "")
            if not uri:
                continue
            routes.append(
                {
                    "uri": uri,
                    "service": _uri_to_service(uri),
                    "status": data.get("status", "active"),
                    "layer": data.get("layer", "?"),
                    "description": data.get("description", ""),
                }
            )
        except Exception:
            continue
    return routes


def _scan_component_nodes() -> list[dict]:
    """Scan Component M1 nodes with BOS_URI protocol for service definitions."""
    comps = []
    comp_dir = L0_M1 / "component"
    if not comp_dir.exists():
        return comps
    for f in sorted(comp_dir.glob("*.yaml")):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if not data:
                continue
            props = data.get("properties") or {}
            if props.get("protocol") != "BOS_URI":
                continue
            comps.append(
                {
                    "name": data.get("name", ""),
                    "status": data.get("status", "active"),
                    "layer": props.get("layer", "?"),
                    "description": data.get("description", ""),
                    "domain": data.get("domain", ""),
                }
            )
        except Exception:
            continue
    return comps


def _uri_to_service(uri: str) -> str:
    """Convert bos:// URI to service name.
    e.g. bos://cockpit/tools/* → cockpit
         bos://kairon/minerva  → minerva
         bos://agora/routes/*  → agora-internal
    """
    parts = uri.replace("bos://", "").split("/")
    if len(parts) >= 2 and parts[0] == "kairon":
        return parts[1]
    return parts[0] if parts else uri


def _invalidate_cache():
    _Cache._routes = None
    _Cache._services = None
    _Cache._known = None
    _Cache._ts = 0


def _ensure_cache():
    now = time.time()
    if _Cache._routes is not None and (now - _Cache._ts) < CACHE_TTL:
        return
    _Cache._routes = _scan_bosroute_nodes()
    _Cache._services = _scan_component_nodes()
    _Cache._ts = now
    _Cache._known = None  # rebuilt on demand in load_known_services


def load_routes() -> dict[str, str]:
    """Load tool→service route mappings from L0 M1 nodes.

    Returns dict like {"research_now": "minerva", "cards_status": "cockpit", ...}

    Merges with static overrides (overrides win).
    """
    _ensure_cache()
    overrides = _load_overrides().get("routes", {})

    # Build from BOSRoute nodes
    routes = {}
    for r in _Cache._routes:
        svc = r["service"]
        r["uri"]
        if svc == "agora-internal":
            continue  # internal routes stay in bootstrap
        # Derive tool names from URI pattern
        # bos://cockpit/tools/* → tools under cockpit
        # bos://kairon/minerva → minerva_* tools
        routes[f"{svc}_default"] = svc

    # Apply overrides (the detailed 80+ mapping)
    routes.update(overrides)
    return routes


def load_services() -> list[dict]:
    """Load service definitions for agora-services.json replacement.

    Each entry: {"name": "...", "protocol": "mcp", "mcp_endpoint": "...", ...}
    """
    _ensure_cache()
    overrides = _load_overrides().get("services", {})
    svc_defs = {}

    # Build from Component M1 nodes
    for c in _Cache._services:
        name = c["name"]
        svc_defs[name] = {
            "name": name,
            "description": c.get("description", ""),
            "protocol": "mcp",
            "protocol_config": {"method": "GET"},
            "mcp_endpoint": f"http://127.0.0.1:0/{name}",
            "health_endpoint": "",
            "port": 0,
            "tags": [],
            "instances": [],
            "provider_info": None,
            "healthy": True,
            "last_health_check": 0.0,
        }

    # Apply overrides (fills in real endpoints/ports)
    for name, cfg in overrides.items():
        if name in svc_defs:
            svc_defs[name].update(cfg)
        else:
            svc_defs[name] = cfg

    return list(svc_defs.values())


def load_known_services() -> dict[str, dict]:
    """Load known service startup configs for mcp_bootstrap replacement.

    Returns dict like KNOWN_SERVICES in mcp_bootstrap.py:
    {"minerva": {"command": "uv", "args": [...], "description": "...", "source": "kairon"}}
    """
    _ensure_cache()
    overrides = _load_overrides().get("known_services", {})

    # Build from Component M1
    known = {}
    for c in _Cache._services:
        name = c["name"]
        known[name] = {
            "command": "uv",
            "args": ["run", "--package", name, "python", "-m", f"{name}.mcp_server"],
            "description": c.get("description", ""),
            "source": "l0",
        }

    # Apply overrides
    known.update(overrides)
    return known


# CLI: inspect current L0 registry state
if __name__ == "__main__":
    import sys

    if "--invalidate" in sys.argv:
        _invalidate_cache()
        print("Cache invalidated.")

    routes = load_routes()
    services = load_services()
    known = load_known_services()

    print(
        f"L0 Registry Loader — {len(routes)} routes, {len(services)} services, {len(known)} known"
    )
    print()
    print("Routes (tool → service):")
    for tool, svc in sorted(routes.items())[:15]:
        print(f"  {tool:30s} → {svc}")
    if len(routes) > 15:
        print(f"  ... and {len(routes) - 15} more")
    print()
    print("Known services:")
    for name, cfg in sorted(known.items()):
        src = cfg.get("source", "?")
        desc = cfg.get("description", "")[:50]
        print(f"  {name:20s} [{src:10s}] {desc}")
