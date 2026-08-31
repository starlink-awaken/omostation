"""Authenticated Cockpit proposal and approval routes."""

import hashlib
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cockpit.adapters.agora import resolve_bos_uri
from cockpit.compat import WORKSPACE_ROOT
from cockpit.web.auth import ApiAuthenticationError, ApiAuthorizationError, authenticate_api_principal

router = APIRouter()

try:
    from cockpit.adapters.omo import (
        append_hitl_override,  # pyright: ignore[reportAttributeAccessIssue]
        approve_hitl_proposal_async,  # pyright: ignore[reportAttributeAccessIssue]
        list_hitl_proposals,  # pyright: ignore[reportAttributeAccessIssue]
        record_hitl_proposal,  # pyright: ignore[reportAttributeAccessIssue]
        reject_hitl_proposal,  # pyright: ignore[reportAttributeAccessIssue]
    )

    _OMO_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # Optional adapter; keep proposal routes discoverable.
    append_hitl_override = approve_hitl_proposal_async = list_hitl_proposals = record_hitl_proposal = None  # type: ignore[assignment]
    reject_hitl_proposal = None  # type: ignore[assignment]
    _OMO_IMPORT_ERROR = exc

ROUTER_DEGRADED = _OMO_IMPORT_ERROR is not None
ROUTER_DEGRADED_REASON = str(_OMO_IMPORT_ERROR) if _OMO_IMPORT_ERROR else None
_FAMILY_WRITE_SCOPES = frozenset({"family-documents-write"})


def _principal(request: Request):
    return authenticate_api_principal(dict(request.headers), any_scope=_FAMILY_WRITE_SCOPES)


def _auth_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, ApiAuthenticationError):
        return JSONResponse({"status": "unauthorized", "error": "proposal_auth_required"}, status_code=401)
    return JSONResponse({"status": "forbidden", "error": "proposal_scope_required"}, status_code=403)


def _proposals_unavailable() -> JSONResponse | None:
    if _OMO_IMPORT_ERROR is None:
        return None
    return JSONResponse(
        {
            "status": "degraded",
            "error": "OMO proposal adapter is unavailable",
            "error_type": type(_OMO_IMPORT_ERROR).__name__,
            "detail": str(_OMO_IMPORT_ERROR),
            "next_action": "安装并挂载 OMO 适配器依赖后重试。",
        },
        status_code=503,
    )


@router.get("/api/v1/proposals")
async def api_list_proposals():
    unavailable = _proposals_unavailable()
    if unavailable:
        return unavailable
    try:
        proposals = list_hitl_proposals(WORKSPACE_ROOT / ".omo")  # type: ignore[union-attr]
    except Exception:  # defensive fallback
        proposals = []
    return JSONResponse({"status": "ok", "proposals": proposals})


@router.post("/api/v1/proposals")
async def api_create_proposal(request: Request):
    unavailable = _proposals_unavailable()
    if unavailable:
        return unavailable
    try:
        principal = _principal(request)
    except (ApiAuthenticationError, ApiAuthorizationError) as exc:
        return _auth_error(exc)
    try:
        body = await request.json()
    except (TypeError, ValueError):
        return JSONResponse({"status": "error", "error": "proposal_object_required"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"status": "error", "error": "proposal_object_required"}, status_code=400)
    try:
        proposal = record_hitl_proposal(  # type: ignore[union-attr]
            WORKSPACE_ROOT / ".omo",
            body,
            requested_by=principal.principal_ref,
            now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=409)
    return JSONResponse({"status": "pending", "proposal_id": proposal["id"]}, status_code=202)


async def _execute_mutation(proposal: dict[str, Any]) -> dict[str, Any]:
    p_type = str(proposal.get("type") or "")
    if p_type in {"budget_increase", "model_swap", "quota_reset"}:
        stream = {
            "budget_increase": "budget_overrides.jsonl",
            "model_swap": "model_overrides.jsonl",
            "quota_reset": "quota_resets.jsonl",
        }[p_type]
        record: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "proposal_id": proposal["id"],
            "status": "applied",
        }
        if p_type == "budget_increase":
            record.update({"action": "increase_limit", "amount_usd": 0.10})
        elif p_type == "model_swap":
            record.update({"action": "swap_model", "target_model": proposal.get("target_model", "claude-3-haiku")})
        else:
            record.update({"action": "reset_quota", "scope": proposal.get("scope", "global")})
        ref = append_hitl_override(  # type: ignore[union-attr]
            WORKSPACE_ROOT / ".omo",
            stream,
            record,
        )
        ref_path = Path(ref)
        digest = "sha256:" + hashlib.sha256(ref_path.read_bytes()).hexdigest()
        relative_ref = ref_path.relative_to(WORKSPACE_ROOT / ".omo").as_posix()
        return {"status": "verified", "verify_receipt_ref": relative_ref, "verify_receipt_sha256": digest}
    response = await resolve_bos_uri(f"bos://governance/hitl/execute/{p_type}", proposal=proposal)
    if response.get("status") != "ok" or not isinstance(response.get("result"), dict):
        return {"status": "error", "error": "bos_execution_failed"}
    return dict(response["result"])


@router.post("/api/v1/proposals/{proposal_id}/approve")
async def api_approve_proposal(proposal_id: str, request: Request):
    unavailable = _proposals_unavailable()
    if unavailable:
        return unavailable
    try:
        principal = _principal(request)
    except (ApiAuthenticationError, ApiAuthorizationError) as exc:
        return _auth_error(exc)
    success, error, receipt = await approve_hitl_proposal_async(  # type: ignore[union-attr]
        WORKSPACE_ROOT / ".omo",
        proposal_id,
        principal_ref=principal.principal_ref,
        approved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        execute_mutation=_execute_mutation,
    )
    if success:
        return JSONResponse({"status": "verified", "proposal_id": proposal_id, "receipt": receipt})
    status_code = 404 if error and "not found" in error else (409 if error and "processed" in error else 400)
    return JSONResponse({"status": "error", "error": error or "proposal_execution_failed"}, status_code=status_code)


@router.post("/api/v1/proposals/{proposal_id}/reject")
async def api_reject_proposal(proposal_id: str, request: Request):
    unavailable = _proposals_unavailable()
    if unavailable:
        return unavailable
    try:
        principal = _principal(request)
    except (ApiAuthenticationError, ApiAuthorizationError) as exc:
        return _auth_error(exc)
    try:
        receipt = reject_hitl_proposal(  # type: ignore[union-attr]
            WORKSPACE_ROOT / ".omo",
            proposal_id,
            principal_ref=principal.principal_ref,
            rejected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=409)
    return JSONResponse({"status": "rejected", "proposal_id": proposal_id, "receipt": receipt})


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
