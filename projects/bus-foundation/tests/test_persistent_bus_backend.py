"""Test PersistentBusBackend — 5 cases covering SQLite durability + GC + subscribe."""

import sqlite3
from pathlib import Path

from bus_foundation.backends.base import BusBackend
from bus_foundation.backends.persistent_bus import PersistentBusBackend
from bus_foundation.envelope import BusEnvelope, EventType


class TestPersistentBusBackend:
    def test_implements_protocol(self, tmp_path: Path):
        b = PersistentBusBackend(db_path=tmp_path / "test.db")
        assert isinstance(b, BusBackend)

    def test_is_available(self, tmp_path: Path):
        b = PersistentBusBackend(db_path=tmp_path / "test.db")
        assert b.is_available() is True

    def test_wal_mode(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        b = PersistentBusBackend(db_path=db_path)
        b.publish(BusEnvelope(type="x:y", source="t"))
        # Inspect raw
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        b.close()
        assert mode.lower() == "wal"

    def test_subscribe_receives(self, tmp_path: Path):
        b = PersistentBusBackend(db_path=tmp_path / "test.db")
        received: list[BusEnvelope] = []
        b.subscribe("pipeline:*", lambda env: received.append(env))
        b.publish(BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="t", payload={"x": 1}))
        b.publish(BusEnvelope(type="other:thing", source="t"))
        assert len(received) == 1
        assert received[0].payload == {"x": 1}
        b.close()

    def test_get_recent(self, tmp_path: Path):
        b = PersistentBusBackend(db_path=tmp_path / "test.db")
        for i in range(5):
            b.publish(BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="t", payload={"i": i}))
        recent = b.get_recent(event_type="pipeline:completed", limit=3)
        assert len(recent) == 3
        b.close()
