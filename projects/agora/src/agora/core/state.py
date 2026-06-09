"""Global application state — single source of truth for shared instances."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
    from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]
    from agora.core.router import Router  # type: ignore[import-not-found]

_registry: ServiceRegistry | None = None
_bus: EventBus | None = None
_router: Router | None = None


def get_registry(storage_path: str | None = None) -> ServiceRegistry:
    """Return the global ServiceRegistry singleton (lazy-init)."""
    global _registry
    if _registry is None:
        from agora.core.registry import ServiceRegistry

        _path = storage_path or os.environ.get("AGORA_STORAGE_PATH")
        _registry = ServiceRegistry(storage_path=_path)
    return _registry


def get_event_bus(registry: ServiceRegistry | None = None) -> EventBus:
    """Return the global EventBus singleton (lazy-init)."""
    global _bus
    if _bus is None:
        from agora.core.event_bus import EventBus

        _bus = EventBus(registry=registry or get_registry())
    return _bus


def get_router(
    registry: ServiceRegistry | None = None, event_bus: EventBus | None = None
) -> Router:
    """Return the global Router singleton (lazy-init)."""
    global _router
    if _router is None:
        from agora.core.router import Router

        _router = Router(
            registry or get_registry(), event_bus=event_bus or get_event_bus()
        )
    return _router


def reset():
    """Reset all global state (for testing only)."""
    global _registry, _bus, _router

    _registry = None
    _bus = None
    _router = None
