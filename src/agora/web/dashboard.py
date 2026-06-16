"""API route handlers for the gateway dashboard.

Web dashboard has been consolidated into cockpit (:8090).
This module provides a redirect to cockpit dashboard.
"""

from __future__ import annotations

from typing import Any

COCKPIT_DASHBOARD_URL = "http://localhost:8090"

_DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>Agora</title>
<style>body{{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:40px;max-width:600px}}
h1{{color:#58a6ff}}a{{color:#58a6ff}}</style>
</head>
<body>
<h1>&#x25C8; Agora</h1>
<p>Web dashboard has been consolidated into <a href="{COCKPIT_DASHBOARD_URL}">Cockpit Dashboard</a> ({COCKPIT_DASHBOARD_URL})</p>
</body></html>"""


def get_dashboard_html() -> str:
    """Return the dashboard HTML page."""
    return _DASHBOARD_HTML


def register_dashboard_routes(router: Any) -> None:
    """Register dashboard route on a FastAPI router."""
    try:
        from fastapi.responses import HTMLResponse
    except ImportError:
        return

    @router.get("/dashboard")
    async def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)
