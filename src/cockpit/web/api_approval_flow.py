"""HITL 审批流 + 证据面板 API 端点.

The HITL (Human-In-The-Loop) approval flow manages the lifecycle from
a pending intent through human review to approval/rejection with full
evidence tracking.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from fastapi import APIRouter

from cockpit.compat import WORKSPACE_ROOT

_REPO_ROOT = WORKSPACE_ROOT

_ENGINE_PATH = _REPO_ROOT / "bin" / "ssot" / "scene-card-approval-flow.py"


def _load_engine():
    spec = importlib.util.spec_from_file_location("scene_card_approval_flow", _ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-approval-flow.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _engine = _load_engine()
    _engine_available = True
    _engine_error: str | None = None
except Exception as exc:
    _engine = None
    _engine_available = False
    _engine_error = str(exc)


router = APIRouter(prefix="/api/decision-inbox/approvals", tags=["decision-inbox-approvals"])


def _unavailable() -> dict[str, Any]:
    return {"ok": False, "status": "unavailable", "error": _engine_error or "engine unavailable"}


@router.get("/queue")
async def get_review_queue() -> dict[str, Any]:
    """Get all intents pending review."""
    if not _engine_available:
        return _unavailable()
    try:
        queue = _engine.get_review_queue(_REPO_ROOT)
        return {"ok": True, "queue": queue, "total": len(queue)}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/evidence/{intent_id}")
async def get_evidence(intent_id: str) -> dict[str, Any]:
    """Get full evidence detail for a specific intent."""
    if not _engine_available:
        return _unavailable()
    try:
        detail = _engine.get_evidence_detail(_REPO_ROOT, intent_id)
        if detail is None:
            return {"ok": False, "status": "not_found", "error": f"Intent {intent_id} not found"}
        return {"ok": True, "detail": detail}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/approve")
async def approve_intent(body: dict) -> dict[str, Any]:
    """Approve an intent and create task binding."""
    if not _engine_available:
        return _unavailable()
    try:
        intent_id = body.get("intent_id", "")
        if not intent_id:
            return {"ok": False, "status": "invalid", "error": "intent_id is required"}
        result = _engine.approve_intent(
            _REPO_ROOT,
            intent_id=intent_id,
            reviewer=body.get("reviewer", "human"),
            note=body.get("note", ""),
            outcome_metric=body.get("outcome_metric", ""),
        )
        return result
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.post("/reject")
async def reject_intent(body: dict) -> dict[str, Any]:
    """Reject an intent."""
    if not _engine_available:
        return _unavailable()
    try:
        intent_id = body.get("intent_id", "")
        if not intent_id:
            return {"ok": False, "status": "invalid", "error": "intent_id is required"}
        result = _engine.reject_intent(
            _REPO_ROOT,
            intent_id=intent_id,
            reviewer=body.get("reviewer", "human"),
            note=body.get("note", ""),
        )
        return result
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/history")
async def get_approval_history(limit: int = 20) -> dict[str, Any]:
    """Get recent approval/rejection history."""
    if not _engine_available:
        return _unavailable()
    try:
        history = _engine.get_approval_history(_REPO_ROOT, limit=limit)
        return {"ok": True, "history": history, "total": len(history)}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/stats")
async def get_approval_stats() -> dict[str, Any]:
    """Get approval statistics."""
    if not _engine_available:
        return _unavailable()
    try:
        stats = _engine.get_approval_stats(_REPO_ROOT)
        return {"ok": True, "stats": stats}
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@router.get("/receipts")
async def list_receipts() -> dict[str, Any]:
    """List all approval receipts."""
    if not _engine_available:
        return _unavailable()
    try:
        receipts = _engine.list_receipts(_REPO_ROOT)
        return {
            "ok": True,
            "receipts": [
                {
                    "receipt_id": r.receipt_id,
                    "intent_id": r.intent_id,
                    "decision": r.decision,
                    "reviewer": r.reviewer,
                    "note": r.note,
                    "created_at": r.created_at,
                }
                for r in reversed(receipts)
            ],
        }
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        return {"ok": False, "status": "error", "error": str(exc)}
