"""Sandbox API routes for Cockpit Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.post("/execute")
async def api_sandbox_execute(request: Request):
    """在隔离沙箱 (KEI Isolation) 中安全执行 python 代码"""
    try:
        from runtime.executor.sandbox import Sandbox

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
    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
