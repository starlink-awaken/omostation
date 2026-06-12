"""bus_foundation — unified bus interface (Phase B, R66 split from agora/bus).

Public API:
    publish(envelope)  — publish an event
    subscribe(pattern, fn)  — register a subscriber
    schedule(expr, fn)  — schedule a recurring task

Architecture: facade → router → backend (5 in 0.1.0) → DLQ on failure.

The bus-foundation package is agora-independent. Consumers that want
agora's premium backends (persistent EventBus, global sse_manager) can
import them from `agora.bus.backends` directly.
"""
from __future__ import annotations

import logging
from typing import Callable

from bus_foundation.backends.croniter import CroniterBackend
from bus_foundation.backends.eventbus import EventBusBackend
from bus_foundation.dlq import DLQ
from bus_foundation.envelope import BusEnvelope, EventType
from bus_foundation.router import Router

logger = logging.getLogger(__name__)

# Multi-backend registry — extend here when adding new backends.
_backends: dict[str, object] = {
    "eventbus": EventBusBackend(),
    "croniter": CroniterBackend(),
}
_croniter = _backends["croniter"]

_default_backend = _backends["eventbus"]
_default_dlq = DLQ()
_router = Router(backend=_default_backend, dlq=_default_dlq)

# Start croniter scheduler thread (no-op if not used)
_croniter.start()

__all__ = ["BusEnvelope", "EventType", "publish", "subscribe", "schedule"]


def publish(envelope: BusEnvelope) -> str:
    """Publish via the appropriate backend (envelope.backend, default eventbus)."""
    backend_name = getattr(envelope, "backend", None) or "eventbus"
    backend = _backends.get(backend_name)
    if backend is None:
        return _router.publish(envelope)
    if not backend.is_available():
        _default_dlq.enqueue(
            event_id=envelope.id,
            backend=backend_name,
            envelope_json=envelope.to_json(),
            error="backend unavailable",
        )
        return envelope.id
    try:
        return backend.publish(envelope)
    except Exception as e:
        _default_dlq.enqueue(
            event_id=envelope.id,
            backend=backend_name,
            envelope_json=envelope.to_json(),
            error=str(e),
        )
        return envelope.id


def subscribe(pattern: str) -> Callable:
    """Decorator: register a subscriber for a pattern (uses eventbus backend)."""

    def decorator(fn: Callable) -> Callable:
        sub_id = _default_backend.subscribe(pattern, fn)
        logger.warning("bus_subscribed: pattern=%s sub_id=%s fn=%s", pattern, sub_id, fn.__name__)
        return fn

    return decorator


def schedule(expr: str) -> Callable:
    """Decorator: schedule a recurring task via the croniter backend."""

    def decorator(fn: Callable) -> Callable:
        sub_id = _croniter.subscribe(expr, fn)
        logger.warning("bus_scheduled: expr=%s sub_id=%s fn=%s", expr, sub_id, fn.__name__)
        return fn

    return decorator
