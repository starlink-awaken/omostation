"""Capability Registry API — 暴露能力注册表给 cockpit-ui.

读取 docs/generated/capability-registry.yaml, 提供:
  GET /api/capability/summary   — 总览统计
  GET /api/capability/servers   — MCP 服务器列表
  GET /api/capability/bos       — BOS 服务域分布
  GET /api/capability/cli       — CLI 命令列表
  GET /api/capability/search    — 搜索工具/命令/服务
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/capability", tags=["capability"])

_REGISTRY_PATH = WORKSPACE_ROOT / "docs" / "generated" / "capability-registry.yaml"


def _load_registry() -> dict[str, Any]:
    """加载能力注册表, 不存在则返回空骨架."""
    if not _REGISTRY_PATH.exists():
        return {
            "totals": {"mcp_servers": 0, "mcp_tools": 0, "bos_services": 0, "bos_domains": 0, "cli_commands": 0},
            "mcp_servers": [],
            "bos_services": {"_domain_counts": {}, "domains": {}},
            "cli_commands": [],
            "available": False,
        }
    try:
        import yaml

        data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
        data["available"] = True
        return data
    except Exception as exc:
        logger.warning("加载能力注册表失败: %s", exc)
        return {"available": False, "error": str(exc), "totals": {}}


@router.get("/summary")
async def capability_summary() -> JSONResponse:
    """能力总览: 各通道数量统计."""
    reg = _load_registry()
    return JSONResponse(
        {
            "available": reg.get("available", False),
            "generated_at": reg.get("generated_at", ""),
            "version": reg.get("version", ""),
            "totals": reg.get("totals", {}),
        }
    )


@router.get("/servers")
async def capability_servers(
    layer: str | None = Query(None, description="按层过滤 (L0/L1/L2/L3/L4/I0/X/M0)"),
) -> JSONResponse:
    """MCP 服务器列表, 可按层过滤."""
    reg = _load_registry()
    servers = reg.get("mcp_servers", [])
    if layer:
        servers = [s for s in servers if s.get("layer") == layer]
    return JSONResponse({"servers": servers, "count": len(servers)})


@router.get("/bos")
async def capability_bos() -> JSONResponse:
    """BOS 服务域分布."""
    reg = _load_registry()
    bos = reg.get("bos_services", {})
    return JSONResponse(
        {
            "domain_counts": bos.get("_domain_counts", {}),
            "total": reg.get("totals", {}).get("bos_services", 0),
        }
    )


@router.get("/cli")
async def capability_cli() -> JSONResponse:
    """CLI 命令列表."""
    reg = _load_registry()
    commands = reg.get("cli_commands", [])
    return JSONResponse({"commands": commands, "count": len(commands)})


@router.get("/workflows")
async def capability_workflows() -> JSONResponse:
    """工作流列表."""
    reg = _load_registry()
    workflows = reg.get("workflows", [])
    return JSONResponse({"workflows": workflows, "count": len(workflows)})


@router.get("/skills")
async def capability_skills() -> JSONResponse:
    """技能列表."""
    reg = _load_registry()
    skills = reg.get("skills", [])
    return JSONResponse({"skills": skills, "count": len(skills)})


@router.get("/search")
async def capability_search(
    q: str = Query(..., description="搜索关键词 (匹配工具名/命令名/服务 URI)"),
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """跨通道搜索: MCP 工具 / CLI 命令 / BOS 服务."""
    reg = _load_registry()
    query_lower = q.lower()
    results: list[dict[str, Any]] = []

    # 搜 MCP 工具
    for srv in reg.get("mcp_servers", []):
        for tool in srv.get("tools", []):
            if query_lower in str(tool).lower():
                results.append({"type": "mcp_tool", "server": srv["id"], "name": tool, "layer": srv.get("layer", "")})
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    # 搜 CLI 命令
    if len(results) < limit:
        for cmd in reg.get("cli_commands", []):
            if query_lower in cmd.get("name", "").lower() or query_lower in cmd.get("description", "").lower():
                results.append({"type": "cli_command", "name": cmd["name"], "description": cmd.get("description", "")})
                if len(results) >= limit:
                    break

    return JSONResponse({"query": q, "results": results, "count": len(results)})
