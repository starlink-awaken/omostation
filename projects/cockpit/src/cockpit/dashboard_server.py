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

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# ─── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent  # cockpit/src/cockpit/
OMO_ROOT = Path.home() / "Workspace/projects/omo"
DASHBOARD_HTML = PROJECT_ROOT / "templates" / "dashboard.html"

# Ensure both runtime/src and omo/src are on sys.path for imports
_runtime_src = str(PROJECT_ROOT / "src")
_omo_src = str(OMO_ROOT / "src")
for p in [_runtime_src, _omo_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

# L4 bridge imports (try/except for graceful degradation)
try:
    from cockpit.scripts.cockpit_mcp import workspace_context, cards_status, cards_check, vault_search
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
    allow_headers=["Authorization", "Content-Type"],
)

# ─── 健康检查 ──────────────────────────────────────────────────


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "cockpit-dashboard", "port": PORT}


# ═══════════════════════════════════════════════════════════════
# 层聚合 API
# ═══════════════════════════════════════════════════════════════

_LAYER_SOURCES: list[dict] = [
    {"layer": "I0", "name": "agora", "url": "http://localhost:7430/api/bos/status", "port": 7430},
    {"layer": "L2", "name": "omo",   "url": "http://localhost:9090/api/v1/status",   "port": 9090},
    {"layer": "L1", "name": "runtime", "url": "http://localhost:9876/api/v1/status",  "port": 9876},
    {"layer": "L0", "name": "ecos",  "url": "http://localhost:9090/api/v1/status",   "port": 9090},
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
            omo_dir = Path(os.environ.get("OMO_DIR",
                            str(Path.home() / "Workspace" / ".omo")))
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
                "data": {"summary": {"total_layers": 3, "healthy": 1},
                         "status": status, "source": "direct_import"},
            }
        except Exception:
            return _fetch_http(source)

    # L0 ecos — HTTP fallback only
    return _fetch_http(source)


def _fetch_http(source: dict) -> dict:
    """Fetch a layer's status via HTTP."""
    import urllib.request
    try:
        req = urllib.request.Request(source["url"], method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
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


@app.get("/api/v1/status")
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
                layers.append({
                    "layer": source["layer"],
                    "name": source["name"],
                    "status": "down",
                    "error": str(e),
                })

    # Sort by layer name for consistent output
    layers.sort(key=lambda x: x["layer"])

    # Compute overall health
    total = len(layers)
    ok = sum(1 for l in layers if l["status"] == "ok")
    degraded = sum(1 for l in layers if l["status"] == "degraded")

    return JSONResponse({
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
        "sources": [{"layer": s["layer"], "name": s["name"], "url": s["url"], "port": s["port"]} for s in _LAYER_SOURCES],
    })


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
  <a href="/api/v1/status">&#x1F4CB; API JSON</a>
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
_LIVE_DATA_JS = r'''
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
</script>'''


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


@app.get("/api/status")
async def api_status():
    try:
        from runtime.i0 import i0_status
        return JSONResponse(content=(i0_status() if i0_status else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/services")
async def api_services():
    try:
        from runtime.i0 import i0_services
        return JSONResponse(content=(i0_services() if i0_services else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/events")
async def api_events():
    try:
        from runtime.i0 import i0_events
        return JSONResponse(content=(i0_events(50) if i0_events else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/protocols")
async def api_protocols():
    try:
        from runtime.i0 import i0_protocols
        return JSONResponse(content=(i0_protocols() if i0_protocols else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@app.get("/api/debt")
async def api_debt():
    return JSONResponse(content=_load_debt())


@app.get("/api/e2e")
async def api_e2e():
    return JSONResponse(content=_run_e2e())


@app.get("/api/omo-report")
async def api_omo_report():
    return JSONResponse(content=_omo_report())


@app.get("/api/context")
async def api_context():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(workspace_context()))


@app.get("/api/cards")
async def api_cards():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_status()))


@app.get("/api/cards/check")
async def api_cards_check():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_check()))


# ═══════════════════════════════════════════════════════════════
# 债务加载 / E2E / OMO 报告 (从原 dashboard_server.py 迁移)
# ═══════════════════════════════════════════════════════════════


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
            items.append({
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
            })

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
            capture_output=True, text=True, timeout=30,
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

    print(f"🚀 Cockpit Web Dashboard (FastAPI)")
    print(f"   Overview: http://127.0.0.1:{PORT}/overview")
    print(f"   Legacy:   http://127.0.0.1:{PORT}/ (原有债务驾驶舱)")
    print(f"   API:      http://127.0.0.1:{PORT}/api/v1/status")
    if _HAS_L4_BRIDGE:
        print(f"   L4 Cards: http://127.0.0.1:{PORT}/api/cards")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
