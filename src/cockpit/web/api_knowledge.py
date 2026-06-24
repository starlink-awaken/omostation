"""Knowledge API routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/api/knowledge/search")
async def api_knowledge_search(request: Request):
    try:
        body = await request.json()
        query = body.get("query")
        if not query:
            return JSONResponse({"status": "error", "error": "query is required"}, status_code=400)

        from agora.mcp.bos_resolver import resolve_bos_uri

        # 传递 proxy_manager 是 Phase 3 蜂群感知的关键，但在 cockpit 层面我们直接调用 local resolve 即可，
        # 真正的 proxy_manager 会由 agora_mcp 守护进程持有。Cockpit 这里作为客户端发起调用。
        # 最规范的做法是通过 HTTP 调用 Agora 7422 端口，但这里保持与旧版兼容的直接 import 调用。
        res = await resolve_bos_uri("bos://memory/local/all-search", {"query": query, "limit": 10})
        return JSONResponse({"status": "ok", "result": res})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
