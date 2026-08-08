"""Test BusEnvelope strict validation (R64)."""

import pytest

from agora.bus.envelope import BusEnvelope, EventType


class TestEnvelopeStrictValidation:
    def test_empty_type_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            BusEnvelope(type="", source="x")

    def test_none_type_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            BusEnvelope(type=None, source="x")  # type: ignore

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            BusEnvelope(type="x:y", source="")

    def test_none_source_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            BusEnvelope(type="x:y", source=None)  # type: ignore

    def test_valid_envelope_passes(self):
        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="svc-1")
        assert env.type == "pipeline:completed"
        assert env.source == "svc-1"

    def test_custom_string_type_passes(self):
        # Custom types are allowed as plain strings (R59 envelope docstring)
        env = BusEnvelope(type="my_app:custom_event", source="svc-2")
        assert env.type == "my_app:custom_event"
