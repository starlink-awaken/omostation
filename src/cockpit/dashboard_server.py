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

from fastapi import FastAPI
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
    allow_methods=["GET", "OPTIONS"],
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
):
    try:
        _mod = importlib.import_module(_router_module)
        _router = getattr(_mod, "router", None)
        if _router is not None:
            app.include_router(_router, dependencies=_AUTH_DEPS)
    except Exception:
        pass

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
