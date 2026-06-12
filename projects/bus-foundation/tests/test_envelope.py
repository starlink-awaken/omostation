"""Test BusEnvelope — first 3 of 12 cases."""
from __future__ import annotations

from bus_foundation.envelope import BusEnvelope, EventType


class TestBusEnvelopeConstruction:
    def test_minimal_envelope(self) -> None:
        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        assert env.type == "pipeline:completed"
        assert env.source == "test"
        assert isinstance(env.id, str) and len(env.id) > 0
        assert env.schema_version == 1
        assert env.payload == {}
        assert env.trace_id is None

    def test_full_envelope(self) -> None:
        env = BusEnvelope(
            type=EventType.MESSAGE_RECEIVED,
            source="bus-foundation",
            payload={"key": "value"},
            trace_id="trace-123",
            schema_version=1,
        )
        assert env.payload == {"key": "value"}
        assert env.trace_id == "trace-123"

    def test_serialization_roundtrip(self) -> None:
        original = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="svc",
            payload={"x": 1},
        )
        json_str = original.to_json()
        restored = BusEnvelope.from_json(json_str)
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.id == original.id


class TestBusEnvelopeValidation:
    def test_empty_type_raises(self) -> None:
        try:
            BusEnvelope(type="", source="test")
        except ValueError:
            return
        raise AssertionError("expected ValueError for empty type")

    def test_empty_source_raises(self) -> None:
        try:
            BusEnvelope(type="x:y", source="")
        except ValueError:
            return
        raise AssertionError("expected ValueError for empty source")

    def test_eventtype_passthrough(self) -> None:
        env = BusEnvelope(type=EventType.PIPELINE_STARTED, source="test")
        assert env.type == "pipeline:started"
