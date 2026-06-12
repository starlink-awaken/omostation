"""agora.bus — unified bus interface (Phase A.0)."""
from __future__ import annotations

import logging
from typing import Callable

from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope, EventType
from agora.bus.router import Router

logger = logging.getLogger(__name__)

_default_backend = EventBusBackend()
_default_dlq = DLQ()
_router = Router(backend=_default_backend, dlq=_default_dlq)

__all__ = ["BusEnvelope", "EventType", "publish", "subscribe", "schedule"]


def publish(envelope: BusEnvelope) -> str:
    return _router.publish(envelope)


def subscribe(pattern: str) -> Callable:
    """Decorator: register a subscriber for a pattern.

    Usage:
        @subscribe("pipeline:*")
        def on_pipeline(env: BusEnvelope) -> None: ...
    """

    def decorator(fn: Callable) -> Callable:
        sub_id = _default_backend.subscribe(pattern, fn)
        logger.warning("bus_subscribed", pattern, sub_id, fn.__name__)
        return fn

    return decorator


def schedule(expr: str) -> Callable:
    """Decorator: schedule a recurring task. Phase A.1 stub."""
    raise NotImplementedError(
        "schedule() lands in Phase A.1 (R58). See Plans/swirling-snuggling-wilkes.md."
    )
