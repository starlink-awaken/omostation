"""Routing and instance commands: route, routes, instance."""

from __future__ import annotations

import json

from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_route(args):
    """Add a tool route."""
    registry = get_registry()
    router = Router(registry)
    router.add_route(args.tool, args.service)
    print(f"Route added: '{args.tool}' -> '{args.service}'")


def cmd_routes(_args):
    """List all routes."""
    registry = get_registry()
    router = Router(registry)
    print(json.dumps(router.list_routes(), ensure_ascii=False, indent=2))


def cmd_instance(args):
    """Load-balanced instance operations."""
    registry = get_registry()
    router = Router(registry)
    if args.instance_cmd == "add":
        router._add_instance(args.service, args.mcp, args.health, args.port)
        print(f"Instance added: {args.service} -> {args.mcp}")
    return 0
