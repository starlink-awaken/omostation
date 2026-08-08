"""Router — dispatch envelope to backend, fall back to DLQ on failure."""

from __future__ import annotations

import logging

from agora.bus.backends.base import BusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class Router:
    """Dispatches envelopes to a backend, writes failures to DLQ.

    RETRY OWNERSHIP: this layer does NOT retry. See RETRY-OWNERSHIP.md.
    """

    def __init__(self, backend: BusBackend, dlq: DLQ | None = None):
        self.backend = backend
        self.dlq = dlq or DLQ()

    def publish(self, envelope: BusEnvelope) -> str:
        if not self.backend.is_available():
            logger.warning(
                "router_backend_unavailable: backend=%s event_id=%s",
                self.backend.name,
                envelope.id,
            )
            self.dlq.enqueue(
                event_id=envelope.id,
                backend=self.backend.name,
                envelope_json=envelope.to_json(),
                error="backend unavailable",
            )
            return envelope.id

        try:
            return self.backend.publish(envelope)
        except Exception as e:  # defensive fallback
            logger.error(
                "router_publish_failed: backend=%s event_id=%s error=%s",
                self.backend.name,
                envelope.id,
                e,
            )
            self.dlq.enqueue(
                event_id=envelope.id,
                backend=self.backend.name,
                envelope_json=envelope.to_json(),
                error=str(e),
            )
            return envelope.id
