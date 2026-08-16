"""KOS Collab → agentmesh MCP bridge.

Sends collab tasks to agentmesh Gateway for distributed execution.
Silently skips when AGENTMESH_API_URL or API_KEY is not configured (dev mode).
"""

import logging
import os
from typing import cast

AGENTMESH_URL = os.environ.get("AGENTMESH_API_URL", "http://localhost:3000")
API_KEY = os.environ.get("API_KEY", "")


def dispatch_to_agentmesh(task_data: dict) -> str | None:
    """Send a KOS collab task to agentmesh for execution.

    Returns the agentmesh task_id on success, or None on failure.
    Failure is logged as warning and does NOT raise — caller must not block on this.
    """
    if not API_KEY:
        return None  # silently skip — dev mode

    try:
        import httpx

        resp = httpx.post(
            f"{AGENTMESH_URL}/v1/tasks",
            json=task_data,
            headers={"X-API-Key": API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        return cast("str | None", resp.json().get("task_id"))
    except ImportError:
        # Fallback: urllib when httpx is not available
        import json as _json
        import urllib.error
        import urllib.request

        data = _json.dumps(task_data).encode()
        req = urllib.request.Request(  # noqa: S310
            f"{AGENTMESH_URL}/v1/tasks",
            data=data,
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = _json.loads(resp.read().decode())
                return cast("str | None", body.get("task_id"))
        except urllib.error.URLError:
            return None
    except Exception as e:
        logging.warning("agentmesh dispatch failed: %s", e)
        return None
