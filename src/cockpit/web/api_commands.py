"""Commands Reflection API — 暴露 COMMAND_CATALOG + help_map 给 cockpit-ui.

提供:
  GET /api/commands   — 全量命令目录 + 分组 + 引导内容
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/commands", tags=["commands"])


@router.get("")
async def commands_index() -> JSONResponse:
    """全量命令目录 + 分组 + 引导内容."""
    try:
        from cockpit.commands.help_map import BLURB_OVERRIDES, GROUPS, GUIDE_SECTIONS, SCENARIOS
        from cockpit.commands.registry import COMMAND_CATALOG

        commands = [
            {
                "name": meta.name,
                "summary": meta.summary,
                "category": meta.category,
                "example": meta.example,
                "owner": meta.owner,
                "maturity": meta.maturity,
                "risk": meta.risk,
                "delegated_target": meta.delegated_target,
                "chain_enabled": meta.chain_enabled,
            }
            for meta in COMMAND_CATALOG.values()
        ]

        return JSONResponse({
            "available": True,
            "commands": commands,
            "groups": [
                {"key": key, "label": label, "count": len(rows)}
                for key, label, rows in GROUPS
            ],
            "guide_sections": GUIDE_SECTIONS,
            "scenarios": SCENARIOS,
            "blurb_overrides": BLURB_OVERRIDES,
            "total": len(commands),
        })
    except Exception as exc:
        logger.warning("加载命令目录失败: %s", exc)
        return JSONResponse({"available": False, "error": str(exc), "commands": [], "total": 0})
