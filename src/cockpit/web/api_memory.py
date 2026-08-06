"""Memory OS HTTP surface — L3 thin gateway to mos CLI (ADR-0372 Phase 5–8).

Does not import gbrain/kairon internals; invokes `python -m mos` via uv for
layer compliance. Unit tests inject `invoke_mos`.

Phase 6: RBAC via X-Mos-Role / X-Agent-Profile headers + body fields.
Phase 8: load NEO4J_*/MOS_* env (memory_env) and uv --with neo4j when configured.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT
from cockpit.web.memory_env import apply_memory_os_env, mos_subprocess_env, mos_uv_extra_args

logger = logging.getLogger("cockpit.web.api_memory")
router = APIRouter(prefix="/api/memory", tags=["memory-os"])

InvokeFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def _default_invoke(cmd: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Call mos via Agora-compatible stdin JSON protocol."""
    apply_memory_os_env()
    kairon = Path(WORKSPACE_ROOT) / "projects" / "kairon"
    proc_cmd = [
        "uv",
        "run",
        "--directory",
        str(kairon),
        "--package",
        "mos",
        *mos_uv_extra_args(),
        "python",
        "-m",
        "mos",
        cmd,
    ]
    payload = json.dumps({"args": [], "kwargs": kwargs}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            proc_cmd,
            input=payload,
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("MOS_HTTP_TIMEOUT", "60")),
            check=False,
            env=mos_subprocess_env(),
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"uv/mos unavailable: {exc}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    if not proc.stdout.strip():
        return {
            "ok": False,
            "error": proc.stderr.strip() or f"empty stdout rc={proc.returncode}",
            "returncode": proc.returncode,
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid json", "raw": proc.stdout[-500:]}


# Patchable for tests
invoke_mos: InvokeFn = _default_invoke


def _body(request_json: dict[str, Any] | None) -> dict[str, Any]:
    return dict(request_json or {})


def _inject_rbac(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Merge RBAC identity from headers into kwargs body (headers win if body empty)."""
    role = request.headers.get("x-mos-role") or request.headers.get("X-Mos-Role")
    profile = request.headers.get("x-agent-profile") or request.headers.get("X-Agent-Profile")
    principal = request.headers.get("x-principal-id") or request.headers.get("X-Principal-Id")
    if role and not body.get("role"):
        body["role"] = role
    if profile and not body.get("agent_profile"):
        body["agent_profile"] = profile
    if principal and not body.get("principal_id"):
        body["principal_id"] = principal
    return body


def _status_code(result: dict[str, Any]) -> int:
    if result.get("error") == "rbac_denied":
        return 403
    if result.get("ok") is False:
        return 400
    return 200


@router.get("/status")
async def memory_status(request: Request) -> JSONResponse:
    body = _inject_rbac({}, request)
    result = invoke_mos("status", body)
    return JSONResponse(result, status_code=_status_code(result))


@router.post("/write")
async def memory_write(request: Request) -> JSONResponse:
    body = _inject_rbac(_body(await request.json()), request)
    result = invoke_mos("write", body)
    return JSONResponse(result, status_code=_status_code(result))


@router.post("/recall")
async def memory_recall(request: Request) -> JSONResponse:
    body = _inject_rbac(_body(await request.json()), request)
    # Allow flat principal fields → scope
    if "scope" not in body and any(k in body for k in ("principal_id", "agent_profile", "scene_id")):
        body["scope"] = {k: body[k] for k in ("principal_id", "agent_profile", "scene_id") if body.get(k)}
    result = invoke_mos("recall", body)
    return JSONResponse(result, status_code=_status_code(result))


@router.post("/forget")
async def memory_forget(request: Request) -> JSONResponse:
    body = _inject_rbac(_body(await request.json()), request)
    result = invoke_mos("forget", body)
    return JSONResponse(result, status_code=_status_code(result))


@router.post("/knowledge-ref")
async def memory_knowledge_ref(request: Request) -> JSONResponse:
    body = _inject_rbac(_body(await request.json()), request)
    result = invoke_mos("knowledge-ref", body)
    return JSONResponse(result, status_code=_status_code(result))


@router.post("/consolidate")
async def memory_consolidate(request: Request) -> JSONResponse:
    body: dict[str, Any] = {}
    try:
        raw = await request.body()
        if raw:
            body = _body(json.loads(raw.decode("utf-8")))
    except Exception:
        body = {}
    body = _inject_rbac(body, request)
    if "dry_run" not in body:
        body["dry_run"] = True
    if not body.get("role") and not body.get("agent_profile"):
        body["agent_profile"] = "governance-agent"
    result = invoke_mos("consolidate", body)
    return JSONResponse(result, status_code=_status_code(result))
