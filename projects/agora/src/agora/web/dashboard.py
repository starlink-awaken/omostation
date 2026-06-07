"""BOS Dashboard — Agora 管理 UI (FastAPI).

运行:
    agora-web             # 通过 MCP HTTP (:7422) 启动 + FastMCP
    uv run python -m agora.web.dashboard --standalone  # 独立模式

访问: http://localhost:7430/dashboard
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── BOS 数据源 (内联调用，不依赖 MCP 协议) ──────────────

try:
    from agora.mcp.bos_router import bos_router
    from agora.mcp.bos_middleware import bos_cache, bos_circuit_breaker, bos_rate_limiter
    from agora.mcp.bos_metrics import bos_metrics
    from agora.mcp.bos_resolver import POC_SERVICES
    HAS_BOS = True
except ImportError:
    HAS_BOS = False


def _collect_status() -> dict:
    """收集 BOS 系统全量状态。"""
    result = {
        "service": "agora",
        "status": "ok",
        "timestamp": time.time(),
    }
    if not HAS_BOS:
        result["status"] = "bos_unavailable"
        return result

    # BOS Router
    result["router"] = {
        "total_routes": bos_router.count(),
        "by_adapter": bos_router.stats(),
    }

    # POC Services
    result["poc_services"] = {
        "total": len(POC_SERVICES),
        "uris": sorted(POC_SERVICES.keys()),
    }

    # BOS Middleware
    result["rate_limiter"] = bos_rate_limiter.status()
    result["circuit_breaker"] = {
        "open_circuits": bos_circuit_breaker.status(),
    }
    result["cache"] = bos_cache.status()

    # BOS Metrics
    result["metrics"] = bos_metrics.summary()
    result["metrics_detail"] = bos_metrics.status()

    # Domains
    from collections import Counter
    doms: Counter = Counter()
    from agora.mcp.bos_resolver import list_services as _list_poc_services
    for svc in _list_poc_services():
        doms[svc.get("domain", "unknown")] += 1
    result["domains"] = dict(doms)

    return result


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agora BOS Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9}
.header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;gap:12px}
.header h1{font-size:18px;color:#58a6ff}.header .sub{color:#8b949e;font-size:12px}
.header .ver{color:#484f58;font-size:11px;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;padding:24px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.card h2{font-size:13px;color:#8b949e;text-transform:uppercase;margin-bottom:12px;letter-spacing:.5px}
.card h3{font-size:12px;color:#8b949e;margin:8px 0 4px}
.stat-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #21262d;font-size:13px}
.stat-val{color:#58a6ff;font-weight:600}.stat-good{color:#3fb950}.stat-warn{color:#d29922}.stat-bad{color:#f85149}
.uri-item{font-size:11px;padding:2px 0;color:#8b949e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.refresh{color:#8b949e;font-size:11px;text-align:right;padding:0 24px 16px}
.badge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}
.badge-poc{background:#1f2937;color:#60a5fa}.badge-proxy{background:#1c1917;color:#fbbf24}
.badge-internal{background:#052e16;color:#4ade80}
</style>
</head>
<body>
<div class="header">
  <div style="font-size:24px">&#x25C8;</div>
  <div><h1>Agora BOS Dashboard</h1><div class="sub">BOS URI Routing &middot; Middleware &middot; Metrics</div></div>
  <div class="ver" id="refresh-time"></div>
</div>
<div class="grid" id="grid"></div>
<div class="refresh">Auto-refreshes every 5s</div>
<script>
async function refresh(){try{
const r=await fetch('/api/bos/status');const d=await r.json();
let html='';
// Card 1: Router
html+='<div class="card"><h2>BOS Router</h2>';
html+='<div class="stat-row"><span>Routes</span><span class="stat-val">'+(d.router?.total_routes||0)+'</span></div>';
const adapters=d.router?.by_adapter||{};
for(const[a,c]of Object.entries(adapters)){
const cls=a==='poc'?'badge-poc':a==='proxy'?'badge-proxy':'badge-internal';
html+='<div class="stat-row"><span><span class="badge '+cls+'">'+a+'</span></span><span class="stat-val">'+c+'</span></div>';}
html+='<h3>POC URIs ('+(d.poc_services?.total||0)+')</h3>';
(d.poc_services?.uris||[]).slice(0,20).forEach(u=>{html+='<div class="uri-item">'+u+'</div>'});
if((d.poc_services?.uris||[]).length>20)html+='<div class="uri-item" style="color:#484f58">... '+(d.poc_services?.uris.length-20)+' more</div>';
html+='</div>';
// Card 2: Domains
html+='<div class="card"><h2>Domains</h2>';
const domains=d.domains||{};
for(const[dom,cnt]of Object.entries(domains)){
html+='<div class="stat-row"><span>bos://'+dom+'/</span><span class="stat-val">'+cnt+'</span></div>';}
html+='</div>';
// Card 3: Middleware
html+='<div class="card"><h2>Middleware</h2>';
html+='<h3>Rate Limiter</h3>';
const rl=d.rate_limiter||{};
for(const[k,v]of Object.entries(rl)){html+='<div class="stat-row"><span>'+k+'</span><span class="stat-val">'+(v||'-')+'</span></div>';}
html+='<h3>Circuit Breaker</h3>';
const cb=d.circuit_breaker?.open_circuits||{};
const cbCount=typeof cb==='object'?Object.keys(cb).length:(cb||0);
html+='<div class="stat-row"><span>Open Circuits</span><span class="'+(cbCount>0?'stat-bad':'stat-good')+'">'+cbCount+'</span></div>';
html+='<h3>Cache</h3>';
const cache=d.cache||{};
if(cache.size!==undefined)html+='<div class="stat-row"><span>Size</span><span class="stat-val">'+cache.size+'</span></div>';
if(cache.hit_rate!==undefined)html+='<div class="stat-row"><span>Hit Rate</span><span class="stat-val">'+(cache.hit_rate*100).toFixed(1)+'%</span></div>';
html+='</div>';
// Card 4: Metrics
html+='<div class="card"><h2>Metrics</h2>';
const m=d.metrics||{};
html+='<div class="stat-row"><span>Total Calls</span><span class="stat-val">'+m.total_calls+'</span></div>';
html+='<div class="stat-row"><span>Success Rate</span><span class="'+(m.success_rate>0.9?'stat-good':'stat-warn')+'">'+(m.success_rate*100).toFixed(1)+'%</span></div>';
html+='<div class="stat-row"><span>Avg Latency</span><span class="stat-val">'+m.avg_latency_ms?.toFixed(1)+'ms</span></div>';
html+='<h3>Per-Prefix</h3>';
const detail=d.metrics_detail||{};
for(const[pref,s]of Object.entries(detail).sort((a,b)=>b[1].calls-a[1].calls).slice(0,15)){
html+='<div class="stat-row"><span style="font-size:11px">'+pref+'</span><span><span class="stat-val">'+s.calls+'</span> <span style="color:'+(s.success_rate>0.9?'#3fb950':'#d29922')+'">'+(s.success_rate*100).toFixed(0)+'%</span> <span style="color:#8b949e">'+s.avg_latency_ms?.toFixed(0)+'ms</span></span></div>';}
html+='</div>';
document.getElementById('grid').innerHTML=html;
document.getElementById('refresh-time').textContent=new Date().toLocaleTimeString();
}catch(e){console.error(e);}}
refresh();setInterval(refresh,5000);
</script></body></html>"""


def create_app() -> FastAPI:
    """创建 BOS Dashboard FastAPI 应用。"""
    app = FastAPI(title="Agora BOS Dashboard", version="1.0.0")

    @app.get("/api/bos/status")
    async def bos_status():
        return JSONResponse(content=_collect_status())

    @app.get("/", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    async def dashboard_page():
        return HTMLResponse(content=_DASHBOARD_HTML, status_code=200)

    return app


def run_standalone():
    """独立运行模式: 启动 dash 服务器在 :7430."""
    import uvicorn
    app = create_app()
    port = int(os.environ.get("AGORA_DASHBOARD_PORT", "7430"))
    host = os.environ.get("AGORA_DASHBOARD_HOST", "0.0.0.0")
    print(f"Starting Agora BOS Dashboard at http://{host}:{port}/dashboard")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_standalone()
