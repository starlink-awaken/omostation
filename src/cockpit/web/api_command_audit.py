"""Command-Audit Reflection API — 暴露评分卡数据给 cockpit-ui.

提供:
  GET /api/command-audit/summary   — 15 维均分 + 低分 TOP-N + 覆盖率
  GET /api/command-audit/{cmd}     — 单命令评分卡详情
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from cockpit.commands.command_audit import AUDIT_DIR, DIMENSIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/command-audit", tags=["command-audit"])


def _load_scorecards() -> list[dict[str, Any]]:
    """加载所有评分卡."""
    cards = []
    if not AUDIT_DIR.exists():
        return cards
    for f in sorted(AUDIT_DIR.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data:
                data["_file"] = f.stem
                cards.append(data)
        except Exception:
            pass
    return cards


def _calc_summary(cards: list[dict]) -> dict[str, Any]:
    """计算 15 维均分."""
    dim_scores: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for card in cards:
        for dim in DIMENSIONS:
            score = card.get(dim, {}).get("score")
            if score is not None:
                dim_scores[dim].append(score)

    averages = {
        dim: round(sum(scores) / len(scores), 2) if scores else None
        for dim, scores in dim_scores.items()
    }

    # Lowest-scoring commands per dimension
    low_cards = [c for c in cards if any(c.get(d, {}).get("score", 5) <= 2 for d in DIMENSIONS)]

    return {
        "dimension_averages": averages,
        "total_cards": len(cards),
        "scored_cards": sum(1 for c in cards if any(c.get(d, {}).get("score") is not None for d in DIMENSIONS)),
        "low_score_count": len(low_cards),
    }


@router.get("/summary")
async def audit_summary() -> JSONResponse:
    """15 维均分 + 覆盖率."""
    try:
        cards = _load_scorecards()
        summary = _calc_summary(cards)
        return JSONResponse({
            "available": True,
            "dimensions": DIMENSIONS,
            **summary,
        })
    except Exception as exc:
        logger.warning("加载评分卡汇总失败: %s", exc)
        return JSONResponse({"available": False, "error": str(exc)})


@router.get("/{cmd_path:path}")
async def audit_detail(cmd_path: str) -> JSONResponse:
    """单命令评分卡详情."""
    # cmd_path may contain dots (e.g. "research.list") — try as-is and with .yaml
    candidate = AUDIT_DIR / f"{cmd_path}.yaml"
    if not candidate.exists():
        candidate = AUDIT_DIR / cmd_path

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Scorecard '{cmd_path}' not found")

    try:
        import yaml
        data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        return JSONResponse({"available": True, "scorecard": data})
    except Exception as exc:
        logger.warning("加载评分卡 %s 失败: %s", cmd_path, exc)
        return JSONResponse({"available": False, "error": str(exc)})
