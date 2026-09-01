"""Chains Reflection API — 暴露 chain spec 给 cockpit-ui.

提供:
  GET /api/chains          — 列出所有可用 chain
  GET /api/chains/{id}     — 单个 chain spec 详情
  POST /api/chains/{id}/dry-run  — 展开模板变量（不执行）
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chains", tags=["chains"])


@router.get("")
async def chains_list() -> JSONResponse:
    """列出所有可用 chain."""
    try:
        from cockpit.chain.spec import chain_source, list_chains, parse_spec

        chains = []
        for cid in list_chains():
            src = chain_source(cid)
            raw, _ = _load_raw_safe(cid)
            if raw:
                chains.append({
                    "id": cid,
                    "name": raw.get("name", cid),
                    "description": raw.get("description", ""),
                    "step_count": len(raw.get("steps", [])),
                    "source": str(src) if src else None,
                })
        return JSONResponse({"available": True, "chains": chains, "total": len(chains)})
    except Exception as exc:
        logger.warning("加载 chain 列表失败: %s", exc)
        return JSONResponse({"available": False, "error": str(exc), "chains": [], "total": 0})


@router.get("/{chain_id}")
async def chain_detail(chain_id: str) -> JSONResponse:
    """单个 chain spec 详情."""
    try:
        from cockpit.chain.spec import _load_raw, parse_spec

        raw, source = _load_raw(chain_id)
        spec = parse_spec(raw, str(source))
        return JSONResponse({
            "available": True,
            "id": chain_id,
            "name": raw.get("name", chain_id),
            "description": raw.get("description", ""),
            "params": raw.get("params", {}),
            "steps": [
                {
                    "name": s.name,
                    "command": s.command,
                    "args": s.args,
                    "when": s.when,
                    "on_failure": s.on_failure,
                    "retry": s.retry,
                    "capture_output_to": s.capture_output_to,
                }
                for s in spec.steps
            ],
            "hitl": raw.get("hitl", []),
            "timeout": raw.get("timeout", 600),
        })
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Chain '{chain_id}' not found")
    except Exception as exc:
        logger.warning("加载 chain %s 失败: %s", chain_id, exc)
        return JSONResponse({"available": False, "error": str(exc)})


@router.post("/{chain_id}/dry-run")
async def chain_dry_run(chain_id: str) -> JSONResponse:
    """展开模板变量（不执行）."""
    try:
        from cockpit.chain.context import render_template
        from cockpit.chain.spec import _load_raw, parse_spec

        raw, source = _load_raw(chain_id)
        spec = parse_spec(raw, str(source))

        # Dry-run: render templates with placeholder values
        rendered_steps = []
        for step in spec.steps:
            rendered_steps.append({
                "name": step.name,
                "command": step.command,
                "args": step.args,
                "when": step.when,
                "argv": step.argv(),
            })

        return JSONResponse({
            "available": True,
            "id": chain_id,
            "dry_run": True,
            "steps": rendered_steps,
        })
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Chain '{chain_id}' not found")
    except Exception as exc:
        logger.warning("Chain %s dry-run 失败: %s", chain_id, exc)
        return JSONResponse({"available": False, "error": str(exc)})


def _load_raw_safe(chain_id: str) -> tuple[dict[str, Any] | None, Any]:
    """安全加载 raw spec."""
    try:
        from cockpit.chain.spec import _load_raw
        return _load_raw(chain_id)
    except FileNotFoundError:
        return None, None
