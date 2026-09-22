#!/usr/bin/env python3
"""Quick verification of _record_fallback_receipt state handling.

Runs the importer's fallback logic against each possible snapshot state and
asserts that the resulting event sequence ends with WorkflowSucceeded followed
by EvidenceRecorded.
"""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def load_importer():
    path = Path(__file__).resolve().parent.parent / "engineering-delivery-candidate-importer.py"
    spec = importlib.util.spec_from_file_location("importer", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    sys.path.insert(0, str(path.resolve().parents[2] / "projects" / "omo" / "src"))
    spec.loader.exec_module(mod)
    return mod


mod = load_importer()
SCENE_BINDING = mod.SCENE_BINDING
_record_fallback_receipt = mod._record_fallback_receipt


class FakeStore:
    def __init__(self) -> None:
        self.events = []

    def snapshot(self, run_id: str) -> dict:
        return getattr(self, "_snapshot", {"state": "unknown"})

    def append(self, event) -> None:
        self.events.append(event)


def make_pr() -> dict:
    return {
        "number": 1,
        "title": "test",
        "created_at": "2026-08-20T10:00:00Z",
        "merged_at": "2026-08-20T10:05:00Z",
        "html_url": "https://example.com/pr/1",
    }


def event_types(events):
    return [e["event_type"] for e in events]


def assert_sequence(events, expected):
    actual = event_types(events)
    assert actual == expected, f"expected {expected}, got {actual}"


def test_unknown_state():
    store = FakeStore()
    store._snapshot = {"state": "unknown"}
    _record_fallback_receipt(store, "run-1", make_pr(), "repo")
    assert_sequence(
        store.events,
        [
            "WorkflowRequested",
            "WorkflowAdmitted",
            "StepDispatched",
            "StepStarted",
            "WorkflowSucceeded",
            "EvidenceRecorded",
        ],
    )


def test_planned_state():
    store = FakeStore()
    store._snapshot = {"state": "planned"}
    _record_fallback_receipt(store, "run-2", make_pr(), "repo")
    assert_sequence(
        store.events,
        [
            "WorkflowAdmitted",
            "StepDispatched",
            "StepStarted",
            "WorkflowSucceeded",
            "EvidenceRecorded",
        ],
    )


def test_admitted_state():
    store = FakeStore()
    store._snapshot = {"state": "admitted"}
    _record_fallback_receipt(store, "run-3", make_pr(), "repo")
    assert_sequence(
        store.events,
        [
            "StepDispatched",
            "StepStarted",
            "WorkflowSucceeded",
            "EvidenceRecorded",
        ],
    )


def test_dispatched_state():
    store = FakeStore()
    store._snapshot = {"state": "dispatched"}
    _record_fallback_receipt(store, "run-4", make_pr(), "repo")
    assert_sequence(
        store.events,
        [
            "StepDispatched",
            "StepStarted",
            "WorkflowSucceeded",
            "EvidenceRecorded",
        ],
    )


def test_succeeded_state():
    store = FakeStore()
    store._snapshot = {"state": "succeeded"}
    _record_fallback_receipt(store, "run-5", make_pr(), "repo")
    assert_sequence(store.events, ["EvidenceRecorded"])


def test_evidence_payload_has_required_fields():
    store = FakeStore()
    store._snapshot = {"state": "unknown"}
    _record_fallback_receipt(store, "run-6", make_pr(), "repo")
    evidence = next(e for e in store.events if e["event_type"] == "EvidenceRecorded")
    payload = evidence["payload"]
    assert payload["evidence_id"] == "external:engineering-delivery:pr-1"
    assert payload["kind"] == "engineering-delivery-receipt"
    assert payload["resource_id"] == "engineering-delivery"
    assert payload["step_run_id"] == "run-6:execute"


if __name__ == "__main__":
    test_unknown_state()
    test_planned_state()
    test_admitted_state()
    test_dispatched_state()
    test_succeeded_state()
    test_evidence_payload_has_required_fields()
    print("all fallback state tests passed")
