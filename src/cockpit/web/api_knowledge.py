"""Knowledge API routes."""

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

_WS = os.environ.get("WORKSPACE_ROOT") or str(Path.home() / "Workspace")
_CARDS_DIR = Path(_WS) / "data" / "cards"


@router.post("/api/knowledge/search")
async def api_knowledge_search(request: Request):
    try:
        body = await request.json()
        query = body.get("query")
        if not query:
            return JSONResponse({"status": "error", "error": "query is required"}, status_code=400)

        from cockpit.adapters.agora import resolve_bos_uri

        # 传递 proxy_manager 是 Phase 3 蜂群感知的关键，但在 cockpit 层面我们直接调用 local resolve 即可，
        # 真正的 proxy_manager 会由 agora_mcp 守护进程持有。Cockpit 这里作为客户端发起调用。
        # 最规范的做法是通过 HTTP 调用 Agora 7422 端口，但这里保持与旧版兼容的直接 import 调用。
        res = await resolve_bos_uri("bos://memory/local/all-search", {"query": query, "limit": 10})
        return JSONResponse({"status": "ok", "result": res})
    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/knowledge/put")
async def api_knowledge_put(request: Request):
    try:
        body = await request.json()
        slug = body.get("slug")
        title = body.get("title")
        content = body.get("content")
        tags = body.get("tags") or []

        if not slug or not title or not content:
            return JSONResponse({"status": "error", "error": "slug, title, and content are required"}, status_code=400)

        # Create cards directory if missing
        _CARDS_DIR.mkdir(parents=True, exist_ok=True)

        # Format markdown card with yaml frontmatter
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        card_content = f"""---
title: {title}
tags: [{tags_str}]
slug: {slug}
---
{content}
"""
        file_path = _CARDS_DIR / f"{slug}.md"
        file_path.write_text(card_content, encoding="utf-8")

        return JSONResponse({"status": "success", "msg": "知识注入成功，已落盘至 bos://memory (本地卡片)."})
    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
