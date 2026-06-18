"""Proposals API routes."""

import json
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

WORKSPACE_ROOT = Path.home() / "Workspace"
OMO_ROOT = WORKSPACE_ROOT / "projects" / "omo"
import sys

if str(OMO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(OMO_ROOT / "src"))

from omo.omo_cockpit_bridge import (
    append_hitl_override,
    approve_hitl_proposal_async,
    list_hitl_proposals,
    reject_hitl_proposal,
)


@router.get("/api/v1/proposals")
async def api_list_proposals():
    try:
        proposals = list_hitl_proposals(WORKSPACE_ROOT / ".omo")
    except Exception:
        proposals = []
    return JSONResponse({"status": "ok", "proposals": proposals})


async def _execute_mutation(proposal: dict) -> bool:
    import logging

    _log = logging.getLogger("cockpit.hitl")

    p_type = proposal.get("type")
    debt_id = proposal.get("debt_id", "unknown")
    _log.info("[HITL] Executing mutation: %s for %s", p_type, debt_id)

    if p_type == "budget_increase":
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "increase_limit",
            "amount_usd": 0.10,
            "status": "applied",
        }
        append_hitl_override(WORKSPACE_ROOT / ".omo", "budget_overrides.jsonl", record)
        return True
    elif p_type == "model_swap":
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "swap_model",
            "target_model": proposal.get("target_model", "claude-3-haiku"),
            "status": "applied",
        }
        append_hitl_override(WORKSPACE_ROOT / ".omo", "model_overrides.jsonl", record)
        return True
    elif p_type == "quota_reset":
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "reset_quota",
            "scope": proposal.get("scope", "global"),
            "status": "applied",
        }
        append_hitl_override(WORKSPACE_ROOT / ".omo", "quota_resets.jsonl", record)
        return True

    # Plugin Mechanism (BOS URI Hook)
    try:
        from agora.mcp.resolver.api import resolve_bos_uri

        res = await resolve_bos_uri(f"bos://governance/hitl/execute/{p_type}", proposal)
        if res and res.get("status") == "ok":
            return True
    except Exception as e:
        _log.debug("[HITL] Plugin dispatch not found or failed for %s: %s", p_type, e)

    return False


@router.post("/api/v1/proposals/{proposal_id}/approve")
async def api_approve_proposal(proposal_id: str):
    import logging

    _log = logging.getLogger("cockpit.hitl")

    success, error = await approve_hitl_proposal_async(
        WORKSPACE_ROOT / ".omo",
        proposal_id,
        execute_mutation=_execute_mutation,
    )
    if success:
        return JSONResponse({"status": "ok", "message": f"Proposal {proposal_id} approved and executed."})
    if error and "not found" in error:
        return JSONResponse({"status": "error", "error": error}, status_code=404)
    if error and "already being processed" in error:
        return JSONResponse({"status": "error", "error": error}, status_code=409)
    if error and "No execution logic" in error:
        _log.warning("[HITL] %s", error)
        return JSONResponse({"status": "error", "error": error}, status_code=400)
    return JSONResponse({"status": "error", "error": error or "unknown error"}, status_code=500)


@router.post("/api/v1/proposals/{proposal_id}/reject")
async def api_reject_proposal(proposal_id: str):
    reject_hitl_proposal(WORKSPACE_ROOT / ".omo", proposal_id)
    return JSONResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
