"""Cockpit Web Dashboard — FastAPI unified status aggregation hub (L3).

原有 stdlib http.server 已升级为 FastAPI, 保持所有现有 API 向后兼容。
新增 /api/v1/status + /overview 统一层聚合页面。

Endpoints (现有, 向后兼容):
  GET /               → dashboard HTML (原有模板)
  GET /api/status     → i0_status() JSON
  GET /api/services   → i0_services() JSON
  GET /api/events     → i0_events(50) JSON
  GET /api/protocols  → i0_protocols() JSON
  GET /api/debt       → debt ledger JSON
  GET /api/context    → workspace_context JSON (L4 bridge)
  GET /api/cards      → cards_status JSON (L4 bridge)

Endpoints (新增):
  GET /api/v1/status  → 统一层聚合 JSON (I0+L2+L1+L0+L4)
  GET /healthz        → 健康检查
  GET /overview       → 统一层聚合 HTML 页面

Usage:
    cockpit dashboard
    # or
    python3 -m cockpit.dashboard_server
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# ─── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent  # cockpit/src/cockpit/
WORKSPACE_ROOT = Path.home() / "Workspace"
OMO_ROOT = Path.home() / "Workspace/projects/omo"
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))
DASHBOARD_HTML = WORKSPACE_ROOT / "projects" / "cockpit" / "web" / "dashboard.html"
M0_SNAPSHOT_PATH = Path.home() / "Workspace/projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml"
HERMES_CONSOLE_DIST = Path.home() / "Workspace/projects/hermes-console/dist"
PROVIDER_PLANE_PATH = WORKSPACE_ROOT / ".omo" / "state" / "provider-plane.yaml"
LLM_QUOTA_SUMMARY_PATH = RUNTIME_HOME / "data" / "llm_quota_summary.json"
LLM_COST_LOG_PATH = RUNTIME_HOME / "data" / "llm_cost.jsonl"

# Ensure both runtime/src and omo/src are on sys.path for imports
_runtime_src = str(PROJECT_ROOT / "src")
_omo_src = str(OMO_ROOT / "src")
for p in [_runtime_src, _omo_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

# L4 bridge imports (try/except for graceful degradation)
try:
    from cockpit.scripts.cockpit_mcp import cards_check, cards_status, workspace_context

    _HAS_L4_BRIDGE = True
except ImportError:
    _HAS_L4_BRIDGE = False

PORT = int(os.environ.get("COCKPIT_DASHBOARD_PORT", "8090"))
DASHBOARD_TOKEN = os.environ.get("COCKPIT_DASHBOARD_TOKEN", "")
DASHBOARD_CORS_ORIGIN = os.environ.get("COCKPIT_DASHBOARD_CORS_ORIGIN", "http://localhost:8090")
DASHBOARD_RATE_LIMIT = int(os.environ.get("COCKPIT_DASHBOARD_RATE_LIMIT", "60"))


# ═══════════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="Cockpit Dashboard", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DASHBOARD_CORS_ORIGIN],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)


# ─── 统一认证 (OPT-UNIFIED-AUTH) ──────────────────────────────
from cockpit.web.auth import get_subservice_token, verify_api_key


async def _auth_dependency(request: Request) -> None:
    from fastapi import HTTPException

    try:
        verify_api_key(dict(request.headers))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


try:
    from fastapi import Depends, Request

    _AUTH_DEPS = [Depends(_auth_dependency)]
except ImportError:
    _AUTH_DEPS = []

if HERMES_CONSOLE_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/hermes", StaticFiles(directory=str(HERMES_CONSOLE_DIST), html=True), name="hermes_console")

# ─── P46 治理面板 mount (P45 W3 known issue 升级真修) ─────────────────────
# 通用 router 注册: 加新面板 router 只需在 tuple 里加 module 路径.
# graceful degradation — fastapi/router import 失败时跳过该 router (不阻断 app 启动).
for _router_module in (
    "cockpit.web.governance.api",
    "cockpit.web.api_omos",
    "cockpit.web.api_ecos",
):
    try:
        _mod = importlib.import_module(_router_module)
        _router = getattr(_mod, "router", None)
        if _router is not None:
            app.include_router(_router, dependencies=_AUTH_DEPS)
    except Exception:
        pass

# ─── 健康检查 ──────────────────────────────────────────────────


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "cockpit-dashboard", "port": PORT}


# ═══════════════════════════════════════════════════════════════
# 层聚合 API
# ═══════════════════════════════════════════════════════════════

_LAYER_SOURCES: list[dict] = [
    {"layer": "I0", "name": "agora", "url": "http://localhost:8080/v1/health", "port": 8080},
    {"layer": "L2", "name": "omo", "url": "http://localhost:9190/api/v1/status", "port": 9190},
    {"layer": "L1", "name": "runtime", "url": "http://localhost:9876/api/v1/status", "port": 9876},
    {"layer": "L0", "name": "ecos", "url": "file://m0_snapshot", "port": None, "source": "m0_snapshot"},
]


def _fetch_layer_status(source: dict) -> dict:
    """Fetch a single layer's status — try direct import first, then HTTP."""

    # I0 Agora — always HTTP (separate process)
    if source["layer"] == "I0":
        return _fetch_http(source)

    # L2 omo — try direct import
    if source["layer"] == "L2":
        try:
            from omo.omo_dashboard import _load_json as _omo_load

            omo_dir = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))
            system = _omo_load(omo_dir / "state" / "system.yaml")
            return {
                "layer": "L2",
                "name": "omo",
                "status": "ok",
                "data": {"system": system, "source": "direct_import"},
            }
        except Exception:
            return _fetch_http(source)

    # L1 runtime — try direct import
    if source["layer"] == "L1":
        try:
            from runtime.i0 import i0_status

            status = i0_status() if i0_status else {}
            return {
                "layer": "L1",
                "name": "runtime",
                "status": "ok",
                "data": {"summary": {"total_layers": 3, "healthy": 1}, "status": status, "source": "direct_import"},
            }
        except Exception:
            return _fetch_http(source)

    # L0 ecos — read from M0 snapshot file
    if source["layer"] == "L0":
        return _read_m0_snapshot()
    return _fetch_http(source)


def _read_m0_snapshot() -> dict:
    """Read the M0 runtime snapshot from the local YAML file."""
    try:
        m0_path = M0_SNAPSHOT_PATH
        if not m0_path.exists():
            return {
                "layer": "L0",
                "name": "ecos",
                "status": "down",
                "error": f"M0 snapshot not found at {m0_path}",
            }
        raw = yaml.safe_load(m0_path.read_text(encoding="utf-8"))
        return {
            "layer": "L0",
            "name": "ecos",
            "status": "ok",
            "data": {
                "source": "m0_snapshot",
                "snapshot": {
                    "version": raw.get("version"),
                    "generated_at": str(raw.get("generated_at", "")),
                    "daemon": raw.get("daemon", {}),
                    "m1_node_count": raw.get("m1_node_count", 0),
                    "protocols": raw.get("protocols", {}),
                },
            },
        }
    except Exception as e:
        return {
            "layer": "L0",
            "name": "ecos",
            "status": "down",
            "error": f"M0 snapshot read error: {e}",
        }


def _fetch_http(source: dict) -> dict:
    """Fetch a layer's status via HTTP."""
    import urllib.request

    try:
        token = get_subservice_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-Api-Key"] = token
        req = urllib.request.Request(source["url"], method="GET", headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return {
            "layer": source["layer"],
            "name": source["name"],
            "status": data.get("status", "ok"),
            "data": data,
        }
    except Exception as e:
        return {
            "layer": source["layer"],
            "name": source["name"],
            "status": "down",
            "error": str(e),
        }


@app.get("/api/v1/status", dependencies=_AUTH_DEPS)
async def api_v1_status():
    """Aggregated status from all layers."""
    import concurrent.futures

    layers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_layer_status, s): s for s in _LAYER_SOURCES}
        for future in concurrent.futures.as_completed(futures, timeout=5):
            try:
                layers.append(future.result())
            except Exception as e:
                source = futures[future]
                layers.append(
                    {
                        "layer": source["layer"],
                        "name": source["name"],
                        "status": "down",
                        "error": str(e),
                    }
                )

    # Sort by layer name for consistent output
    layers.sort(key=lambda x: x["layer"])

    # Compute overall health
    total = len(layers)
    ok = sum(1 for layer in layers if layer["status"] == "ok")
    degraded = sum(1 for layer in layers if layer["status"] == "degraded")

    return JSONResponse(
        {
            "service": "cockpit-dashboard",
            "version": "2.0.0",
            "timestamp": time.time(),
            "layers": layers,
            "summary": {
                "total_layers": total,
                "healthy": ok,
                "degraded": degraded,
                "down": total - ok - degraded,
            },
            "sources": [
                {"layer": s["layer"], "name": s["name"], "url": s["url"], "port": s["port"]} for s in _LAYER_SOURCES
            ],
        }
    )


@app.get("/api/v1/m0", dependencies=_AUTH_DEPS)
async def api_v1_m0():
    """Return M0 runtime snapshot as JSON."""
    try:
        if not M0_SNAPSHOT_PATH.exists():
            return JSONResponse(
                {"error": f"M0 snapshot not found at {M0_SNAPSHOT_PATH}"},
                status_code=404,
            )
        raw = yaml.safe_load(M0_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return JSONResponse(raw)
    except Exception as e:
        return JSONResponse(
            {"error": f"M0 snapshot read error: {e}"},
            status_code=500,
        )


# ═══════════════════════════════════════════════════════════════
# 统一概览页面
# ═══════════════════════════════════════════════════════════════

_OVERVIEW_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cockpit — 统一状态概览</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9;padding:24px}
h1{color:#58a6ff;font-size:20px;margin-bottom:4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.layer-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.layer-card h2{font-size:14px;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.badge-ok{background:#052e16;color:#4ade80}.badge-degraded{background:#271c00;color:#fbbf24}.badge-down{background:#3b0d0d;color:#f87171}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot-ok{background:#4ade80}.dot-degraded{background:#fbbf24}.dot-down{background:#f87171}
.stat{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid #21262d}
.stat:last-child{border:none}.label{color:#8b949e}.val{color:#58a6ff;font-weight:600}
a{color:#58a6ff;text-decoration:none}a:hover{text-decoration:underline}
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav a{padding:6px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;font-size:12px}
.nav a:hover{background:#1c2333;border-color:#58a6ff}
.legacy-link{font-size:12px;color:#8b949e;margin-top:16px;text-align:center}
</style>
</head>
<body>
<h1>&#x25C8; Cockpit — 统一状态概览</h1>
<div class="sub">L3 聚合入口 · 自动检测各层状态</div>
<div class="nav">
  <a href="/">&#x1F4CA; 债务驾驶舱 (原有)</a>
  <a href="/hermes/">&#x2728; Hermes Console</a>
  <a href="/api/v1/status">&#x1F4CB; API JSON</a>
  <a href="/api/v1/m0">&#x1F4CA; M0 快照</a>
  <a href="http://localhost:7430">&#x2197; Agora (I0)</a>
  <a href="http://localhost:9090">&#x2197; OMO (L2)</a>
  <a href="http://localhost:9876">&#x2197; Runtime (L1)</a>
</div>
<div class="grid" id="layer-grid">
  <div style="color:#8b949e;grid-column:1/-1;text-align:center;padding:40px">Loading...</div>
</div>
<div class="legacy-link">
  <span id="refresh-time"></span>
</div>
<script>
async function refresh(){try{
const r=await fetch('/api/v1/status');const d=await r.json();
let html='';
d.layers.forEach(l=>{
  const badgeCls=l.status==='ok'?'badge-ok':l.status==='degraded'?'badge-degraded':'badge-down';
  const dotCls='dot-'+l.status;
  let body='';
  if(l.data){
    if(l.data.router)body+='<div class="stat"><span class="label">路由</span><span class="val">'+l.data.router.total_routes+'</span></div>';
    if(l.data.domains)body+='<div class="stat"><span class="label">域</span><span class="val">'+Object.keys(l.data.domains).length+'</span></div>';
    if(l.data.metrics)body+='<div class="stat"><span class="label">调用</span><span class="val">'+l.data.metrics.total_calls+'</span></div>';
    if(l.data.poc_services)body+='<div class="stat"><span class="label">POC</span><span class="val">'+l.data.poc_services.total+'</span></div>';
    if(l.data.summary){
      const s=l.data.summary;
      body+='<div class="stat"><span class="label">健康</span><span class="val">'+s.healthy+'/'+s.total_layers+'</span></div>';
    }
    // L0 M0 snapshot protocol health
    if(l.data.snapshot){
      const snap=l.data.snapshot;
      body+='<div class="stat"><span class="label">Daemon</span><span class="val">'+(snap.daemon.healthy?'\u2705 \u5065\u5eb7':'\u274c \u5f02\u5e38')+'</span></div>';
      body+='<div class="stat"><span class="label">M1 \u8282\u70b9</span><span class="val">'+snap.m1_node_count+'</span></div>';
      body+='<div class="stat"><span class="label">\u5feb\u7167\u7248\u672c</span><span class="val">'+(snap.version||'N/A')+'</span></div>';
      body+='<div style="margin-top:8px;font-size:11px;color:#8b949e">\u534f\u8bae\u8870\u51cf</div>';
      for(const [pname, p] of Object.entries(snap.protocols||{})){
        const pct=p.remaining_pct;
        const decay=p.decay;
        const age=p.age_days;
        const status=p.status;
        const barColor=pct>80?'#4ade80':pct>50?'#fbbf24':'#f87171';
        const statusBadgeCls=status==='fresh'?'badge-ok':status==='aging'?'badge-degraded':'badge-down';
        body+='<div style="margin:6px 0;padding:6px 8px;background:#0d1117;border:1px solid #21262d;border-radius:4px">'+
          '<div style="display:flex;justify-content:space-between;margin-bottom:4px">'+
          '<span style="font-weight:600;font-size:11px">'+pname+'</span>'+
          '<span class="badge '+statusBadgeCls+'">'+status+'</span>'+
          '</div>'+
          '<div style="display:flex;justify-content:space-between;font-size:10px;color:#8b949e;margin-bottom:3px">'+
          '<span>\u8870\u51cf: '+(decay*100).toFixed(0)+'%</span>'+
          '<span>\u5269\u4f59: '+pct+'%</span>'+
          '<span>\u5df2\u8fc7: '+age+'\u5929</span>'+
          '</div>'+
          '<div style="background:#21262d;border-radius:4px;height:8px;overflow:hidden">'+
          '<div style="height:100%;width:'+pct+'%;background:'+barColor+';border-radius:4px;transition:width 0.5s"></div>'+
          '</div>'+
          '</div>';
      }
    }
  }
  if(l.error)body+='<div class="stat"><span class="label">错误</span><span style="color:#f87171;font-size:11px">'+l.error.slice(0,60)+'</span></div>';
  if(!body)body='<div class="stat"><span class="label">无数据</span></div>';
  html+='<div class="layer-card"><h2><span class="status-dot '+dotCls+'"></span> '+l.layer+' '+l.name+' <span class="badge '+badgeCls+'">'+l.status+'</span></h2>'+body+'</div>';
});
document.getElementById('layer-grid').innerHTML=html;
document.getElementById('refresh-time').textContent='Updated '+new Date().toLocaleTimeString();
}catch(e){console.error(e);}}
refresh();setInterval(refresh,10000);
</script>
</body></html>"""


@app.get("/overview", response_class=HTMLResponse)
@app.get("/overview/", response_class=HTMLResponse)
async def overview_page():
    return _OVERVIEW_HTML


# ═══════════════════════════════════════════════════════════════
# 原有 Dashboard (向后兼容)
# ═══════════════════════════════════════════════════════════════

# 注入 JS 片段 (从原 dashboard_server.py 迁移)
_LIVE_DATA_JS = r"""
<script>
const STATIC_DEBTS = typeof DEBTS !== 'undefined' ? DEBTS : [];
const STATIC_TIERS = typeof TIERS !== 'undefined' ? TIERS : [];
const STATIC_POLICIES = typeof POLICIES !== 'undefined' ? POLICIES : [];
const STATIC_RULES = typeof RULES !== 'undefined' ? RULES : [];
const STATIC_TIER_COUNTS = typeof TIER_COUNTS !== 'undefined' ? TIER_COUNTS : {};
const STATIC_POLICY_COUNTS = typeof POLICY_COUNTS !== 'undefined' ? POLICY_COUNTS : {};
const STATIC_RULE_COUNTS = typeof RULE_COUNTS !== 'undefined' ? RULE_COUNTS : {};
const STATIC_SEV_COLORS = typeof SEV_COLORS !== 'undefined' ? SEV_COLORS : {};

async function loadLiveDebt() {
  try {
    const resp = await fetch('/api/debt');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const ledger = await resp.json();
    if (ledger.error) { console.warn('Debt API error:', ledger.error); return; }
    const items = ledger.items || [];
    const tierCounts = {}; const policyCounts = {}; const ruleCounts = {};
    STATIC_TIERS.forEach(t => { tierCounts[t.id] = { count: 0, color: t.color }; });
    STATIC_POLICIES.forEach(p => { policyCounts[p.id] = { ...p, count: 0 }; });
    STATIC_RULES.forEach(r => { ruleCounts[r.id] = { ...r, count: 0 }; });
    items.forEach(d => {
      const tier = d.x3 || d.x3_tier;
      if (tier && tierCounts[tier]) tierCounts[tier].count++;
      const refs = Array.isArray(d.x1) ? d.x1 : (d.x1_policy_refs || []);
      refs.forEach(p => { if (policyCounts[p]) policyCounts[p].count++; });
      (d.x2 || []).forEach(r => { if (ruleCounts[r]) ruleCounts[r].count++; });
    });
    window.DEBTS = items;
    window.TIER_COUNTS = tierCounts;
    window.POLICY_COUNTS = policyCounts;
    window.RULE_COUNTS = ruleCounts;
    renderTierChart(); renderPolicyGrid(); renderX2Grid(); populateFilters(); renderTable(items);
  } catch(e) { console.warn('Live debt unavailable:', e); }
}

async function loadLiveStatus() {
  try {
    const [status, services] = await Promise.all([
      fetch('/api/status').then(r => r.ok ? r.json() : null),
      fetch('/api/services').then(r => r.ok ? r.json() : null)
    ]);
    if (status) {
      const meta = document.querySelector('.header .meta');
      if (meta) {
        const el = document.querySelector('.header .meta span:first-child');
        if (el) el.textContent = '\uD83D\uDCE6 ' + (status.total_services || '?') + ' services';
      }
    }
    const card = document.querySelector('.card-stat:first-child .value');
    if (card && services) {
      const online = services.filter(s => s.port_listening).length;
      card.textContent = online + '/' + services.length;
      card.style.color = online === services.length ? '#4ade80' : '#fbbf24';
    }
  } catch(e) { console.log('Status unavailable:', e); }
}
loadLiveDebt(); loadLiveStatus();
setInterval(loadLiveStatus, 30000);
setInterval(loadLiveDebt, 60000);
</script>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    """Serve the existing dashboard.html with live-data JS injected."""
    if not DASHBOARD_HTML.exists():
        html = f"""<!DOCTYPE html><html><body><h1>Dashboard not found</h1>
<p>Expected at: {DASHBOARD_HTML}</p>
<p>Try <a href="/overview">/overview</a> for unified status.</p></body></html>"""
        return HTMLResponse(content=html, status_code=404)

    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    html = html.replace("</body>", _LIVE_DATA_JS + "\n</body>")
    return HTMLResponse(content=html)


# ═══════════════════════════════════════════════════════════════
# 原有 API (向后兼容)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/status", dependencies=_AUTH_DEPS)
async def api_status():
    try:
        from runtime.i0 import i0_status

        return JSONResponse(content=(i0_status() if i0_status else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/services", dependencies=_AUTH_DEPS)
async def api_services():
    try:
        from runtime.i0 import i0_services

        return JSONResponse(content=(i0_services() if i0_services else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/events", dependencies=_AUTH_DEPS)
async def api_events():
    try:
        from runtime.i0 import i0_events

        return JSONResponse(content=(i0_events(50) if i0_events else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/protocols", dependencies=_AUTH_DEPS)
async def api_protocols():
    try:
        from runtime.i0 import i0_protocols

        return JSONResponse(content=(i0_protocols() if i0_protocols else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/debt", dependencies=_AUTH_DEPS)
async def api_debt():
    return JSONResponse(content=_load_debt())


@app.get("/api/compute", dependencies=_AUTH_DEPS)
async def api_compute():
    return JSONResponse(content=_load_compute())


@app.get("/api/e2e", dependencies=_AUTH_DEPS)
async def api_e2e():
    return JSONResponse(content=_run_e2e())


@app.get("/api/omo-report", dependencies=_AUTH_DEPS)
async def api_omo_report():
    return JSONResponse(content=_omo_report())


@app.get("/api/context", dependencies=_AUTH_DEPS)
async def api_context():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(workspace_context()))


@app.get("/api/cards", dependencies=_AUTH_DEPS)
async def api_cards():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_status()))


@app.get("/api/cards/check", dependencies=_AUTH_DEPS)
async def api_cards_check():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_check()))


# ═══════════════════════════════════════════════════════════════
# 债务加载 / E2E / OMO 报告 (从原 dashboard_server.py 迁移)
# ═══════════════════════════════════════════════════════════════

_DEFAULT_COMPUTE_TOPOLOGY = [
    {"id": "local-mac", "label": "Local-Mac", "kind": "local", "role": "Cockpit / Agent host"},
    {"id": "macmini-ollama", "label": "MacMini (Ollama)", "kind": "local", "role": "Local inference"},
    {"id": "y7000p-lmstudio", "label": "Y7000P (LMStudio)", "kind": "local", "role": "GPU workstation"},
    {"id": "cloud-cc-switch", "label": "Cloud (cc-switch)", "kind": "cloud", "role": "Remote provider relay"},
]


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    model_lower = (model or "unknown").lower()
    cost_map = {
        "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
        "gpt-4o": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "deepseek-v4-flash": {"input": 0.0005, "output": 0.002},
        "deepseek-v4": {"input": 0.002, "output": 0.008},
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
        "ollama": {"input": 0.0, "output": 0.0},
        "lmstudio": {"input": 0.0, "output": 0.0},
        "mock-model": {"input": 0.0, "output": 0.0},
    }
    rates = None
    for key in sorted(cost_map, key=len, reverse=True):
        if model_lower.startswith(key):
            rates = cost_map[key]
            break
    if rates is None:
        rates = {"input": 0.002, "output": 0.008}
    return round((input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"], 6)


def _infer_node(model: str, provider_name: str | None) -> dict[str, str]:
    model_lower = (model or "").lower()
    provider_lower = (provider_name or "").lower()
    if "ollama" in model_lower:
        return {"node_id": "macmini-ollama", "node_label": "MacMini (Ollama)", "route_type": "local"}
    if "lmstudio" in model_lower:
        return {"node_id": "y7000p-lmstudio", "node_label": "Y7000P (LMStudio)", "route_type": "local"}
    if any(key in model_lower for key in ("gpt", "claude", "deepseek", "gemini")) or "deepseek" in provider_lower:
        return {"node_id": "cloud-cc-switch", "node_label": "Cloud (cc-switch)", "route_type": "cloud"}
    return {"node_id": "local-mac", "node_label": "Local-Mac", "route_type": "local"}


def _load_compute() -> dict:
    quota_summary = _read_json_file(LLM_QUOTA_SUMMARY_PATH)
    provider_plane = {}
    if PROVIDER_PLANE_PATH.exists():
        provider_plane = yaml.safe_load(PROVIDER_PLANE_PATH.read_text(encoding="utf-8")) or {}

    selected_provider = provider_plane.get("selected_provider") or {}
    provider_name = selected_provider.get("name")
    selected_cloud_model = selected_provider.get("model") or "gpt-4o"

    records = []
    if LLM_COST_LOG_PATH.exists():
        for line in LLM_COST_LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = entry.get("model", "unknown")
            input_tokens = int(entry.get("input_tokens", 0) or 0)
            output_tokens = int(entry.get("output_tokens", 0) or 0)
            raw_ts = entry.get("timestamp") or entry.get("ts")
            ts = _parse_timestamp(raw_ts)
            provider_hint = entry.get("provider") or provider_name or "unknown"
            inferred_node = _infer_node(model, provider_hint)
            latency_ms = entry.get("latency_ms")
            tokens_per_second = entry.get("tokens_per_second")
            estimated_cost = float(
                entry.get("estimated_cost_usd")
                or entry.get("cost")
                or _estimate_cost(model, input_tokens, output_tokens)
            )
            total_tokens = input_tokens + output_tokens
            route_type = entry.get("route_type") or inferred_node["route_type"]
            equivalent_cloud_cost = _estimate_cost(selected_cloud_model, input_tokens, output_tokens)
            records.append(
                {
                    "timestamp": ts.isoformat() if ts else raw_ts,
                    "model": model,
                    "provider_hint": provider_hint,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": round(estimated_cost, 6),
                    "equivalent_cloud_cost_usd": round(equivalent_cloud_cost, 6),
                    "saved_vs_cloud_usd": round(max(equivalent_cloud_cost - estimated_cost, 0.0), 6),
                    "latency_ms": float(latency_ms) if latency_ms is not None else None,
                    "tokens_per_second": float(tokens_per_second) if tokens_per_second is not None else None,
                    "node_id": entry.get("node_id") or inferred_node["node_id"],
                    "node_label": entry.get("node_label") or inferred_node["node_label"],
                    "route_type": route_type,
                }
            )

    records.sort(key=lambda item: item.get("timestamp") or "", reverse=True)

    latest_request_at = records[0].get("timestamp") if records else None
    earliest_request_at = records[-1].get("timestamp") if records else None
    latest_dt = _parse_timestamp(latest_request_at)
    earliest_dt = _parse_timestamp(earliest_request_at)
    span_hours = None
    if latest_dt and earliest_dt:
        span_hours = round((latest_dt - earliest_dt).total_seconds() / 3600, 2)

    traffic_by_node: dict[str, dict] = {}
    for record in records:
        bucket = traffic_by_node.setdefault(
            record["node_id"],
            {
                "node_id": record["node_id"],
                "node_label": record["node_label"],
                "route_type": record["route_type"],
                "calls": 0,
                "tokens": 0,
                "estimated_cost_usd": 0.0,
                "equivalent_cloud_cost_usd": 0.0,
                "saved_vs_cloud_usd": 0.0,
                "latency_samples": 0,
                "latency_ms_avg": None,
                "tokens_per_second_avg": None,
                "_latency_total": 0.0,
                "_throughput_total": 0.0,
                "_throughput_samples": 0,
            },
        )
        bucket["calls"] += 1
        bucket["tokens"] += record["total_tokens"]
        bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"] + record["estimated_cost_usd"], 6)
        bucket["equivalent_cloud_cost_usd"] = round(
            bucket["equivalent_cloud_cost_usd"] + record["equivalent_cloud_cost_usd"], 6
        )
        bucket["saved_vs_cloud_usd"] = round(bucket["saved_vs_cloud_usd"] + record["saved_vs_cloud_usd"], 6)
        if record["latency_ms"] is not None:
            bucket["latency_samples"] += 1
            bucket["_latency_total"] += record["latency_ms"]
        if record["tokens_per_second"] is not None:
            bucket["_throughput_samples"] += 1
            bucket["_throughput_total"] += record["tokens_per_second"]

    for bucket in traffic_by_node.values():
        if bucket["latency_samples"]:
            bucket["latency_ms_avg"] = round(bucket["_latency_total"] / bucket["latency_samples"], 3)
        if bucket["_throughput_samples"]:
            bucket["tokens_per_second_avg"] = round(bucket["_throughput_total"] / bucket["_throughput_samples"], 3)
        del bucket["_latency_total"]
        del bucket["_throughput_total"]
        del bucket["_throughput_samples"]

    topology = []
    active_node_ids = set(traffic_by_node)
    selected_node_id = _infer_node(selected_provider.get("model", ""), provider_name).get("node_id")
    for node in _DEFAULT_COMPUTE_TOPOLOGY:
        topology.append(
            {
                **node,
                "active": node["id"] in active_node_ids,
                "selected_provider_route": node["id"] == selected_node_id,
            }
        )

    quota_providers = []
    for provider_id, details in (provider_plane.get("quota_summary", {}).get("providers", {}) or {}).items():
        quota_providers.append(
            {
                "provider_id": provider_id,
                "available": bool(details.get("available", False)),
                "summary": details.get("summary"),
                "balance": details.get("balance"),
                "remaining": details.get("remaining"),
                "used_percent": details.get("used_percent"),
            }
        )

    latency_values = [item["latency_ms"] for item in records if item["latency_ms"] is not None]
    throughput_values = [item["tokens_per_second"] for item in records if item["tokens_per_second"] is not None]
    total_calls = len(records)
    local_records = [item for item in records if item["route_type"] != "cloud"]
    cloud_records = [item for item in records if item["route_type"] == "cloud"]
    intercepted_calls = len(local_records)
    intercepted_tokens = sum(item["total_tokens"] for item in local_records)
    actual_local_cost = round(sum(item["estimated_cost_usd"] for item in local_records), 6)
    actual_cloud_cost = round(sum(item["estimated_cost_usd"] for item in cloud_records), 6)
    cloud_equivalent_cost = round(sum(item["equivalent_cloud_cost_usd"] for item in records), 6)
    intercepted_equivalent_cloud_cost = round(sum(item["equivalent_cloud_cost_usd"] for item in local_records), 6)
    saved_vs_cloud = round(sum(item["saved_vs_cloud_usd"] for item in local_records), 6)
    codex_provider = (provider_plane.get("quota_summary", {}).get("providers", {}) or {}).get("codex", {})

    return {
        "summary": {
            "generated_at": quota_summary.get("generated_at"),
            "entry_count": quota_summary.get("entry_count", len(records)),
            "total_calls": total_calls,
            "recent_calls": len(records[:10]),
            "total_input_tokens": sum(item["input_tokens"] for item in records),
            "total_output_tokens": sum(item["output_tokens"] for item in records),
            "total_estimated_cost_usd": round(
                quota_summary.get("total_estimated_cost_usd", sum(item["estimated_cost_usd"] for item in records)),
                6,
            ),
            "remaining_ratio": quota_summary.get("remaining_ratio"),
            "remaining_budget_usd": quota_summary.get("remaining_budget_usd"),
            "effective_remaining_budget_usd": quota_summary.get("effective_remaining_budget_usd"),
            "quota_low": bool(quota_summary.get("quota_low", False)),
            "latest_request_at": latest_request_at,
            "earliest_request_at": earliest_request_at,
            "time_span_hours": span_hours,
            "avg_latency_ms": round(sum(latency_values) / len(latency_values), 3) if latency_values else None,
            "avg_tokens_per_second": round(sum(throughput_values) / len(throughput_values), 3)
            if throughput_values
            else None,
        },
        "provider": {
            "name": selected_provider.get("name"),
            "model": selected_provider.get("model"),
            "base_url": selected_provider.get("base_url"),
            "source": selected_provider.get("source"),
            "is_healthy": selected_provider.get("is_healthy"),
            "quota_provider_count": provider_plane.get("quota_summary", {}).get("provider_count", 0),
            "quota_providers": quota_providers,
        },
        "topology": topology,
        "traffic_by_node": sorted(traffic_by_node.values(), key=lambda item: item["calls"], reverse=True),
        "recent_traffic": records[:10],
        "cost_board": {
            "selected_cloud_model": selected_cloud_model,
            "intercepted_calls": intercepted_calls,
            "intercepted_tokens": intercepted_tokens,
            "interception_rate": round(intercepted_calls / total_calls, 4) if total_calls else 0.0,
            "actual_cloud_cost_usd": actual_cloud_cost,
            "actual_local_cost_usd": actual_local_cost,
            "actual_total_cost_usd": round(actual_cloud_cost + actual_local_cost, 6),
            "cloud_equivalent_cost_usd": cloud_equivalent_cost,
            "intercepted_equivalent_cloud_cost_usd": intercepted_equivalent_cloud_cost,
            "saved_vs_cloud_usd": saved_vs_cloud,
            "codex_remaining_credits": codex_provider.get("remaining"),
            "codex_secondary_used_percent": codex_provider.get("used_percent"),
            "codex_available": bool(codex_provider.get("available", False)),
            "codex_summary": codex_provider.get("summary"),
        },
        "observations": {
            "cross_day": bool(latest_dt and earliest_dt and latest_dt.date() != earliest_dt.date()),
            "cross_week": bool(
                latest_dt and earliest_dt and latest_dt.isocalendar()[:2] != earliest_dt.isocalendar()[:2]
            ),
            "cross_model": len({item["model"] for item in records}) > 1,
            "latency_available": bool(latency_values),
            "throughput_mode": "trace" if throughput_values else "token-aggregate",
        },
    }


def _load_debt() -> dict:
    """Load OMO debt ledger from the filesystem and return a JSON-safe dict."""
    try:
        from omo.omo_debt_registry import load_debt_ledger

        omo_dir = OMO_ROOT / ".omo"
        if not omo_dir.exists():
            return {"error": f"OMO directory not found at {omo_dir}", "items": []}

        ledger = load_debt_ledger(omo_dir)

        items = []
        for i in ledger.items:
            items.append(
                {
                    "id": i.id,
                    "title": i.title,
                    "dimension": i.dimension,
                    "subdimension": i.subdimension,
                    "domain": i.domain,
                    "scope": i.scope,
                    "severity": i.severity,
                    "weight": i.weight,
                    "entropy_class": i.entropy_class,
                    "lifecycle_state": i.lifecycle_state,
                    "owner": i.owner,
                    "affected_roots": list(i.affected_roots),
                    "evidence_refs": list(i.evidence_refs),
                    "mitigation_refs": list(i.mitigation_refs),
                    "opened_at": i.opened_at,
                    "last_reviewed_at": i.last_reviewed_at,
                    "next_review_at": i.next_review_at,
                    "gate_level": i.gate_level,
                    "history": list(i.history),
                    "x1_policy_refs": [i.x1_policy_ref] if i.x1_policy_ref else [],
                    "x1_policy_ref": i.x1_policy_ref,
                    "x1": [i.x1_policy_ref] if i.x1_policy_ref else [],
                    "x2_freshness": i.x2_freshness,
                    "x2": [],
                    "x3_tier": i.x3_tier,
                    "x3": i.x3_tier,
                }
            )

        return {
            "total": len(items),
            "open": sum(1 for i in ledger.items if i.lifecycle_state != "closed"),
            "closed": sum(1 for i in ledger.items if i.lifecycle_state == "closed"),
            "items": items,
        }
    except ImportError as e:
        return {"error": f"Import error: {e}", "items": []}
    except Exception as e:
        return {"error": str(e), "items": []}


def _run_e2e() -> dict:
    """Run the e2e check and return results."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "runtime.e2e"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        stdout = result.stdout
        m = re.search(r"Result:\s*(\d+)/(\d+)\s*checks\s*passed", stdout)
        if m:
            return {"result": f"{m.group(1)}/{m.group(2)} passed", "output": stdout}
        return {"result": "unparsed", "output": stdout}
    except subprocess.TimeoutExpired:
        return {"result": "timeout", "error": "E2E took >30s"}
    except Exception as e:
        return {"result": "error", "error": str(e)}


def _omo_report() -> dict:
    """Generate OMO summary report."""
    try:
        omo_dir = OMO_ROOT / ".omo"
        items_dir = omo_dir / "debt" / "items"
        files = sorted(items_dir.glob("*.yaml")) if items_dir.exists() else []
        items = []
        for f in files:
            import yaml

            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            items.append(d)
        open_count = sum(1 for i in items if i.get("lifecycle_state") not in ("closed", "resolved"))
        closed_count = sum(1 for i in items if i.get("lifecycle_state") in ("closed", "resolved"))
        return {
            "summary": f"{len(items)} items, {open_count} open, {closed_count} closed",
            "total": len(items),
            "open": open_count,
            "closed": closed_count,
        }
    except Exception as e:
        return {"error": str(e), "summary": "Error"}


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


def main():
    """Start the dashboard HTTP server via uvicorn."""
    import uvicorn

    print("🚀 Cockpit Web Dashboard (FastAPI)")
    print(f"   Overview: http://127.0.0.1:{PORT}/overview")
    print(f"   Legacy:   http://127.0.0.1:{PORT}/ (原有债务驾驶舱)")
    print(f"   API:      http://127.0.0.1:{PORT}/api/v1/status")
    if _HAS_L4_BRIDGE:
        print(f"   L4 Cards: http://127.0.0.1:{PORT}/api/cards")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
