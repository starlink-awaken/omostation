"""EventBusBackend — wraps agora.core.event_bus.EventBus.

Phase A.0: thin wrapper, zero behavior change.
RETRY: passes through to underlying EventBus (3x, exponential backoff).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from agora.bus.envelope import BusEnvelope
from agora.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class EventBusBackend:
    """agora.core.event_bus wrapper for unified bus interface."""

    name = "eventbus"

    def __init__(self, storage_path: Path | str | None = None):
        self._bus = EventBus(storage_path=str(storage_path) if storage_path else None)

    def is_available(self) -> bool:
        try:
            return self._bus._storage_path.parent.exists()
        except Exception as e:  # defensive fallback
            logger.warning("eventbus_unavailable", e)
            return False

    def publish(self, envelope: BusEnvelope) -> str:
        return self._bus.publish(
            event_type=envelope.type,
            payload=envelope.payload,
            source=envelope.source,
            trace_id=envelope.trace_id or "",
        )

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe via EventBus.register_hook (in-process delivery).

        Why hook not subscribe(): agora EventBus.subscribe is HTTP callback
        (fire-and-forget POST to subscriber URL), wrong primitive for
        same-process BusBackend wrapper. register_hook gives in-process
        delivery, which is what BusBackend Protocol promises.

        NOTE: cross-process HTTP delivery is publisher's responsibility,
        not subscriber's.
        """

        def hook(event_dict: dict) -> None:
            envelope = BusEnvelope.from_dict(
                {
                    "id": event_dict.get("id"),
                    "time": event_dict.get("time"),
                    "type": event_dict.get("type"),
                    "source": event_dict.get("source"),
                    "trace_id": event_dict.get("trace_id"),
                    "payload": event_dict.get("payload", {}),
                }
            )
            callback(envelope)

        self._bus.register_hook(hook)
        return f"hook-{id(hook):x}"

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. EventBus hooks have no native unsubscribe."""
        return False

    def get_event_log(self, limit: int = 50):
        """Pass-through to EventBus (for tests)."""
        return self._bus.get_event_log(limit=limit)
