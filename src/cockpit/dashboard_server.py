"""Cockpit Web Dashboard — FastAPI unified status aggregation hub (L3).

Entry point for `cockpit dashboard`. Routes and helpers live in
cockpit.dashboard.{routes,helpers,constants}.

Usage:
    cockpit dashboard
    # or
    python3 -m cockpit.dashboard_server
"""

from __future__ import annotations

import importlib
import sys
import traceback

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from cockpit.dashboard.constants import (
    COCKPIT_UI_DIST,
    DASHBOARD_CORS_ORIGIN,
    PORT,
)
from cockpit.dashboard.routes import _auth_dependency as _auth_dep
from cockpit.dashboard.routes import router as dashboard_router

# ─── FastAPI App ───────────────────────────────────────────────

app = FastAPI(title="Cockpit Dashboard", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DASHBOARD_CORS_ORIGIN],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)

# ─── Auth dep for external router imports ─────────────────────

try:
    from fastapi import Depends

    _AUTH_DEPS = [Depends(_auth_dep)]
except ImportError:
    _AUTH_DEPS = []

# ─── Governance routers (graceful degradation) ────────────────

for _router_module in (
    "cockpit.web.governance.api",
    "cockpit.web.api_omos",
    "cockpit.web.api_ecos",
    "cockpit.web.api_knowledge",
    "cockpit.web.api_bos",
    "cockpit.web.api_proposals",
    "cockpit.web.api_metaos",
    "cockpit.web.api_agora",
    "cockpit.web.api_sandbox",
    "cockpit.web.api_l4",
    "cockpit.web.api_health",
    "cockpit.web.api_alerts",
    "cockpit.web.api_tasks",
    "cockpit.web.api_logs",
    "cockpit.web.api_metrics",
):
    try:
        _mod = importlib.import_module(_router_module)
        _router = getattr(_mod, "router", None)
        if _router is not None:
            app.include_router(_router, dependencies=_AUTH_DEPS)
            print(f"Successfully loaded router: {_router_module}")
    except Exception as e:
        print(f"Error loading router {_router_module}: {e}", file=sys.stderr)
        traceback.print_exc()

# ─── GBrain Proxy ─────────────────────────────────────────────


@app.api_route("/admin/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_gbrain_admin(path: str, request: Request):
    """Forward /admin requests to the GBrain service (with Streaming/SSE support)."""
    import os

    gbrain_port = int(os.environ.get("GBRAIN_PORT", "3131"))
    target_url = f"http://127.0.0.1:{gbrain_port}/admin/{path}"

    # Pass along query parameters
    params = dict(request.query_params)

    # Strip dangerous/unnecessary headers like host and accept-encoding to avoid handshake/decompression conflicts
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "accept-encoding")}

    # Read raw body
    body = await request.body()

    # Detect if this is an SSE / EventStream connection
    is_sse = "events" in path or "events" in request.url.path or request.headers.get("accept") == "text/event-stream"

    try:
        if is_sse:
            from fastapi.responses import StreamingResponse

            async def event_generator():
                async with httpx.AsyncClient(timeout=3600.0) as client:
                    req = client.build_request(
                        method=request.method,
                        url=target_url,
                        params=params,
                        headers=headers,
                        content=body,
                    )
                    resp = await client.send(req, stream=True)
                    try:
                        async for chunk in resp.aiter_raw():
                            yield chunk
                    finally:
                        await resp.aclose()

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    params=params,
                    headers=headers,
                    content=body,
                )
                # Remove connection/length headers to allow FastAPI to handle body streaming naturally
                excluded_headers = ["content-length", "transfer-encoding", "connection"]
                resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
                return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)
    except httpx.RequestError as e:
        return Response(content=f"Proxy error connecting to GBrain ({gbrain_port}): {str(e)}", status_code=502)


# ─── Main dashboard router ────────────────────────────────────

app.include_router(dashboard_router)

# ─── Static files (Cockpit UI) ────────────────────────────

if COCKPIT_UI_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(COCKPIT_UI_DIST), html=True), name="cockpit_ui")


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════


def main():
    import uvicorn

    uvicorn.run(
        "cockpit.dashboard_server:app",
        host="127.0.0.1",
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
