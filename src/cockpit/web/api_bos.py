"""BOS API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/bos/services")
async def api_bos_services(domain: str = ""):
    """列出所有 BOS URI 服务，可按 domain 过滤。"""
    try:

        from agora.mcp.resolver.services import POC_SERVICES

        services = []
        for s in POC_SERVICES:
            if domain and s.domain != domain:
                continue
            services.append({
                "uri": s.uri,
                "domain": s.domain,
                "action": s.action,
                "transport": s.transport,
            })
        return JSONResponse(content={"total": len(services), "services": services})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/resolve")
async def api_bos_resolve(uri: str = "", arguments: str = "{}"):
    """解析一个 BOS URI——返回路由表中的服务信息。"""
    if not uri:
        return JSONResponse(content={"error": "uri 参数必填"}, status_code=400)
    if not uri.startswith("bos://"):
        return JSONResponse(content={"error": "URI 必须是 bos:// 格式"}, status_code=400)

    try:

        from agora.mcp.resolver.api import parse_bos_uri
        from agora.mcp.resolver.services import POC_SERVICES

        # 1. 解析 URI
        parsed = parse_bos_uri(uri)
        if "error" in parsed:
            return JSONResponse(content={"error": parsed["error"]}, status_code=400)

        # 2. 查找匹配服务
        matched = [s for s in POC_SERVICES if s.uri == uri]
        if not matched:
            return JSONResponse(content={
                "uri": uri,
                "parsed": parsed,
                "matched": False,
                "message": "URI 在注册表中未匹配到服务",
            })

        svc = matched[0]
        return JSONResponse(content={
            "uri": uri,
            "parsed": parsed,
            "matched": True,
            "service": {
                "domain": svc.domain,
                "package": svc.package,
                "action": svc.action,
                "transport": svc.transport,
                "description": svc.description,
            },
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/health")
async def api_bos_health():
    """BOS 系统健康检查。"""
    try:

        from agora.mcp.bos_metrics import bos_metrics
        from agora.mcp.resolver.services import POC_SERVICES

        m = bos_metrics.health()
        by_domain: dict[str, int] = {}
        for s in POC_SERVICES:
            by_domain[s.domain] = by_domain.get(s.domain, 0) + 1

        return JSONResponse(content={
            "status": "ok",
            "total_routes": len(POC_SERVICES),
            "domains": by_domain,
            "metrics": m,
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/metrics")
async def api_bos_metrics(prefix: str = ""):
    """BOS 调用指标。"""
    try:

        from agora.mcp.bos_metrics import bos_metrics

        if prefix:
            data = bos_metrics.status(prefix)
        else:
            data = bos_metrics.summary()
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# 债务加载 / E2E / OMO 报告 (从原 dashboard_server.py 迁移)
# ═══════════════════════════════════════════════════════════════

_DEFAULT_COMPUTE_TOPOLOGY = [
    {"id": "local-mac", "label": "Local-Mac", "kind": "local", "role": "Cockpit / Agent host"},
    {"id": "macmini-ollama", "label": "MacMini (Ollama)", "kind": "local", "role": "Local inference"},
    {"id": "y7000p-lmstudio", "label": "Y7000P (LMStudio)", "kind": "local", "role": "GPU workstation"},
    {"id": "cloud-cc-switch", "label": "Cloud (cc-switch)", "kind": "cloud", "role": "Remote provider relay"},
]



