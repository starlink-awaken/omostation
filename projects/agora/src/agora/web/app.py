"""Agora Web Dashboard entry point (bridge).

The full dashboard lives at extrash/web/dashboard.py and is not packaged into
the pip install. This module provides a minimal bridge that tries to import
the extras dashboard, falling back to a status message.

To run the full dashboard:
    cd projects/agora && uv run python3 extrash/web/dashboard.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("agora.web")


def main() -> int:
    """Start the web dashboard, attempting full extras integration first."""
    # Try loading the full extras dashboard
    extras_path = Path(__file__).resolve().parent.parent.parent / "extrash" / "web"
    dashboard_py = extras_path / "dashboard.py"

    if dashboard_py.exists():
        sys.path.insert(0, str(extras_path.parent.parent))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("dashboard", dashboard_py)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "main"):
                    logger.info("Starting full Agora dashboard from extras...")
                    return mod.main()
        except Exception as e:
            logger.warning("Failed to load extras dashboard: %s", e)

    # Fallback: minimal status page
    host = os.environ.get("AGORA_HOST", "0.0.0.0")
    port = int(os.environ.get("AGORA_PORT", "7430"))

    try:
        import uvicorn
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse

        app = FastAPI(title="Agora Dashboard (bridge)")

        @app.get("/")
        async def index():
            return HTMLResponse(
                f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>Agora Dashboard</title>
<style>body{{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:40px;max-width:600px;margin:auto}}
h1{{color:#58a6ff}}.warn{{color:#f0883e;background:#2d1b00;padding:12px;border-radius:6px}}</style>
</head>
<body>
<h1>◈ Agora Dashboard</h1>
<div class="warn">⚠ 完整 Dashboard 需从 extras 启动</div>
<p>运行以下命令启动完整界面:</p>
<pre style="background:#161b22;padding:12px;border-radius:6px">
cd ~/Workspace/projects/agora && uv run python3 extras/web/dashboard.py
</pre>
<p>MCP SSE: <a href="http://localhost:7431/sse">:7431/sse</a></p>
</body>
</html>"""
            )

        @app.get("/health")
        async def health():
            return {"status": "ok", "mode": "bridge", "version": "3.0.0"}

        logger.info("Starting Agora Dashboard (bridge mode) on %s:%s", host, port)
        uvicorn.run(app, host=host, port=port, log_level="info")
        return 0
    except ImportError as e:
        logger.error("Cannot start dashboard: %s", e)
        print(f"Agora Dashboard unavailable — missing dependency: {e}", file=sys.stderr)
        print("Run the full dashboard: uv run python3 extras/web/dashboard.py", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
