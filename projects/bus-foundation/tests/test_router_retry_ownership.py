"""Test RETRY-OWNERSHIP rule — bus layer must NOT retry on failure."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from bus_foundation.backends.base import BusBackend
from bus_foundation.dlq import DLQ
from bus_foundation.envelope import BusEnvelope, EventType
from bus_foundation.router import Router


class TestRouterRetryOwnership:
    def test_publish_failure_goes_to_dlq_no_retry(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.publish.side_effect = ConnectionError("simulated")

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        result = router.publish(env)

        assert mock_backend.publish.call_count == 1
        assert result == env.id
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["event_id"] == env.id
        assert "simulated" in rows[0]["error"]
        dlq.close()

    def test_publish_unavailable_backend_goes_to_dlq(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = False
        mock_backend.publish.return_value = "should-not-be-called"

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        router.publish(env)

        mock_backend.is_available.assert_called_once()
        mock_backend.publish.assert_not_called()
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["error"] == "backend unavailable"
        dlq.close()

    def test_publish_success_no_dlq(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.publish.return_value = "evt-from-backend"

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        result = router.publish(env)

        assert result == "evt-from-backend"
        assert dlq.list_all() == []
        dlq.close()
