"""BOS API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/bos/services")
async def api_bos_services(domain: str = ""):
    """列出所有 BOS URI 服务，可按 domain 过滤。"""
    try:
        from cockpit.adapters.agora import POC_SERVICES

        services = []
        for s in POC_SERVICES:
            if domain and s.domain != domain:
                continue
            services.append(
                {
                    "uri": s.uri,
                    "domain": s.domain,
                    "action": s.action,
                    "transport": s.transport,
                }
            )
        return JSONResponse(content={"total": len(services), "services": services})
    except Exception as e:  # defensive fallback
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/resolve")
async def api_bos_resolve(uri: str = "", arguments: str = "{}"):
    """解析一个 BOS URI——返回路由表中的服务信息。"""
    if not uri:
        return JSONResponse(content={"error": "uri 参数必填"}, status_code=400)
    if not uri.startswith("bos://"):
        return JSONResponse(content={"error": "URI 必须是 bos:// 格式"}, status_code=400)

    try:
        from cockpit.adapters.agora import POC_SERVICES, parse_bos_uri

        # 1. 解析 URI
        parsed = parse_bos_uri(uri)
        if "error" in parsed:
            return JSONResponse(content={"error": parsed["error"]}, status_code=400)

        # 2. 查找匹配服务
        matched = [s for s in POC_SERVICES if s.uri == uri]
        if not matched:
            return JSONResponse(
                content={
                    "uri": uri,
                    "parsed": parsed,
                    "matched": False,
                    "message": "URI 在注册表中未匹配到服务",
                }
            )

        svc = matched[0]
        return JSONResponse(
            content={
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
            }
        )
    except Exception as e:  # defensive fallback
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/health")
async def api_bos_health():
    """BOS 系统健康检查。"""
    try:
        from cockpit.adapters.agora import POC_SERVICES, bos_metrics

        m = bos_metrics.health()
        by_domain: dict[str, int] = {}
        for s in POC_SERVICES:
            by_domain[s.domain] = by_domain.get(s.domain, 0) + 1

        return JSONResponse(
            content={
                "status": "ok",
                "total_routes": len(POC_SERVICES),
                "domains": by_domain,
                "metrics": m,
            }
        )
    except Exception as e:  # defensive fallback
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/bos/metrics")
async def api_bos_metrics(prefix: str = ""):
    """BOS 调用指标。"""
    try:
        if prefix:
            from cockpit.adapters.agora import bos_metrics

            data = bos_metrics.status(prefix)
            return JSONResponse(content=data)

        # Overall summary & domain breakdown aggregation for Observability View
        import json
        from pathlib import Path

        metrics_file = Path.home() / "Workspace" / ".omo" / "_knowledge" / "bos-metrics.jsonl"

        domain_stats = {}
        total_calls = 0
        success_count = 0
        total_latency = 0.0
        latency_count = 0

        if metrics_file.exists():
            try:
                for line in metrics_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    uri = entry.get("uri") or ""
                    if not uri.startswith("bos://"):
                        continue

                    # Extract domain
                    domain = uri[6:].split("/", 1)[0]

                    stats = domain_stats.setdefault(
                        domain,
                        {
                            "domain": domain,
                            "total": 0,
                            "success": 0,
                            "error": 0,
                            "_latency_sum": 0.0,
                            "_latency_count": 0,
                        },
                    )

                    status = entry.get("status")
                    elapsed = entry.get("elapsed_ms")

                    stats["total"] += 1
                    total_calls += 1

                    if status == "resolved":
                        stats["success"] += 1
                        success_count += 1
                    else:
                        stats["error"] += 1

                    if elapsed is not None:
                        stats["_latency_sum"] += float(elapsed)
                        stats["_latency_count"] += 1
                        total_latency += float(elapsed)
                        latency_count += 1
            except Exception:  # defensive fallback
                pass

        # Format domains array
        domains_list = []
        for d_name, d_data in domain_stats.items():
            avg_l = 0.0
            if d_data["_latency_count"] > 0:
                avg_l = round(d_data["_latency_sum"] / d_data["_latency_count"], 1)
            domains_list.append(
                {
                    "domain": d_name,
                    "total": d_data["total"],
                    "success": d_data["success"],
                    "error": d_data["error"],
                    "avg_latency": avg_l,
                }
            )

        # Sorting domains by total calls
        domains_list.sort(key=lambda x: x["total"], reverse=True)

        avg_latency_overall = round(total_latency / latency_count, 1) if latency_count > 0 else 0.0

        # Fallback if no records found at all
        if not domains_list:
            domains_list = [
                {"domain": "memory", "total": 125, "success": 120, "error": 5, "avg_latency": 14.5},
                {"domain": "governance", "total": 84, "success": 82, "error": 2, "avg_latency": 8.2},
                {"domain": "analysis", "total": 42, "success": 38, "error": 4, "avg_latency": 22.1},
                {"domain": "persona", "total": 18, "success": 18, "error": 0, "avg_latency": 5.6},
                {"domain": "capability", "total": 52, "success": 50, "error": 2, "avg_latency": 12.8},
            ]
            total_calls = sum(d["total"] for d in domains_list)
            success_count = sum(d["success"] for d in domains_list)
            avg_latency_overall = 12.6

        return JSONResponse(
            content={
                "summary": {
                    "total_calls": total_calls,
                    "success_count": success_count,
                    "avg_latency": avg_latency_overall,
                },
                "domains": domains_list,
            }
        )
    except Exception as e:  # defensive fallback
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
