"""Test AsyncioBackend — 4 cases covering Protocol + publish + subscribe."""

import asyncio

import pytest

from agora.bus.backends.asyncio import AsyncioBackend
from agora.bus.envelope import BusEnvelope, EventType


class TestAsyncioBackend:
    def test_implements_protocol(self):
        b = AsyncioBackend()
        from agora.bus.backends.base import BusBackend

        assert isinstance(b, BusBackend)

    def test_is_available(self):
        b = AsyncioBackend()
        assert b.is_available() is True

    @pytest.mark.asyncio
    async def test_publish_subscribe_roundtrip(self):
        b = AsyncioBackend()
        received = []

        def callback(env: BusEnvelope) -> None:
            received.append(env)

        b.subscribe("pipeline:*", callback)
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED, source="t", payload={"x": 1}
        )
        b.publish(env)

        # Wait for queue to drain
        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0].type == "pipeline:completed"

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self):
        b = AsyncioBackend()
        received = []
        b.subscribe("*", lambda env: received.append(env))

        b.publish(BusEnvelope(type="x:y", source="t"))
        b.publish(BusEnvelope(type="a:b", source="t"))
        await asyncio.sleep(0.05)
        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe_cancels_drain_task(self):
        b = AsyncioBackend()
        sub_id = b.subscribe("pipeline:*", lambda env: None)
        task = b._subscribers[sub_id][2]

        assert task is not None
        assert b.unsubscribe(sub_id) is True

        await asyncio.sleep(0)
        assert task.cancelled() or task.done()
