"""omo bus adapter — bridges omo_sse_daemon to agora.bus facade.

Phase A.1: omo_sse_daemon still uses raw httpx + SSE URL for connection-level
control (heartbeat, reconnect backoff, SIGTERM handling). This adapter
adds the bus-facade subscription layer for *new* consumers, without
modifying the legacy daemon's internals.
"""
from __future__ import annotations

from typing import Callable

from bus_foundation.facade import event as bus_event


def subscribe_to_governance_events(callback: Callable) -> Callable:
    """Subscribe to governance-relevant events via agora.bus facade.

    Returns the original callback (so it can still be wired into omo_sse_daemon).

    Usage (in omo_sse_daemon or any omo consumer):
        from omo.omo_bus_adapter import subscribe_to_governance_events
        subscribe_to_governance_events(my_callback)

    Currently subscribes to: pipeline:*, debt:*, node_completed
    (matches omo_sse_daemon's _governance_types filter in listen_to_sse).
    """
    @bus_event.subscribe("pipeline:*")
    def on_pipeline(env) -> None:
        callback(env)

    @bus_event.subscribe("debt:*")
    def on_debt(env) -> None:
        callback(env)

    return callback
