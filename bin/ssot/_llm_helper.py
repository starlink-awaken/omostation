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
        # insert(0) 倒序生效: 列表末尾的最优先。final-ae3570f 是 launchd
        # com.aetherforge.gateway 正在运行的同一份代码, 一致性优先, 避免
        # 主仓子仓副本行为漂移; 主仓路径保留兜底。
        for p in [
            str(ws / "projects" / "aetherforge"),
            str(ws / "projects" / "aetherforge" / "src"),
            str(ws / "projects" / "aetherforge" / "packages" / "gateway" / "src"),
            "/Users/xiamingxing/aetherforge-final-ae3570f",
            "/Users/xiamingxing/aetherforge-final-ae3570f/src",
            "/Users/xiamingxing/aetherforge-final-ae3570f/packages/gateway/src",
        ]:
            if p not in sys.path:
                sys.path.insert(0, p)
        from llm_gateway import ModelGateway

        gw = ModelGateway.create()
        # 2026-08-25 总闸修复: create() 只把 provider register 进 _providers,
        # _models 缓存必须 refresh() 填充 —— cli.py(launchd 版装配)显式跑过
        # 这步, 进程内实例此前没跑 → registry 恒空 → 一切模型解析失败 →
        # llm_ask 46s 慢死。refresh 一次性 ~7s, 单例进程终身复用。
        import asyncio

        asyncio.run(gw._registry.refresh())
        _GATEWAY = gw
        return _GATEWAY
    except Exception:
        return None


def llm_ask(question: str, context: dict[str, Any] | None = None, timeout: float = 60.0, model: str = "") -> str | None:
    """Ask LLM a question, return plain text response.

    Backend 1: AetherForge ModelGateway (omlx local).
    Backend 2: GLM cloud direct (key embedded).
    model: 显式指定本地模型 id(如 "qwen-3.8-27b"); 空=auto-route。
    注意 auto-route 依赖 gateway 复杂度链, 链头若配了本地不存在的模型名
    (如 mythos-fast, 本地 oMLX 只有 mythos)会静默落 LM Link 兜底 —
    稳定场景建议显式传 model (2026-08-25 mail-daemon 路由病根)。
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

            # 2026-08-25 根因修复: 此前 model="" 让网关自选路由, 结果邮件分类
            # 这类轻任务被路由到本地 LM Studio 的 qwythos bf16(18.84GB JIT),
            # mail-daemon 每 30s 轮询一次 → qwythos 反复被拉起驻留, 是 MBP
            # swap 高烧与"神秘加载"的直接元凶。SSOT 邮件分类/轻文本任务固定
            # 走云端免费 glm-4.7-flash(MODEL-BREW-ZHIPU, cost=0)。
            req = GatewayRequest(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                timeout=timeout,
            )
            resp = run_async(gw.generate(req))
            if resp and resp.content:
                return resp.content.strip()
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
