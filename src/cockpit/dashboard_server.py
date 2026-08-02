"""Cockpit Web Dashboard — FastAPI unified status aggregation hub (L3).

Entry point for `cockpit dashboard`. Routes and helpers live in
cockpit.dashboard.{routes,helpers,constants}.

Usage:
    cockpit dashboard
    # or
    python3 -m cockpit.dashboard_server
"""

from __future__ import annotations

import contextlib
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
from cockpit.web.router_health import ROUTER_LOAD_REPORT, ROUTER_MODULES, router_health_snapshot
from cockpit.web.versioning import register_app_routes, setup_version_middleware, version_manager

# ─── Lifespan (startup / shutdown hooks) ─────────────────────


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    """FastAPI lifespan — startup/shutdown 键 (ADR-0294)."""
    # ── startup ──
    try:
        from cockpit.web.knowledge_indexer import start_knowledge_indexer

        await start_knowledge_indexer()
    except Exception as e:
        print(f"Warning: KnowledgeIndexer startup error (non-fatal): {e}", file=sys.stderr)

    yield  # 应用运行期间

    # ── shutdown ──
    try:
        from cockpit.web.knowledge_indexer import stop_knowledge_indexer

        await stop_knowledge_indexer()
    except Exception as e:
        print(f"Warning: KnowledgeIndexer shutdown error: {e}", file=sys.stderr)


# ─── FastAPI App ───────────────────────────────────────────────

app = FastAPI(title="Cockpit Dashboard", version=version_manager.current_version, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DASHBOARD_CORS_ORIGIN],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)

# ─── API 版本管理设置 ─────────────────────────────────────────

setup_version_middleware(app)

# ─── Auth dep for external router imports ─────────────────────

try:
    from fastapi import Depends

    _AUTH_DEPS = [Depends(_auth_dep)]
except ImportError:
    _AUTH_DEPS = []

# ─── Governance routers (graceful degradation) ────────────────

for _router_module in ROUTER_MODULES:
    try:
        _mod = importlib.import_module(_router_module)
        _router = getattr(_mod, "router", None)
        if _router is not None:
            app.include_router(_router, dependencies=_AUTH_DEPS)
            route_count = len(getattr(_router, "routes", []) or [])
            if getattr(_mod, "ROUTER_DEGRADED", False):
                ROUTER_LOAD_REPORT.append(
                    {
                        "module": _router_module,
                        "status": "degraded",
                        "route_count": route_count,
                        "error_type": "OptionalDependencyUnavailable",
                        "error": str(getattr(_mod, "ROUTER_DEGRADED_REASON", "")),
                    }
                )
                print(f"Loaded degraded router: {_router_module}")
            else:
                ROUTER_LOAD_REPORT.append(
                    {"module": _router_module, "status": "loaded", "route_count": route_count}
                )
                print(f"Successfully loaded router: {_router_module}")
        else:
            ROUTER_LOAD_REPORT.append({"module": _router_module, "status": "missing_router", "route_count": 0})
    except Exception as e:  # defensive fallback
        ROUTER_LOAD_REPORT.append(
            {
                "module": _router_module,
                "status": "unavailable",
                "route_count": 0,
                "error_type": type(e).__name__,
                "error": str(e),
            }
        )
        print(f"Error loading router {_router_module}: {e}", file=sys.stderr)
        traceback.print_exc()

# ─── KOS Knowledge Integration (REST API proxy) ────────────────

try:
    from cockpit.kos_proxy import init_kos_routes

    init_kos_routes(app)
    print("Successfully loaded KOS proxy routes")
except Exception as e:
    print(f"Warning: KOS proxy not available: {e}", file=sys.stderr)

# ─── Brain API (Phase 48 MVP) ──────────────────────────────────

try:
    from cockpit.web.api_brain import router as brain_router

    app.include_router(brain_router)
    print("Successfully loaded Brain API routes")
except Exception as e:
    print(f"Warning: Brain API not available: {e}", file=sys.stderr)

# ─── Knowledge Indexer callback endpoint (ADR-0294) ───────────────

try:
    from cockpit.web.knowledge_indexer import callback_router as _ki_callback_router

    app.include_router(_ki_callback_router)
    print("Successfully loaded KnowledgeIndexer callback route")
except Exception as e:
    print(f"Warning: KnowledgeIndexer callback router not available: {e}", file=sys.stderr)

# ─── Capability Registry API (能力全景覆盖) ─────────────────────

try:
    from cockpit.web.api_capability import router as _capability_router

    app.include_router(_capability_router)
    print("Successfully loaded Capability Registry API routes")
except Exception as e:
    print(f"Warning: Capability API not available: {e}", file=sys.stderr)

# ─── GBrain Proxy ─────────────────────────────────────────────


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


# Register each method separately so OpenAPI exposes stable, unique operation IDs.
for _admin_method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
    app.add_api_route(
        "/admin/{path:path}",
        proxy_gbrain_admin,
        methods=[_admin_method],
        name=f"proxy_gbrain_admin_{_admin_method.lower()}",
        operation_id=f"proxy_gbrain_admin_{_admin_method.lower()}",
    )


# ─── Main dashboard router ────────────────────────────────────

app.include_router(dashboard_router)


@app.get("/api/cockpit/router-health", dependencies=_AUTH_DEPS)
async def router_health() -> dict[str, object]:
    """Expose structured router loading evidence after graceful degradation."""
    return router_health_snapshot()

# ─── Static files (Cockpit UI) ────────────────────────────

if COCKPIT_UI_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(COCKPIT_UI_DIST), html=True), name="cockpit_ui")

# 所有业务路由都挂载完成后，再同步版本目录，避免 /api/version/history 变成空壳。
register_app_routes(app)


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
