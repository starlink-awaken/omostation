"""API routes and page routes for the Cockpit Dashboard."""

from __future__ import annotations

import concurrent.futures
import json
import time

import yaml
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from cockpit.dashboard.constants import (
    BOS_DASHBOARD_HTML,
    DASHBOARD_HTML,
    LAYER_SOURCES,
    LIVE_DATA_JS,
    M0_SNAPSHOT_PATH,
    OVERVIEW_HTML,
    PORT,
)
from cockpit.dashboard.helpers import (
    fetch_layer_status,
    load_bos_metrics,
    load_compute,
    load_debt,
    omo_report,
    run_e2e,
)
from cockpit.web.auth import verify_api_key

# L4 bridge imports (try/except for graceful degradation)
try:
    from cockpit.scripts.cockpit_mcp import cards_check, cards_status, workspace_context

    _HAS_L4_BRIDGE = True
except ImportError:
    _HAS_L4_BRIDGE = False


# ─── Auth ─────────────────────────────────────────────────────


async def _auth_dependency(request: Request) -> None:
    from fastapi import HTTPException

    try:
        verify_api_key(dict(request.headers))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


try:
    _AUTH_DEPS = [Depends(_auth_dependency)]
except ImportError:
    _AUTH_DEPS = []


# ─── Router ───────────────────────────────────────────────────

router = APIRouter()


# ─── Health ────────────────────────────────────────────────────


@router.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "cockpit-dashboard", "port": PORT}


# ─── Layer aggregation API ────────────────────────────────────


@router.get("/api/v1/status", dependencies=_AUTH_DEPS)
async def api_v1_status():
    """Aggregated status from all layers."""
    layers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_layer_status, s): s for s in LAYER_SOURCES}
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

    layers.sort(key=lambda x: x["layer"])
    total = len(layers)
    ok = sum(1 for layer in layers if layer["status"] == "ok")
    degraded = sum(1 for layer in layers if layer["status"] == "degraded")

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
        "sources": [
            {"layer": s["layer"], "name": s["name"], "url": s["url"], "port": s["port"]}
            for s in LAYER_SOURCES
        ],
    })


@router.get("/api/v1/m0", dependencies=_AUTH_DEPS)
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
        return JSONResponse({"error": f"M0 snapshot read error: {e}"}, status_code=500)


# ─── Pages ─────────────────────────────────────────────────────


@router.get("/overview", response_class=HTMLResponse)
@router.get("/overview/", response_class=HTMLResponse)
async def overview_page():
    return OVERVIEW_HTML


@router.get("/", response_class=HTMLResponse)
async def dashboard_page():
    """Serve the existing dashboard.html with live-data JS injected."""
    if not DASHBOARD_HTML.exists():
        html = f"""<!DOCTYPE html><html><body><h1>Dashboard not found</h1>
<p>Expected at: {DASHBOARD_HTML}</p>
<p>Try <a href="/overview">/overview</a> for unified status.</p></body></html>"""
        return HTMLResponse(content=html, status_code=404)

    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    html = html.replace("</body>", LIVE_DATA_JS + "\n</body>")
    return HTMLResponse(content=html)


# ─── Legacy API (backward compatible) ─────────────────────────


@router.get("/api/status", dependencies=_AUTH_DEPS)
async def api_status():
    try:
        from runtime.i0 import i0_status

        return JSONResponse(content=(i0_status() if i0_status else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@router.get("/api/services", dependencies=_AUTH_DEPS)
async def api_services():
    try:
        from runtime.i0 import i0_services

        return JSONResponse(content=(i0_services() if i0_services else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@router.get("/api/events", dependencies=_AUTH_DEPS)
async def api_events():
    try:
        from runtime.i0 import i0_events

        return JSONResponse(content=(i0_events(50) if i0_events else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@router.get("/api/protocols", dependencies=_AUTH_DEPS)
async def api_protocols():
    try:
        from runtime.i0 import i0_protocols

        return JSONResponse(content=(i0_protocols() if i0_protocols else {"error": "runtime.i0 not available"}))
    except ImportError:
        return JSONResponse(content={"error": "runtime.i0 not available"})


@router.get("/api/debt", dependencies=_AUTH_DEPS)
async def api_debt():
    return JSONResponse(content=load_debt())


@router.get("/api/compute", dependencies=_AUTH_DEPS)
async def api_compute():
    return JSONResponse(content=load_compute())


@router.get("/api/e2e", dependencies=_AUTH_DEPS)
async def api_e2e():
    return JSONResponse(content=run_e2e())


@router.get("/api/omo-report", dependencies=_AUTH_DEPS)
async def api_omo_report():
    return JSONResponse(content=omo_report())


@router.get("/api/context", dependencies=_AUTH_DEPS)
async def api_context():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(workspace_context()))


@router.get("/api/cards", dependencies=_AUTH_DEPS)
async def api_cards():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_status()))


@router.get("/api/cards/check", dependencies=_AUTH_DEPS)
async def api_cards_check():
    if not _HAS_L4_BRIDGE:
        return JSONResponse(content={"error": "L4 bridge not available"})
    return JSONResponse(content=json.loads(cards_check()))


# ─── BOS 可观测 ────────────────────────────────────────────────


@router.get("/api/bos/metrics", dependencies=_AUTH_DEPS)
async def api_bos_metrics():
    """BOS 调用指标聚合 (JSONL → domain aggregation)."""
    return JSONResponse(content=load_bos_metrics())


@router.get("/bos", response_class=HTMLResponse)
@router.get("/bos/", response_class=HTMLResponse)
async def bos_dashboard():
    """BOS 调用可观测面板。"""
    return BOS_DASHBOARD_HTML
