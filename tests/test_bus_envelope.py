"""Test BusEnvelope — first 3 of 12 cases (TDD red)."""

from agora.bus.envelope import BusEnvelope, EventType


class TestBusEnvelopeConstruction:
    def test_minimal_envelope(self):
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
        )
        assert env.type == "pipeline:completed"
        assert env.source == "test"
        assert isinstance(env.id, str) and len(env.id) > 0
        assert env.schema_version == 1
        assert env.payload == {}
        assert env.trace_id is None

    def test_full_envelope(self):
        env = BusEnvelope(
            type=EventType.MESSAGE_RECEIVED,
            source="agora",
            payload={"key": "value"},
            trace_id="trace-123",
        )
        assert env.payload == {"key": "value"}
        assert env.trace_id == "trace-123"

    def test_serialization_roundtrip(self):
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
