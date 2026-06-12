"""Test EventBusBackend (bus-foundation flavor) — Protocol + in-process dispatch."""
from __future__ import annotations

from bus_foundation.backends.base import BusBackend
from bus_foundation.backends.eventbus import EventBusBackend
from bus_foundation.envelope import BusEnvelope, EventType


class TestEventBusBackendProtocol:
    def test_implements_protocol(self) -> None:
        backend = EventBusBackend()
        assert isinstance(backend, BusBackend)

    def test_is_available_default_true(self) -> None:
        backend = EventBusBackend()
        assert backend.is_available() is True

    def test_publish_returns_event_id(self) -> None:
        backend = EventBusBackend()
        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test", payload={"x": 1})
        result_id = backend.publish(env)
        assert result_id == env.id

    def test_subscribe_dispatches(self) -> None:
        backend = EventBusBackend()
        received: list[BusEnvelope] = []

        def cb(env: BusEnvelope) -> None:
            received.append(env)

        sub_id = backend.subscribe("pipeline:*", cb)
        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test", payload={"k": "v"})
        backend.publish(env)
        assert len(received) == 1
        assert received[0].id == env.id
        # Unsubscribe
        assert backend.unsubscribe(sub_id) is True
        backend.publish(env)
        assert len(received) == 1  # no new event

    def test_pattern_prefix_match(self) -> None:
        backend = EventBusBackend()
        received: list[BusEnvelope] = []

        def cb(env: BusEnvelope) -> None:
            received.append(env)

        backend.subscribe("foo:*", cb)
        env_match = BusEnvelope(type="foo:bar", source="x")
        env_nomatch = BusEnvelope(type="bar:foo", source="x")
        backend.publish(env_match)
        backend.publish(env_nomatch)
        assert len(received) == 1
        assert received[0].id == env_match.id

    def test_pattern_exact_match(self) -> None:
        backend = EventBusBackend()
        received: list[BusEnvelope] = []

        def cb(env: BusEnvelope) -> None:
            received.append(env)

        backend.subscribe("foo:bar", cb)
        backend.publish(BusEnvelope(type="foo:bar", source="x"))
        backend.publish(BusEnvelope(type="foo:baz", source="x"))
        assert len(received) == 1
