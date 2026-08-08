"""Test RETRY-OWNERSHIP rule — bus layer must NOT retry on failure."""

from unittest.mock import MagicMock

from agora.bus.backends.base import BusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope, EventType
from agora.bus.router import Router


class TestRouterRetryOwnership:
    def test_publish_failure_goes_to_dlq_no_retry(self, tmp_path):
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

    def test_publish_unavailable_backend_goes_to_dlq(self, tmp_path):
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

    def test_publish_success_no_dlq(self, tmp_path):
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
