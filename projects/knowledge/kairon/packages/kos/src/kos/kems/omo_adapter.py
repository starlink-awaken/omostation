"""Translate KEMS task drafts into OMO planned-task envelopes.

The adapter only creates a reviewable planned payload.  OMO remains the state
authority and must perform approval, promotion, dispatch, and execution.
"""

from __future__ import annotations

from typing import Any

from .task_contract import TaskDraft

_RISK_TO_LEVEL = {"low": "L0", "medium": "L1", "high": "L2"}
_REQUIRED_FIELDS = {
    "id",
    "title",
    "status",
    "assigned_to",
    "dispatch_id",
    "run_ref",
    "approval_ref",
    "review_ref",
    "knowledge_refs",
    "handoff_refs",
    "risk_level",
    "allowed_operation_level",
    "human_approval_required",
    "source_docs",
    "entry_gate",
    "evidence_required",
    "test_plan",
}


class OmoTaskAdapter:
    """Build and validate a planned OMO task without mutating OMO state."""

    @staticmethod
    def to_planned_payload(draft: TaskDraft) -> dict[str, Any]:
        level = _RISK_TO_LEVEL[draft.risk_level]
        evidence = list(draft.evidence_refs)
        payload: dict[str, Any] = {
            "id": draft.task_id,
            "title": draft.title,
            "description": draft.acceptance_criteria,
            "status": "candidate",
            "task_type": "kems_evidence_action",
            "risk_level": level,
            "allowed_operation_level": level,
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": list(draft.graph_refs),
            "handoff_refs": [],
            "source_docs": evidence,
            "entry_gate": ["evidence_bound", "human_review_required"],
            "evidence_required": evidence,
            "test_plan": [draft.acceptance_criteria],
            "deliverables": [draft.acceptance_criteria],
            "human_approval_required": draft.risk_level != "low",
            "depends_on": [],
            "context_uri": f"bos://kems/task/{draft.task_id}",
            "metadata": {
                "source_run_id": draft.source_run_id,
                "proposed_owner": draft.owner,
                "due_at": draft.due_at,
                "priority": draft.priority,
                "idempotency_key": draft.idempotency_key,
                "created_via": "kems_omo_adapter",
            },
        }
        return payload

    @staticmethod
    def validate_planned_payload(payload: dict[str, Any]) -> list[str]:
        missing = sorted(_REQUIRED_FIELDS - payload.keys())
        errors = [f"missing required OMO field: {field}" for field in missing]
        if payload.get("status") not in {"candidate", "pending"}:
            errors.append("KEMS payload must enter OMO as candidate or pending")
        if payload.get("assigned_to") is not None:
            errors.append("planned KEMS payload must not assign a worker")
        if not payload.get("source_docs") or not payload.get("evidence_required"):
            errors.append("KEMS payload requires evidence-bound source_docs")
        return errors

    @classmethod
    def build(cls, draft: TaskDraft) -> dict[str, Any]:
        payload = cls.to_planned_payload(draft)
        errors = cls.validate_planned_payload(payload)
        if errors:
            raise ValueError("; ".join(errors))
        return payload
