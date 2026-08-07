"""Knowledge API routes."""

import json
import logging
import re
from inspect import isawaitable
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT

logger = logging.getLogger("cockpit.web.api_knowledge")
router = APIRouter()

_CARDS_DIR = WORKSPACE_ROOT / "data" / "cards"
_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
from cockpit.web._agora_ports import agora_http_endpoint

_AGORA_HTTP_ENDPOINT = agora_http_endpoint()


async def _resolve_bos_uri_network_or_compat(uri: str, payload: dict) -> dict:
    """Resolve BOS URI via Agora /v1/tools/call (bos_resolve tool) with graceful local fallback.

    Agora 实际暴露的 HTTP 端点: /v1/tools/call, /v1/backends/register, /health, /api/v1/a2a/send
    /bos/resolve 不存在于 HTTP 层，通过 /v1/tools/call 调用 bos_resolve MCP tool。
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(
                f"{_AGORA_HTTP_ENDPOINT}/v1/tools/call",
                json={"tool": "bos_resolve", "arguments": {"uri": uri, "payload": payload}},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    return data.get("result", data)
    except Exception as e:
        logger.debug("Network BOS resolution fallback to in-process compat: %s", e)

    # Defensive fallback to compat in-process adapter for standalone / unit tests
    from cockpit.adapters.agora import resolve_bos_uri

    res = resolve_bos_uri(uri, payload)
    if isawaitable(res):
        res = await res
    return res


async def _notify_knowledge_event(event_uri: str, payload: dict) -> None:
    """Emit write-after event via Agora /v1/tools/call (publish_event MCP tool).

    /bos/emit 不存在于 agora HTTP 层，正确路径是 /v1/tools/call + publish_event 工具。
    Agora EventBus 收到事件后，通过 callback_url push 给已注册的 KnowledgeIndexer。
    失败静默降级：Agora offline 不影响写入成功，Indexer 重新上线后可通过 get_event_log 补偿。
    """
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.post(
                f"{_AGORA_HTTP_ENDPOINT}/v1/tools/call",
                json={
                    "tool": "publish_event",
                    "arguments": {
                        "event_type": event_uri,
                        "payload": json.dumps(payload),
                        "source": "cockpit.api_knowledge",
                    },
                },
            )
    except Exception as e:
        logger.debug("Knowledge event emission non-blocking fallback: %s", e)


@router.post("/api/knowledge/search")
async def api_knowledge_search(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"status": "error", "error": "request body must be an object"}, status_code=400)
        query = body.get("query")
        if not isinstance(query, str) or not query.strip():
            return JSONResponse({"status": "error", "error": "query is required"}, status_code=400)
        raw_limit = body.get("limit", 10)
        try:
            limit = min(max(int(raw_limit), 1), 50)
        except (TypeError, ValueError):
            return JSONResponse({"status": "error", "error": "limit must be an integer"}, status_code=400)

        # 架构收敛：优先使用 HTTP BOS Transport 网络解耦协议，带兼容态平滑降级
        res = await _resolve_bos_uri_network_or_compat(
            "bos://memory/local/all-search",
            {"query": query.strip(), "limit": limit},
        )
        if isinstance(res, dict) and isawaitable(res.get("result")):
            res = {**res, "result": await res["result"]}
        return JSONResponse({"status": "ok", "result": res})
    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/knowledge/put")
async def api_knowledge_put(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"status": "error", "error": "request body must be an object"}, status_code=400)
        slug = body.get("slug")
        title = body.get("title")
        content = body.get("content")
        tags = body.get("tags") or []

        if not isinstance(slug, str) or not isinstance(title, str) or not isinstance(content, str):
            return JSONResponse({"status": "error", "error": "slug, title, and content are required"}, status_code=400)
        slug = slug.strip()
        title = title.strip()
        content = content.strip()
        if not _SLUG_PATTERN.fullmatch(slug):
            return JSONResponse(
                {"status": "error", "error": "slug must use 1-120 letters, numbers, hyphens, or underscores"},
                status_code=400,
            )
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            return JSONResponse({"status": "error", "error": "tags must be a list of strings"}, status_code=400)
        tags = [tag.strip() for tag in tags if tag.strip()][:20]

        # Create cards directory if missing
        _CARDS_DIR.mkdir(parents=True, exist_ok=True)

        # Format markdown card with yaml frontmatter
        tags_str = ", ".join(json.dumps(tag, ensure_ascii=False) for tag in tags)
        card_content = f"""---
title: {json.dumps(title, ensure_ascii=False)}
tags: [{tags_str}]
slug: {json.dumps(slug, ensure_ascii=False)}
---
{content}
"""
        file_path = _CARDS_DIR / f"{slug}.md"
        file_path.write_text(card_content, encoding="utf-8")

        # 方案 C：写后即时分发卡片更新通知（Event-Driven Card Indexing Convergence）
        # ADR-0372 D5: emit canonical memory-domain URI (indexer dual-accepts brain legacy).
        await _notify_knowledge_event(
            "bos://memory/events/card_updated",
            {
                "slug": slug,
                "title": title,
                "path": str(file_path),
                "action": "upsert",
            },
        )

        return JSONResponse(
            {
                "status": "success",
                "msg": "知识注入成功，已落盘至 bos://memory (本地卡片).",
                "knowledge_ref": f"memory:{slug}",
                "source_ref": f"bos://memory/cards/{slug}",
                "path": str(file_path),
            }
        )
    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
