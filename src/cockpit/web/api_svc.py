"""Workspace 服务控制面 API — 统一视图 + 场景启停。

数据源:bin/svc/service_view.py(join 四张 SSOT + 实时探活),不落库、不失真。

Routes:
    GET  /api/svc/overview          全服务统一视图(launchd/docker + 端口一致性)
    GET  /api/svc/ports             端口体检(未登记/僵尸/冲突)
    POST /api/svc/action            起停单个服务
    POST /api/svc/profile           按场景批量起停(minimal/dev/data)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_ENGINE = None


def _engine():
    """惰性加载 bin/svc/service_view.py(它不在包内,按路径导入)。"""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    cur = Path(__file__).resolve()
    root = None
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            root = parent
            break
    if root is None:
        raise HTTPException(status_code=500, detail="定位不到 workspace 根目录")
    mod_path = root / "bin" / "svc" / "service_view.py"
    if not mod_path.is_file():
        raise HTTPException(status_code=500, detail=f"缺少引擎: {mod_path}")
    spec = importlib.util.spec_from_file_location("service_view", mod_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail="加载 service_view 失败")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["service_view"] = mod
    spec.loader.exec_module(mod)
    _ENGINE = mod
    return mod


class ActionRequest(BaseModel):
    id: str
    action: str  # up | down


class ProfileRequest(BaseModel):
    profile: str  # minimal | dev | data
    action: str   # up | down


@router.get("/api/svc/overview")
async def svc_overview() -> dict[str, Any]:
    """全服务统一视图:19 LaunchAgent + Docker 容器 + BOS 能力数 + 端口一致性。"""
    try:
        return {"status": "success", **_engine().collect()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采集失败: {e}") from e


@router.get("/api/svc/ports")
async def svc_ports() -> dict[str, Any]:
    """端口体检:在跑但未登记 / 登记但没跑 / 疑似冲突。"""
    try:
        v = _engine().collect()
        p = v["ports"]
        return {
            "status": "success",
            "summary": {
                "registered": v["counts"]["ports_registered"],
                "live": v["counts"]["ports_live"],
                "undocumented": len(p["undocumented"]),
                "stale": len(p["stale"]),
                "conflicts": len(p["conflicts"]),
            },
            **p,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"端口体检失败: {e}") from e


@router.post("/api/svc/action")
async def svc_action(req: ActionRequest) -> dict[str, Any]:
    """起停单个服务(launchd 或 docker,自动判别)。"""
    if req.action not in ("up", "down"):
        raise HTTPException(status_code=400, detail="action 必须是 up 或 down")
    try:
        ok, msg = _engine().service_action(req.id, req.action)
        return {"status": "success" if ok else "failed",
                "id": req.id, "action": req.action, "output": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{req.action} 失败: {e}") from e


@router.post("/api/svc/profile")
async def svc_profile(req: ProfileRequest) -> dict[str, Any]:
    """按场景批量起停:minimal(日常)/ dev(开发)/ data(数据栈)。"""
    if req.action not in ("up", "down"):
        raise HTTPException(status_code=400, detail="action 必须是 up 或 down")
    try:
        results = _engine().profile_action(req.profile, req.action)
        return {"status": "success", "profile": req.profile,
                "action": req.action, "results": results,
                "ok_count": sum(1 for r in results if r.get("ok"))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"profile {req.action} 失败: {e}") from e
