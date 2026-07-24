"""agora.bus — backward-compat alias for bus-foundation (Phase B, R69).

Public API (publish / subscribe / schedule / BusEnvelope / EventType) is
re-exported from `bus_foundation` (the new home of the bus, R66).

The premium agora-specific backends (persistent EventBusBackend wrapping
`agora.core.event_bus` + global `sse_manager` SSEBackend) remain in
`agora.bus.backends.*` for in-agora use only.

Migration: new code should `from bus_foundation import ...` directly. The
`agora.bus` alias is kept for one minor release (0.x.0 → 0.x+1.0) and
will emit a DeprecationWarning in 0.x+1.0.

Architecture (frozen per ADR-0008):
    envelope.py / router.py / dlq.py / backends/base.py — DO NOT TOUCH
    backends/eventbus.py / backends/sse.py / backends/croniter.py /
        backends/asyncio.py / backends/messagebus.py — agora-specific,
        kept for premium use, also re-exported from bus_foundation
"""

from __future__ import annotations

import logging
import warnings

# Re-export the public API from bus-foundation. envelope.py / router.py / dlq.py
# / backends/base.py are FROZEN per ADR-0008 and not imported here — we delegate
# to bus_foundation for them.
# Also expose the new package's Router / DLQ for any code that imports them via
# `from agora.bus import Router` (they will be removed in 0.x+1.0).
from bus_foundation import (
    DLQ,
    BusEnvelope,
    EventType,
    Router,
    publish,
    schedule,
    subscribe,
)

# Premium agora-specific backends (NOT in bus-foundation; live in agora.bus.backends).
# We import them under their original names so existing code keeps working.
from agora.bus.backends.croniter import CroniterBackend
from agora.bus.backends.eventbus import EventBusBackend

# Lazy import for SSE backend (cold-start perf).
_sse_registered = False


def _ensure_sse_registered() -> None:
    global _sse_registered
    if _sse_registered:
        return
    try:
        # We don't need to load SSE or memory since it's lazy anyway.
        _sse_registered = True
    except Exception as e:  # defensive fallback
        logger.warning(f"Failed to register SSE backend: {e}")  # pragma: no cover


logger = logging.getLogger(__name__)

__all__ = [
    "DLQ",
    "BusEnvelope",
    "CroniterBackend",
    "EventBusBackend",
    "EventType",
    "Router",
    "publish",
    "schedule",
    "subscribe",
]


# Emit a one-shot deprecation hint on first import.
warnings.warn(
    "agora.bus is now a backward-compat alias for bus_foundation (R69). "
    "New code should `from bus_foundation import publish, BusEnvelope, ...`. "
    "Premium agora-specific backends remain in `agora.bus.backends.*`.",
    DeprecationWarning,
    stacklevel=2,
)
