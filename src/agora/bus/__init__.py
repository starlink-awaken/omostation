"""agora.bus — unified bus interface (Phase A.1)."""
from __future__ import annotations

import logging
from typing import Callable

from agora.bus.backends.croniter import CroniterBackend
from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope, EventType
from agora.bus.router import Router

logger = logging.getLogger(__name__)

# Multi-backend: route by envelope.backend, default = eventbus
_backends: dict[str, object] = {
    "eventbus": EventBusBackend(),
    "croniter": CroniterBackend(),
}
_croniter = _backends["croniter"]  # expose for schedule() to use

# Default router uses eventbus
_default_backend = _backends["eventbus"]
_default_dlq = DLQ()
_router = Router(backend=_default_backend, dlq=_default_dlq)

# Start croniter scheduler thread
_croniter.start()

__all__ = ["BusEnvelope", "EventType", "publish", "subscribe", "schedule"]


def publish(envelope: BusEnvelope) -> str:
    """Publish via the appropriate backend (envelope.backend, default eventbus)."""
    backend_name = getattr(envelope, "backend", None) or "eventbus"
    backend = _backends.get(backend_name)
    if backend is None:
        # Unknown backend — fall through to default router + DLQ
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
    """Decorator: schedule a recurring task.

    Usage:
        @schedule("every 5m")
        def heartbeat() -> None: ...
    """
    if not isinstance(expr, str):
        raise TypeError(f"schedule expression must be str, got {type(expr)}")

    def decorator(fn: Callable) -> Callable:
        sub_id = _croniter.subscribe(expr, fn)
        logger.warning("bus_scheduled: expr=%s sub_id=%s fn=%s", expr, sub_id, fn.__name__)
        return fn

    return decorator
