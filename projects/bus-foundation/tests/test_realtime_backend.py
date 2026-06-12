"""Test RealtimeBackend — 4 cases."""
from bus_foundation.backends.base import BusBackend
from bus_foundation.backends.realtime import RealtimeBackend
from bus_foundation.envelope import BusEnvelope, EventType


class TestRealtimeBackend:
    def test_implements_protocol(self):
        b = RealtimeBackend()
        assert isinstance(b, BusBackend)

    def test_is_available(self):
        b = RealtimeBackend()
        assert b.is_available() is True

    def test_version_increments(self):
        b = RealtimeBackend()
        assert b.get_version("task-1") == 0
        b.publish(BusEnvelope(type="task-1", source="t"))
        assert b.get_version("task-1") == 1
        b.publish(BusEnvelope(type="task-1", source="t"))
        assert b.get_version("task-1") == 2

    def test_subscriber_receives_version(self):
        b = RealtimeBackend()
        received: list[tuple[BusEnvelope, int]] = []
        b.subscribe("task-2", lambda env, v: received.append((env, v)))
        b.publish(BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="t", payload={"x": 1}))
        b.publish(BusEnvelope(type="task-2", source="t", payload={"x": 2}))
        # Subscriber matches on task_id (envelope.type); first publish used a
        # different type, so only the second matches.
        assert len(received) == 1
        assert received[0][1] == 1
        assert received[0][0].payload == {"x": 2}
