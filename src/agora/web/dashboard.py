"""API route handlers for the gateway dashboard and management.

Adapted from agentmesh gateway routes/dashboard.ts.
Serves an HTML dashboard with real-time gateway status.

注意: 完整 Dashboard 在 extras/web/dashboard.py (port 7430, agora web CLI)。
此文件仅保留轻量路由注册入口。
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi.responses import HTMLResponse

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# 轻量 Dashboard HTML — 仅作 fallback，实际页面由 extras/web/dashboard.py 提供
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>Agora</title>
<style>body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:40px;max-width:600px}
h1{color:#58a6ff}a{color:#58a6ff}.note{color:#8b949e;font-size:12px;margin-top:20px}</style>
</head>
<body>
<h1>&#x25C8; Agora</h1>
<p>Full dashboard at <a href="http://localhost:7430/dashboard">extras/web/dashboard.py</a> (port 7430)</p>
<div class="note">Run <code>agora web</code> or <code>cd extras/web && python dashboard.py</code></div>
</body></html>"""


def get_dashboard_html() -> str:
    """Return the dashboard HTML page."""
    return _DASHBOARD_HTML


def register_dashboard_routes(router: Any) -> None:
    """Register dashboard route on a FastAPI router."""
    if not HAS_FASTAPI:
        return

    @router.get("/dashboard")
    async def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)
