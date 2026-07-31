"""cron-service — Standalone cron scheduler for Hermes Agent.

Replaces Hermes' embedded cron scheduler with an independent service
in ~/Workspace/cron-service/. Scripts live in ~/Workspace/<project>/scripts/
as SSOT; cron-service symlinks to them.

Architecture:
    scheduler.py   — Tick-based scheduling engine
    executor.py    — Subprocess script executor
    delivery.py    — Result delivery (local file / WeChat via iLink)
    db.py          — SQLite job persistence
    models.py      — Pydantic data models
    mcp_server.py  — FastMCP server for Hermes integration
    server.py      — FastAPI entry point + service lifecycle
"""

import builtins as _builtins

from runtime.cron_service.classify import classify_tasks, sort_by_priority  # type: ignore[import-not-found]

__version__ = "1.0.0"

_builtins.classify_tasks = classify_tasks
_builtins.sort_by_priority = sort_by_priority

__all__ = (
    "__version__",
    "classify_tasks",
    "sort_by_priority",
)
