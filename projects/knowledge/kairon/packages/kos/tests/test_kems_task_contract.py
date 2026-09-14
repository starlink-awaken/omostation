"""Tests for evidence-bound OMO task drafts."""

import pytest
from kos.kems import TaskDraft


def task(**overrides):
    values = {
        "task_id": "task-1",
        "source_run_id": "run-1",
        "title": "补齐台账",
        "owner": "单位 B",
        "due_at": "2026-08-15",
        "acceptance_criteria": "提交已审核台账",
        "evidence_refs": ("ev-1",),
    }
    values.update(overrides)
    return TaskDraft(**values)


def test_task_draft_requires_evidence_and_emits_idempotent_omo_payload():
    draft = task()
    assert draft.idempotency_key == "run-1:task-1"
    assert draft.to_omo_payload()["approval_required"] is True
    assert draft.approve("reviewer").status == "approved"

    with pytest.raises(ValueError, match="evidence"):
        task(evidence_refs=())


def test_only_drafts_can_be_approved():
    with pytest.raises(ValueError, match="reviewer"):
        task().approve("")
    with pytest.raises(ValueError, match="only draft"):
        task(status="approved").approve("reviewer")
