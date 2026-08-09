#!/usr/bin/env python3
"""Shared LLM helper — AetherForge ModelGateway 调用工具.

供 bin/ssot/ 所有 daemon 复用, 避免每个脚本重复实现 LLM 接入逻辑.
架构: AetherForge ModelGateway → omlx local (auto-routing) → GLM cloud 兜底.

Usage:
    from _llm_helper import llm_ask
    response = llm_ask("What are the top 3 priorities?", {"debt": 14})
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_GATEWAY = None


def _get_gateway():
    """Lazy-init AetherForge ModelGateway singleton."""
    global _GATEWAY
    if _GATEWAY is not None:
        return _GATEWAY
    try:
        ws = Path(os.environ.get("WORKSPACE_ROOT", str(_ROOT)))
        for p in [
            str(ws / "projects" / "aetherforge" / "packages" / "gateway" / "src"),
            str(ws / "projects" / "aetherforge" / "src"),
            str(ws / "projects" / "aetherforge"),
        ]:
            if p not in sys.path:
                sys.path.insert(0, p)
        from llm_gateway import ModelGateway

        _GATEWAY = ModelGateway.create()
        return _GATEWAY
    except Exception:
        return None


def llm_ask(
    question: str, context: dict[str, Any] | None = None, timeout: float = 60.0
) -> str | None:
    """Ask LLM a question, return plain text response.

    Backend 1: AetherForge ModelGateway (omlx local).
    Backend 2: GLM cloud direct (key embedded).
    Returns None if all backends fail.
    """
    prompt = question
    if context:
        prompt += f"\nContext: {json.dumps(context, ensure_ascii=False)[:500]}"

    # Backend 1: AetherForge ModelGateway
    gw = _get_gateway()
    if gw is not None:
        try:
            from llm_gateway import GatewayRequest
            from llm_gateway.gateway import run_async

            req = GatewayRequest(
                messages=[{"role": "user", "content": prompt}],
                model="",
                timeout=timeout,
            )
            resp = run_async(gw.generate(req))
            if resp and resp.content:
                return resp.content.strip()
        except Exception:
            pass

    # Backend 2: GLM cloud (key embedded, proven working)
    try:
        body = json.dumps(
            {
                "model": "glm-4.7-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            }
        ).encode()
        req = urllib.request.Request(  # noqa: S310
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            data=body,
            headers={
                "Authorization": "Bearer db6c1d03aadf4853b361448ee235fd14.aWIjxBcAyAO7i1ct",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return content.strip()
    except Exception:
        pass

    return None
