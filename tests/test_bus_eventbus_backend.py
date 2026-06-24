"""Test EventBusBackend — 4 cases covering Protocol + is_available + publish."""

from pathlib import Path

from agora.bus.backends.base import BusBackend
from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.envelope import BusEnvelope, EventType


class TestEventBusBackendProtocol:
    def test_implements_protocol(self, tmp_path: Path):
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        assert isinstance(backend, BusBackend)

    def test_is_available_default_true(self, tmp_path: Path):
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        assert backend.is_available() is True

    def test_publish_returns_event_id(self, tmp_path: Path):
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
            payload={"x": 1},
        )
        result_id = backend.publish(env)
        # EventBus generates its own id internally; just verify we got one back
        assert isinstance(result_id, str) and len(result_id) > 0

    def test_persist_in_storage(self, tmp_path: Path):
        storage = tmp_path / "eb.json"
        backend = EventBusBackend(storage_path=storage)
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
            payload={"k": "v"},
        )
        backend.publish(env)
        backend2 = EventBusBackend(storage_path=storage)
        log = backend2.get_event_log(limit=10)
        assert len(log) >= 1
        # EventBus generates id internally; verify by type+source
        assert any(
            e.get("type") == env.type and e.get("source") == env.source for e in log
        )
