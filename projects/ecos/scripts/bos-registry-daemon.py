#!/usr/bin/env python3
"""
BOS Registry Daemon — watch L0-constraints.yaml → auto-update routes.json

Monitors the domain_registry in L0-constraints.yaml for changes.
On change: re-read registry → update ~/.ecos/bos/routes.json → notify MCP.

Usage:
    python3 bos-registry-daemon.py [--interval 60] [--once]

Designed for launchd or background job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Try to import yaml for fallback parsing
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ── Paths ──
# SSOT (single source of truth) — project repo
L0_CONSTRAINTS_SSOT = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "l0" / "constraints.yaml"
# L4 cache copy — synced from SSOT
L0_CONSTRAINTS_L4 = Path.home() / "Documents" / "@学习进化" / "_knowledge" / "10-systems" / "基建架构" / "L0-constraints.yaml"
ROUTES_JSON = Path.home() / ".ecos" / "bos" / "routes.json"
DOMAIN_MANAGER = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "services" / "governance" / "domain_manager.py"
LOG_FILE = Path.home() / ".ecos" / "bos" / "daemon.log"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def update_routes() -> bool:
    """Re-read L0-constraints.yaml and update routes.json.
    
    Returns True if routes.json was updated.
    """
    # Pick best available L0 constraints source (SSOT first, then L4 cache)
    L0_PATH = L0_CONSTRAINTS_SSOT if L0_CONSTRAINTS_SSOT.exists() else L0_CONSTRAINTS_L4
    if not L0_PATH.exists():
        log(f"⚠️  L0-constraints.yaml not found (SSOT={L0_CONSTRAINTS_SSOT}, L4={L0_CONSTRAINTS_L4})")
        return False

    registry = None

    # Method 1: Use domain_manager to reload and export routes
    try:
        # Add governance/ to sys.path so domain_manager can import l0_audit / audit_unified
        sys.path.insert(0, str(DOMAIN_MANAGER.parent))
        from importlib.machinery import SourceFileLoader
        dm = SourceFileLoader("dm", str(DOMAIN_MANAGER)).load_module()
        registry = dm.load_registry()
        log("✅ Loaded registry via domain_manager")
    except Exception as e:
        log(f"ℹ️  domain_manager load failed: {e}")

    # Method 2: Fallback — parse YAML directly
    if registry is None and HAS_YAML:
        try:
            with open(L0_PATH) as f:
                data = yaml.safe_load(f)
            registry = data.get("domain_registry", [])
            log(f"✅ Loaded registry via YAML fallback ({len(registry)} domains)")
        except Exception as e:
            log(f"⚠️  YAML fallback also failed: {e}")
            return False

    if registry is None:
        log("⚠️  No registry source available")
        return False

    # Parse domain_registry into routes format
    routes = {"_generated": datetime.now().isoformat(), "_source": str(L0_PATH), "routes": {}}
    for entry in registry:
        domain_id = entry.get("id", entry.get("name", ""))
        if domain_id:
            routes["routes"][domain_id] = {
                "id": domain_id,
                "name": entry.get("name", ""),
                "layer": entry.get("layer", "?"),
                "type": entry.get("domain_type", "?"),
                "path": str(entry.get("path", "")),
                "state_md": str(entry.get("state_md", "")),
                "claude_md": str(entry.get("claude_md", "")),
                "kems_planes": entry.get("kems_planes", []),
            }

    # Write routes.json
    ROUTES_JSON.parent.mkdir(parents=True, exist_ok=True)
    ROUTES_JSON.write_text(json.dumps(routes, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"✅ Updated routes.json: {len(routes['routes'])} domains")
    return True


def notify_mcp() -> None:
    """Notify MCP server that routes have changed.
    
    Creates a touch file that the MCP server can watch.
    """
    touch = ROUTES_JSON.parent / ".updated"
    touch.write_text(datetime.now().isoformat(), encoding="utf-8")


def main() -> int:
    interval = 60
    run_once = False

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--interval" and i + 1 < len(args):
            interval = int(args[i + 1])
        elif arg == "--once":
            run_once = True

    log(f"BOS Registry Daemon starting (interval={interval}s)")
    
    # Warm L2 → L1 cache if domain_manager is available
    try:
        sys.path.insert(0, str(DOMAIN_MANAGER.parent))
        from importlib.machinery import SourceFileLoader
        dm = SourceFileLoader("dm", str(DOMAIN_MANAGER)).load_module()
        warm_stats = dm._cache_warm()
        log(f"Cache warm: L2={warm_stats['l2_items']} → L1={warm_stats['warmed']}")
    except Exception:
        log("Cache warm skipped (domain_manager not available)")
    
    if run_once:
        if update_routes():
            notify_mcp()
        return 0

    # Watch both SSOT and L4 cache copies
    last_mtime = max(get_mtime(L0_CONSTRAINTS_SSOT), get_mtime(L0_CONSTRAINTS_L4))
    if not update_routes():
        log("⚠️  Initial route update failed")

    try:
        while True:
            time.sleep(interval)
            current = max(get_mtime(L0_CONSTRAINTS_SSOT), get_mtime(L0_CONSTRAINTS_L4))
            if current != last_mtime:
                log(f"Detected change in L0-constraints.yaml")
                if update_routes():
                    notify_mcp()
                last_mtime = current
    except KeyboardInterrupt:
        log("Daemon stopped")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
