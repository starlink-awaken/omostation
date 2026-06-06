"""Discovery commands: discover, sync."""

from __future__ import annotations

import asyncio
import contextlib
import json

from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_discover(args):
    """Auto-discover MCP services."""
    from agora.core.discovery import DiscoveryEngine  # type: ignore[import-not-found]

    workspace = args.workspace or None
    engine = DiscoveryEngine(workspace)

    if args.watch:
        registry = get_registry()

        async def _watch():
            async for _svc in engine.watch(registry, args.interval):
                pass

        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(_watch())
        return 0

    if args.probe:
        services = asyncio.run(engine.discover_all_async())
        print(f"Discovered {len(services)} MCP-capable services (incl. port probe):\n")
    else:
        services = engine.discover_all()
        print(f"Discovered {len(services)} MCP-capable services (strategies: known + pyproject + compose):\n")

    if args.register:
        registry = get_registry()
        count = engine.auto_register(registry)
        print(f"Discovered {len(services)} services, {count} newly registered\n")
    else:
        print(f"Discovered {len(services)} MCP-capable services:\n")

    if args.json:
        result = [
            {
                "name": s.name,
                "description": s.description,
                "mcp_endpoint": s.mcp_endpoint,
                "health_endpoint": s.health_endpoint,
                "port": s.port,
                "tags": s.tags,
                "source": s.source,
                "confidence": s.confidence,
            }
            for s in services
        ]
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in services:
            conf_bar = "#" * int(s.confidence * 10) + "-" * (10 - int(s.confidence * 10))
            print(f"  [{conf_bar}] {s.name}")
            print(f"         {s.description}")
            if s.mcp_endpoint:
                print(f"         endpoint: {s.mcp_endpoint}")
            if s.health_endpoint:
                print(f"         health:   {s.health_endpoint}")
            if s.tags:
                print(f"         tags:     {', '.join(s.tags)}")
            print(f"         source:   {s.source}")
            print()
    return 0


def cmd_sync(args):
    """Sync workspace services to Agora registry.

    Auto-discovers MCP services and registers them + prefix routes.
    """
    from agora.core.discovery import DiscoveryEngine
    from agora.core.registry import Service  # type: ignore[import-not-found]
    from agora.core.router import Router  # type: ignore[import-not-found]

    workspace = args.workspace or None
    engine = DiscoveryEngine(workspace)
    registry = get_registry()
    router = Router(registry)
    dry_run = getattr(args, "dry_run", False)

    services = engine.discover_all()

    to_register = [s for s in services if s.name not in {s2.name for s2 in registry.list_all()}]
    existing = [s for s in services if s.name in {s2.name for s2 in registry.list_all()}]

    if dry_run:
        print(f"{len(services)} services discovered in workspace")
        if to_register:
            print(f"  + {len(to_register)} new service(s) to register:")
            for s in to_register:
                print(f"    - {s.name}: {s.description}")
        if existing:
            print(f"  ~ {len(existing)} already registered")
        print("\n(dry-run: no changes written)")
        return 0

    for svc in to_register:
        port = svc.port or 0
        registry.register(
            Service(
                name=svc.name,
                description=svc.description,
                mcp_endpoint=svc.mcp_endpoint,
                health_endpoint=svc.health_endpoint,
                port=port,
                tags=svc.tags,
            )
        )
        print(f"  Registered: {svc.name}")

    print()
    for svc in services:
        if svc.name not in router.list_routes():
            router.add_route(svc.name, svc.name)
            print(f"  Routed: {svc.name}")

    print(f"\nSync complete: {len(to_register)} registered, {len(services)} services total")
    return 0
