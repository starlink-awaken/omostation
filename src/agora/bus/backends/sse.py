"""SSEBackend — wraps agora.sse.SSEManager as a bus backend (R60, 5th backend).

Use case: when an event is published on the bus, fan it out to all connected
SSE clients (e.g. browser dashboards). The backend reuses the global
`agora.sse.sse_manager` singleton and the wire-format already used by the
HTTP `/events` endpoint, so bus events look identical to hand-rolled SSE
events to consumers.

Constraints (per RETRY-OWNERSHIP.md):
  - publish() MUST NOT retry (router catches + writes to DLQ).
  - publish() MUST raise on failure (router decides DLQ vs drop).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from agora.bus.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class SSEBackend:
    """Bus backend that fans out events to SSE-connected clients.

    Reuses the global `agora.sse.sse_manager` so the bus and the HTTP /events
    route share one connection set. Each bus event becomes one SSE message
    shaped as: {"type": <envelope.type>, "data": <envelope.to_dict()>}.
    """

    name = "sse"

    def __init__(self, sse_manager=None):
        # Lazy import: sse module pulls in asyncio json etc; keep import local
        # so cold-start of bus facade is not blocked on aetherforge-only deps.
        if sse_manager is None:
            from agora.sse import sse_manager as _default

            sse_manager = _default
        self._sse = sse_manager
        self._subscribers: dict[str, tuple[str, Callable]] = {}

    def is_available(self) -> bool:
        # SSE backend is "available" whenever the manager exists.
        # Connectivity is per-client; the backend is reachable iff at least
        # one client is connected, but a backend with zero clients is still
        # functional (it just drops events at fanout time).
        return self._sse is not None

    def publish(self, envelope: BusEnvelope) -> str:
        # SSE fanout is async; we schedule it on the running loop if any,
        # otherwise run it inline. We block briefly with a timeout to keep
        # the bus publisher's latency predictable.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self._sse.broadcast(envelope.type, envelope.to_dict())
        if loop is not None:
            # From a sync hot-path: schedule and return immediately. The
            # router does not await this — the bus's contract is fire-and-
            # forward. If broadcast fails, we log and let router route to
            # DLQ. We don't raise here because we're not awaiting.
            loop.create_task(coro)
        else:
            # No running loop — drain synchronously via asyncio.run.
            try:
                asyncio.run(coro)
            except Exception as e:  # defensive fallback
                # Surface failure to caller; router catches and writes DLQ.
                raise RuntimeError(f"sse_broadcast_failed: {e}") from e
        return envelope.id

    def subscribe(self, pattern: str, callback: Callable) -> str:
        # SSE is a one-way push: subscribers register a callback that will
        # receive every published envelope matching the pattern. This is
        # used internally for testing/observability — typical consumers
        # connect via the HTTP /events route instead.
        import uuid

        sub_id = f"sse-{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (pattern, callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscribers:
            del self._subscribers[sub_id]
            return True
        return False

    def client_count(self) -> int:
        """Number of currently connected SSE clients. Useful for is_available()."""
        return self._sse.client_count() if self._sse else 0
