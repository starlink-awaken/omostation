"""Memory OS HTTP surface — L3 thin gateway to mos CLI (ADR-0372 Phase 5).

Does not import gbrain/kairon internals; invokes `python -m mos` via uv for
layer compliance. Unit tests inject `invoke_mos`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT

logger = logging.getLogger("cockpit.web.api_memory")
router = APIRouter(prefix="/api/memory", tags=["memory-os"])

InvokeFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def _default_invoke(cmd: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Call mos via Agora-compatible stdin JSON protocol."""
    kairon = Path(WORKSPACE_ROOT) / "projects" / "kairon"
    proc_cmd = [
        "uv",
        "run",
        "--directory",
        str(kairon),
        "--package",
        "mos",
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
            env={**os.environ, "MOS_STDIO": "1"},
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


@router.get("/status")
async def memory_status() -> JSONResponse:
    result = invoke_mos("status", {})
    return JSONResponse(result)


@router.post("/write")
async def memory_write(request: Request) -> JSONResponse:
    body = _body(await request.json())
    result = invoke_mos("write", body)
    code = 200 if result.get("ok", True) else 400
    return JSONResponse(result, status_code=code)


@router.post("/recall")
async def memory_recall(request: Request) -> JSONResponse:
    body = _body(await request.json())
    # Allow flat principal fields → scope
    if "scope" not in body and any(k in body for k in ("principal_id", "agent_profile", "scene_id")):
        body["scope"] = {
            k: body[k] for k in ("principal_id", "agent_profile", "scene_id") if body.get(k)
        }
    result = invoke_mos("recall", body)
    return JSONResponse(result)


@router.post("/forget")
async def memory_forget(request: Request) -> JSONResponse:
    body = _body(await request.json())
    result = invoke_mos("forget", body)
    code = 200 if result.get("ok", True) else 400
    return JSONResponse(result, status_code=code)


@router.post("/knowledge-ref")
async def memory_knowledge_ref(request: Request) -> JSONResponse:
    body = _body(await request.json())
    result = invoke_mos("knowledge-ref", body)
    return JSONResponse(result)


@router.post("/consolidate")
async def memory_consolidate(request: Request) -> JSONResponse:
    body: dict[str, Any] = {}
    try:
        raw = await request.body()
        if raw:
            body = _body(json.loads(raw.decode("utf-8")))
    except Exception:  # noqa: BLE001
        body = {}
    if "dry_run" not in body:
        body["dry_run"] = True
    result = invoke_mos("consolidate", body)
    return JSONResponse(result)
