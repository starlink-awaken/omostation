"""Tests for SSEBackend (R60, 5th bus backend)."""

from __future__ import annotations

import asyncio
from typing import Any

from agora.bus.backends.sse import SSEBackend
from agora.bus.envelope import BusEnvelope


class _StubSSEManager:
    """Minimal stand-in for agora.sse.SSEManager so we don't need a real loop."""

    def __init__(self):
        self.broadcasts: list[tuple[str, Any]] = []
        self._connected = 1

    def client_count(self) -> int:
        return self._connected

    async def broadcast(self, event_type: str, data: Any) -> int:
        self.broadcasts.append((event_type, data))
        return self._connected


def test_name_attribute() -> None:
    backend = SSEBackend(sse_manager=_StubSSEManager())
    assert backend.name == "sse"


def test_is_available_true_with_stub() -> None:
    backend = SSEBackend(sse_manager=_StubSSEManager())
    assert backend.is_available() is True


def test_publish_runs_broadcast_when_no_loop() -> None:
    """When called outside an event loop, broadcast should run inline via asyncio.run."""
    stub = _StubSSEManager()
    backend = SSEBackend(sse_manager=stub)
    env = BusEnvelope(
        type="pipeline:started", source="agora.bus.test", payload={"x": 1}
    )
    event_id = backend.publish(env)
    assert event_id == env.id
    assert len(stub.broadcasts) == 1
    ev_type, ev_data = stub.broadcasts[0]
    assert ev_type == "pipeline:started"
    assert ev_data["type"] == "pipeline:started"
    assert ev_data["payload"] == {"x": 1}
    assert ev_data["id"] == env.id


def test_publish_inside_running_loop_schedules_task() -> None:
    """When called inside an event loop, broadcast should be scheduled (not awaited)."""

    stub = _StubSSEManager()
    backend = SSEBackend(sse_manager=stub)

    async def _driver() -> None:
        env = BusEnvelope(type="message:received", source="agora.bus.test")
        backend.publish(env)  # schedules a task; does not block
        # Let the scheduled task run.
        await asyncio.sleep(0.05)

    asyncio.run(_driver())
    assert len(stub.broadcasts) == 1
    assert stub.broadcasts[0][0] == "message:received"


def test_subscribe_unsubscribe_roundtrip() -> None:
    backend = SSEBackend(sse_manager=_StubSSEManager())
    sub_id = backend.subscribe("*", lambda env: None)
    assert backend.unsubscribe(sub_id) is True
    assert backend.unsubscribe(sub_id) is False  # already gone


def test_client_count_delegates() -> None:
    stub = _StubSSEManager()
    backend = SSEBackend(sse_manager=stub)
    assert backend.client_count() == 1
