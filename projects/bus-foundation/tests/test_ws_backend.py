"""Test WebSocketBackend — 4 cases."""
import pytest

from bus_foundation.backends.base import BusBackend
from bus_foundation.backends.ws import WebSocketBackend
from bus_foundation.envelope import BusEnvelope, EventType


class TestWebSocketBackend:
    def test_implements_protocol(self):
        b = WebSocketBackend()
        assert isinstance(b, BusBackend)

    def test_is_available(self):
        b = WebSocketBackend()
        assert b.is_available() is True

    @pytest.mark.asyncio
    async def test_publish_fanout(self):
        b = WebSocketBackend()
        _, q1 = b.connect("pipeline:*")
        _, q2 = b.connect("*")
        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="t", payload={"x": 1})
        b.publish(env)
        # Drain manually (subscribe also works but we want direct check)
        assert not q1.empty()
        assert not q2.empty()
        assert q1.get_nowait().payload == {"x": 1}

    def test_disconnect(self):
        b = WebSocketBackend()
        cid, _ = b.connect("pipeline:*")
        assert b.disconnect(cid) is True
        assert b.disconnect("nonexistent") is False
