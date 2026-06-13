"""Test SSEBackend — bus-foundation flavor (in-process fan-out + client tracking)."""

from __future__ import annotations

from bus_foundation.backends.sse import SSEBackend
from bus_foundation.envelope import BusEnvelope


def test_client_count_tracks_connections() -> None:
    backend = SSEBackend()
    assert backend.client_count() == 0
    backend.client_connected()
    backend.client_connected()
    assert backend.client_count() == 2
    backend.client_disconnected()
    assert backend.client_count() == 1


def test_publish_dispatches_to_subscribers() -> None:
    backend = SSEBackend()
    received: list[BusEnvelope] = []

    def cb(env: BusEnvelope) -> None:
        received.append(env)

    backend.subscribe("sse-test:*", cb)
    env = BusEnvelope(type="sse-test:ping", source="x", payload={"k": 1})
    backend.publish(env)
    assert len(received) == 1


def test_is_available_returns_true() -> None:
    backend = SSEBackend()
    assert backend.is_available() is True
