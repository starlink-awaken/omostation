"""Test R75-LOW-1: rate-limited subscriber cleanup."""
from pathlib import Path

from bus_foundation.backends.persistent_bus import (
    CLEANUP_EVERY_N_PUBLISHES,
    PersistentBusBackend,
)
from bus_foundation.envelope import BusEnvelope


class TestR75Low1RateLimitedCleanup:
    def test_publish_count_increments(self, tmp_path: Path):
        b = PersistentBusBackend(db_path=tmp_path / "t.db")
        assert b._publish_count == 0
        for _ in range(3):
            b.publish(BusEnvelope(type="x:y", source="t"))
        assert b._publish_count == 3
        b.close()

    def test_cleanup_trigger_at_n_boundary(self, tmp_path: Path):
        """The (publish_count % CLEANUP_EVERY_N_PUBLISHES == 0) check
        is the gate. We test it by patching _cleanup_subs_locked to
        record call count, then publishing N times and confirming
        the gate was hit exactly once.
        """
        b = PersistentBusBackend(db_path=tmp_path / "t.db")
        # Patch the locked cleanup
        original = b._cleanup_subs_locked
        call_count = [0]
        def counting():
            call_count[0] += 1
            original()
        b._cleanup_subs_locked = counting  # type: ignore[assignment]

        # Publish CLEANUP_EVERY_N_PUBLISHES times — gate should fire once
        for i in range(CLEANUP_EVERY_N_PUBLISHES):
            b.publish(BusEnvelope(type=f"x:{i}", source="t"))
        assert call_count[0] == 1
        b.close()

    def test_cleanup_does_not_fire_under_threshold(self, tmp_path: Path):
        """Below N publishes, no cleanup runs."""
        b = PersistentBusBackend(db_path=tmp_path / "t.db")
        call_count = [0]
        original = b._cleanup_subs_locked
        def counting():
            call_count[0] += 1
            original()
        b._cleanup_subs_locked = counting  # type: ignore[assignment]

        # Publish fewer than CLEANUP_EVERY_N_PUBLISHES — no gate fire
        for i in range(CLEANUP_EVERY_N_PUBLISHES - 1):
            b.publish(BusEnvelope(type=f"x:{i}", source="t"))
        assert call_count[0] == 0
        b.close()
