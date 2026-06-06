"""Guided setup wizard — `agora init` for first-time users."""

from __future__ import annotations

import sys


def _confirm(step: str, prompt: str) -> bool:
    """Ask Y/n confirmation. Returns True unless user says n/no."""
    if not sys.stdin.isatty():
        return True  # Non-interactive: default yes
    print(f"\n━ {step}: {prompt} [Y/n] ", end="")
    choice = input().strip().lower()
    return choice not in ("n", "no")


def run_wizard() -> int:
    """Interactive setup wizard for first-time Agora users."""
    print("🏛️  Welcome to Agora — MCP Service Hub\n")
    print("This wizard will help you discover and register services.\n")

    from agora.core.discovery import DiscoveryEngine  # type: ignore[import-not-found]
    from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]

    registry = ServiceRegistry()  # Single instance for both register + health
    engine = DiscoveryEngine()

    # Step 1: Discover
    print("━ Step 1/4: Discovering MCP services in your workspace...")
    services = engine.discover_all()
    print(f"   Found {len(services)} MCP-capable services:\n")
    for i, s in enumerate(services, 1):
        conf = max(0, min(1, s.confidence or 0))
        conf_bar = "█" * int(conf * 10)
        print(f"   {i}. {s.name:20s} [{conf_bar}] {s.description[:50]}")

    # Step 2: Register
    if _confirm("Step 2/4", "Register services?"):
        count = engine.auto_register(registry)
        print(f"   ✅ Registered {count} new services ({len(registry.list_all())} total)")

    # Step 3: Health check
    if _confirm("Step 3/4", "Run health check?"):
        import asyncio

        asyncio.run(registry.health_check_all())
        healthy = len(registry.list_healthy())
        total = len(registry.list_all())
        status = "✅" if healthy == total else "⚠️"
        print(f"   {status} {healthy}/{total} services healthy")

    # Step 4: Quick start
    print("""
━ Step 4/4: You're ready to go!

   Quick commands:
     agora list          List all services
     agora stats         Show statistics
     agora search <kw>   Search services
     agora web           Start dashboard (localhost:7430)
     agora mcp           Start MCP server

   Next steps:
     pip install pallas  (unified CLI entry)
     pallas pipeline --goal 'your goal' --project .
""")

    return 0
