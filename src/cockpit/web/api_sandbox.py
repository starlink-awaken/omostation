"""Sandbox API routes for Cockpit Dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

_REPO_ROOT = Path(__file__).resolve().parents[5]

# Ensure runtime src is in sys.path
_RUNTIME_SRC = _REPO_ROOT / "projects" / "runtime" / "src"
if str(_RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_SRC))

from runtime.executor.sandbox import Sandbox


@router.post("/execute")
async def api_sandbox_execute(request: Request):
    """在隔离沙箱 (KEI Isolation) 中安全执行 python 代码"""
    try:
        body = await request.json()
        code = body.get("code")
        if not code:
            return JSONResponse({"status": "error", "error": "code is required"}, status_code=400)

        # Execute code in restricted KEI sandbox
        res = Sandbox.execute(code)

        return JSONResponse(
            {
                "success": res.success,
                "duration_ms": res.duration_ms,
                "stdout": res.stdout,
                "output": res.output,
                "error": res.error,
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
