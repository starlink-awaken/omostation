"""Tests for the KEMS to OMO planned-task boundary."""

import pytest
from kos.kems import OmoTaskAdapter, TaskDraft


def draft(**overrides):
    values = {
        "task_id": "task-1",
        "source_run_id": "run-1",
        "title": "补齐台账",
        "owner": "单位 B",
        "due_at": "2026-08-15",
        "acceptance_criteria": "提交已审核台账",
        "evidence_refs": ("doc-1#page=2",),
        "graph_refs": ("ent-1",),
        "risk_level": "high",
    }
    values.update(overrides)
    return TaskDraft(**values)


def test_adapter_creates_reviewable_omo_planned_payload():
    payload = OmoTaskAdapter.build(draft())
    assert payload["status"] == "candidate"
    assert payload["assigned_to"] is None
    assert payload["human_approval_required"] is True
    assert payload["source_docs"] == ["doc-1#page=2"]
    assert payload["metadata"]["idempotency_key"] == "run-1:task-1"
    assert OmoTaskAdapter.validate_planned_payload(payload) == []


def test_adapter_rejects_missing_evidence_and_worker_assignment():
    payload = OmoTaskAdapter.to_planned_payload(draft())
    payload["source_docs"] = []
    payload["assigned_to"] = "worker-a"
    errors = OmoTaskAdapter.validate_planned_payload(payload)
    assert "planned KEMS payload must not assign a worker" in errors
    assert "KEMS payload requires evidence-bound source_docs" in errors
    with pytest.raises(ValueError, match="evidence"):
        OmoTaskAdapter.build(draft(evidence_refs=()))
