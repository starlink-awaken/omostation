import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agora.core.event_bus import GOVERNANCE_EVENTS, EventBus


def test_governance_events_defined():
    assert "constraint.changed" in GOVERNANCE_EVENTS
    assert "derived.regenerated" in GOVERNANCE_EVENTS
    assert "m0.drift_detected" in GOVERNANCE_EVENTS
    assert "approval.decided" in GOVERNANCE_EVENTS
    assert len(GOVERNANCE_EVENTS) == 4


def test_publish_governance_event():
    bus = EventBus(storage_path="/tmp/agora-events-test.jsonl")
    bus.subscribe(service="ecos", pattern="governance.*", callback_url="http://localhost:1/hook")
    event_id = bus.publish(event_type="governance.constraint.changed", payload={"id": "X1-C04"})
    assert event_id.startswith("evt_") or len(event_id) > 0
