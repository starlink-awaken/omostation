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


@router.get("/api/v1/proposals")
async def api_list_proposals():
    proposal_dir = WORKSPACE_ROOT / ".omo" / "state" / "proposals"
    if not proposal_dir.exists():
        return JSONResponse({"status": "ok", "proposals": []})

    proposals = []
    try:
        import yaml

        for f in proposal_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                proposals.append(data)
        proposals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    except Exception:
        pass
    return JSONResponse({"status": "ok", "proposals": proposals})


async def _execute_mutation(proposal: dict) -> bool:
    import logging

    _log = logging.getLogger("cockpit.hitl")

    p_type = proposal.get("type")
    debt_id = proposal.get("debt_id", "unknown")
    _log.info("[HITL] Executing mutation: %s for %s", p_type, debt_id)

    if p_type == "budget_increase":
        config_patch = WORKSPACE_ROOT / ".omo" / "state" / "budget_overrides.jsonl"
        config_patch.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "increase_limit",
            "amount_usd": 0.10,
            "status": "applied",
        }
        with open(config_patch, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    elif p_type == "model_swap":
        config_patch = WORKSPACE_ROOT / ".omo" / "state" / "model_overrides.jsonl"
        config_patch.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "swap_model",
            "target_model": proposal.get("target_model", "claude-3-haiku"),
            "status": "applied",
        }
        with open(config_patch, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    elif p_type == "quota_reset":
        config_patch = WORKSPACE_ROOT / ".omo" / "state" / "quota_resets.jsonl"
        config_patch.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "debt_id": debt_id,
            "action": "reset_quota",
            "scope": proposal.get("scope", "global"),
            "status": "applied",
        }
        with open(config_patch, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
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

    proposal_dir = WORKSPACE_ROOT / ".omo" / "state" / "proposals"
    proposal_path = proposal_dir / f"{proposal_id}.yaml"
    processing_path = proposal_dir / f"{proposal_id}.processing"

    if not proposal_path.exists() and not processing_path.exists():
        return JSONResponse({"status": "error", "error": f"Proposal {proposal_id} not found"}, status_code=404)

    try:
        if proposal_path.exists():
            proposal_path.rename(processing_path)
    except OSError:
        return JSONResponse(
            {"status": "error", "error": f"Proposal {proposal_id} is already being processed."}, status_code=409
        )

    try:
        import yaml

        proposal = yaml.safe_load(processing_path.read_text())
        success = await _execute_mutation(proposal)

        if not success:
            _log.warning("[HITL] No execution logic for type: %s", proposal.get("type"))
            # Rollback rename
            processing_path.rename(proposal_path)
            return JSONResponse(
                {"status": "error", "error": f"No execution logic for type {proposal.get('type')}"}, status_code=400
            )

        processing_path.unlink()
        return JSONResponse({"status": "ok", "message": f"Proposal {proposal_id} approved and executed."})
    except Exception as e:
        if processing_path.exists():
            processing_path.rename(proposal_path)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/v1/proposals/{proposal_id}/reject")
async def api_reject_proposal(proposal_id: str):
    proposal_dir = WORKSPACE_ROOT / ".omo" / "state" / "proposals"
    proposal_path = proposal_dir / f"{proposal_id}.yaml"
    if proposal_path.exists():
        proposal_path.unlink()
    return JSONResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
