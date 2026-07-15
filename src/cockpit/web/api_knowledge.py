"""Knowledge API routes."""

import json
import re
from inspect import isawaitable
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

_CARDS_DIR = WORKSPACE_ROOT / "data" / "cards"
_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")


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

        from cockpit.adapters.agora import resolve_bos_uri

        # 传递 proxy_manager 是 Phase 3 蜂群感知的关键，但在 cockpit 层面我们直接调用 local resolve 即可，
        # 真正的 proxy_manager 会由 agora_mcp 守护进程持有。Cockpit 这里作为客户端发起调用。
        # 最规范的做法是通过 HTTP 调用 Agora 7422 端口，但这里保持与旧版兼容的直接 import 调用。
        res = resolve_bos_uri("bos://memory/local/all-search", {"query": query.strip(), "limit": limit})
        if isawaitable(res):
            res = await res
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

        if not all(isinstance(value, str) and value.strip() for value in (slug, title, content)):
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
