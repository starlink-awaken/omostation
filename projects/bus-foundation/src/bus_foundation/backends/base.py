"""BusBackend Protocol — contract all backends must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bus_foundation.envelope import BusEnvelope


@runtime_checkable
class BusBackend(Protocol):
    """Pluggable bus transport."""

    name: str

    def is_available(self) -> bool:
        """Return True if backend is reachable and writable."""
        ...

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish event. Returns event_id.

        MUST NOT retry on failure (RETRY-OWNERSHIP.md).
        MUST raise on failure (router catches + writes to DLQ).
        """
        ...

    def subscribe(self, pattern: str, callback) -> str:
        """Subscribe to events matching pattern. Returns subscription_id."""
        ...

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. Returns True if removed."""
        ...
