"""Test RealtimeBackend + WebSocketBackend fix from R73 code review."""
from bus_foundation.backends.realtime import RealtimeBackend
from bus_foundation.envelope import BusEnvelope


class TestRealtimeUnsubscribeFix:
    def test_unsubscribe_now_truthful(self):
        """R73 fix: unsubscribe() should return True when sub_id exists."""
        b = RealtimeBackend()
        received = []
        sub_id = b.subscribe("task-1", lambda env, v: received.append((env, v)))
        assert b.unsubscribe(sub_id) is True

    def test_unsubscribe_unknown_returns_false(self):
        """R73 fix: still returns False for unknown sub_id."""
        b = RealtimeBackend()
        assert b.unsubscribe("nonexistent") is False

    def test_subscribers_removed_after_unsubscribe(self):
        """R73 fix: after unsubscribe, publish() doesn't call the callback."""
        b = RealtimeBackend()
        received = []
        sub_id = b.subscribe("task-1", lambda env, v: received.append((env, v)))
        b.unsubscribe(sub_id)
        b.publish(BusEnvelope(type="task-1", source="t"))
        assert received == []
