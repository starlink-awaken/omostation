"""Reflection API — 聚合运行时反射数据给 cockpit-ui.

提供:
  GET /api/resident   — 常驻 Agent 状态
  GET /api/bcos       — BCOS 北极星/信号/进化
  GET /api/p74        — P74 工作流沉默治理
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reflection"])

_TIMEOUT = 30


def _run_json(cmd: list[str], timeout: int = _TIMEOUT) -> dict[str, Any]:
    """运行命令并解析 JSON 输出, 失败返回 {available:false}."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {"available": False, "error": f"exit={result.returncode}", "stderr": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "timeout"}
    except json.JSONDecodeError as exc:
        return {"available": False, "error": f"json_decode: {exc}"}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@router.get("/resident")
async def resident_status() -> JSONResponse:
    """常驻 Agent 状态."""
    data = _run_json(["uv", "run", "python", "bin/omo", "resident", "status", "--json"])
    return JSONResponse(data)


@router.get("/bcos")
async def bcos_status() -> JSONResponse:
    """BCOS 北极星/信号/进化."""
    data = _run_json(["uv", "run", "python", "bin/bc-os/north_star_meter_v2.py", "--json"])
    return JSONResponse(data)


@router.get("/p74")
async def p74_status() -> JSONResponse:
    """P74 工作流沉默治理."""
    data = _run_json(["uv", "run", "python", "bin/agent-workflow.py", "compliance", "--json"])
    return JSONResponse(data)
