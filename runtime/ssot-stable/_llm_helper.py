#!/usr/bin/env python3
"""Shared LLM helper — 经 aetherforge 门面调用 LLM.

供 bin/ssot/ 所有 daemon 复用, 避免每个脚本重复实现 LLM 接入逻辑.
架构: aetherforge 门面(HTTP, 按别名路由) → 未配置时 GLM cloud 兜底.

Usage:
    from _llm_helper import llm_ask
    response = llm_ask("What are the top 3 priorities?", {"debt": 14}, model="fast")
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from llm_provider import _gateway_key, _gateway_url

DEFAULT_ALIAS = "fast"


def llm_ask(question: str, context: dict[str, Any] | None = None, timeout: float = 60.0, model: str = "") -> str | None:
    """Ask LLM a question, return plain text response.

    Backend 1: aetherforge 门面 /v1/chat/completions。model 传门面别名
    (aliases.yaml, 如 fast/triage/reasoning), 空则用 fast。
    此前进程内直接加载网关库: 绕过门面统计与别名表, 请求的 qwen-3.8-27b
    早已不存在, 被静默换成 mythos-fast(2026-09-29 邮件闭环实测)。
    Backend 2: GLM cloud direct (ZHIPU_API_KEY 未配置则跳过)。
    Returns None if all backends fail.
    """
    prompt = question
    if context:
        prompt += f"\nContext: {json.dumps(context, ensure_ascii=False)[:500]}"

    # Backend 1: aetherforge 门面
    try:
        body = json.dumps(
            {"model": model or DEFAULT_ALIAS, "messages": [{"role": "user", "content": prompt}]}
        ).encode()
        req = urllib.request.Request(
            f"{_gateway_url()}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_gateway_key()}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        if content:
            return content.strip()
    except Exception:
        pass

    # Backend 2: GLM cloud (ZHIPU_API_KEY 环境变量, 未配置则跳过)
    glm_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not glm_key:
        return None
    try:
        body = json.dumps(
            {
                "model": "glm-4.7-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            }
        ).encode()
        req = urllib.request.Request(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {glm_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return content.strip()
    except Exception:
        pass

    return None
