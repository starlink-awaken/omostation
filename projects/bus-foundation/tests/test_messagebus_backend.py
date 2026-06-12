"""Test MessageBusBackend — in-process agent pub/sub with pattern dispatch."""
from __future__ import annotations

from bus_foundation.backends.messagebus import MessageBusBackend
from bus_foundation.envelope import BusEnvelope


def test_subscribe_dispatches_matching() -> None:
    backend = MessageBusBackend()
    received: list[BusEnvelope] = []

    def cb(env: BusEnvelope) -> None:
        received.append(env)

    backend.subscribe("agent:*", cb)
    env_match = BusEnvelope(type="agent:request", source="x")
    env_nomatch = BusEnvelope(type="system:event", source="x")
    backend.publish(env_match)
    backend.publish(env_nomatch)
    assert len(received) == 1
    assert received[0].id == env_match.id


def test_unsubscribe_removes() -> None:
    backend = MessageBusBackend()
    received: list[BusEnvelope] = []

    def cb(env: BusEnvelope) -> None:
        received.append(env)

    sub_id = backend.subscribe("*", cb)
    backend.publish(BusEnvelope(type="t:1", source="x"))
    assert len(received) == 1
    assert backend.unsubscribe(sub_id) is True
    backend.publish(BusEnvelope(type="t:2", source="x"))
    assert len(received) == 1
