"""Test AsyncioBackend — in-process pubsub via asyncio.Queue."""
from __future__ import annotations

import asyncio

from bus_foundation.backends.asyncio import AsyncioBackend
from bus_foundation.envelope import BusEnvelope


async def test_publish_queues_envelope_for_subscriber() -> None:
    backend = AsyncioBackend()
    received: list[BusEnvelope] = []

    def cb(env: BusEnvelope) -> None:
        received.append(env)

    backend.subscribe("asyncio-test:*", cb)
    env = BusEnvelope(type="asyncio-test:ping", source="x", payload={"k": 1})
    backend.publish(env)
    # Give the drain task a chance to dispatch.
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].id == env.id


def test_is_available_returns_true() -> None:
    backend = AsyncioBackend()
    assert backend.is_available() is True
