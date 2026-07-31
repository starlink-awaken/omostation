"""KEMS workbench API: read-only status and evidence-bound OMO task drafts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from cockpit.web.api_tasks_data import WORKSPACE_DIR

router = APIRouter()

_RISK_TO_LEVEL = {"low": "L0", "medium": "L1", "high": "L2"}


@router.get("/api/kems/status")
async def kems_status() -> dict[str, Any]:
    """Expose capabilities without reading or returning private source content."""
    return {
        "status": "ready",
        "mode": "review_only",
        "capabilities": ["ocr_review", "graph_review", "evaluation", "omo_task_draft"],
        "dispatch": "omo_only",
    }


@router.post("/api/kems/tasks/draft")
async def create_kems_task_draft(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="KEMS task draft must be an object")

    required = ("task_id", "source_run_id", "title", "owner", "due_at", "evidence_refs", "acceptance_criteria")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing KEMS fields: {', '.join(missing)}")
    evidence_refs = body["evidence_refs"]
    if not isinstance(evidence_refs, list) or not all(isinstance(item, str) and item.strip() for item in evidence_refs):
        raise HTTPException(status_code=422, detail="evidence_refs must be a non-empty string list")

    risk = str(body.get("risk_level") or "medium")
    if risk not in _RISK_TO_LEVEL:
        raise HTTPException(status_code=422, detail="risk_level must be low, medium, or high")
    task_id = str(body["task_id"])
    source_run_id = str(body["source_run_id"])
    payload = {
        "id": task_id,
        "title": str(body["title"]),
        "description": str(body["acceptance_criteria"]),
        "status": "candidate",
        "task_type": "kems_evidence_action",
        "risk_level": _RISK_TO_LEVEL[risk],
        "allowed_operation_level": _RISK_TO_LEVEL[risk],
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": list(body.get("graph_refs") or []),
        "handoff_refs": [],
        "source_docs": evidence_refs,
        "entry_gate": ["evidence_bound", "human_review_required"],
        "evidence_required": evidence_refs,
        "test_plan": [str(body["acceptance_criteria"])],
        "deliverables": [str(body["acceptance_criteria"])],
        "human_approval_required": risk != "low",
        "depends_on": [],
        "context_uri": f"bos://kems/task/{task_id}",
        "metadata": {
            "source_run_id": source_run_id,
            "proposed_owner": str(body["owner"]),
            "due_at": str(body["due_at"]),
            "priority": str(body.get("priority") or "P2"),
            "created_via": "cockpit.kems",
        },
    }
    try:
        from omo.omo_ingress_kems import create_kems_planned_task

        created = create_kems_planned_task(
            WORKSPACE_DIR / ".omo",
            task_payload=payload,
            source_ref=f"kems:{source_run_id}:{task_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO KEMS ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": task_id,
        "status": created.get("status", "candidate"),
        "created": True,
        "review_required": True,
        "source": "omo_kems_ingress",
        "evidence_count": len(evidence_refs),
    }
