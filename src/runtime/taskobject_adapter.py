"""TaskObject v1.0 adapter for Runtime MCP Server.

Maps TaskObject envelopes to Runtime MCP tool calls.
L3 Entry Bridge: the canonical task dispatch pipeline.
"""
from __future__ import annotations
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_SRC = Path(__file__).resolve().parent


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_taskobject(payload: dict) -> str | None:
    """Validate a TaskObject envelope. Returns error string or None if valid."""
    required = ['id', 'intent']
    for field in required:
        if field not in payload:
            return f"Missing required field: {field}"
    if 'target' not in payload or 'service' not in payload.get('target', {}):
        return "Missing target.service"
    if 'tool' not in payload.get('target', {}):
        return "Missing target.tool"
    valid_intents = ['run', 'query', 'control', 'custom']
    if payload.get('intent') not in valid_intents:
        return f"Invalid intent: {payload.get('intent')}. Must be one of {valid_intents}"
    return None


def _mcp_call(tool_name: str, arguments: dict) -> dict:
    """Call a Runtime MCP tool via subprocess."""
    request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        }
    }
    mcp_script = RUNTIME_SRC / "mcp_server.py"
    result = subprocess.run(
        [sys.executable, str(mcp_script)],
        input=json.dumps(request),
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {"status": "error", "error": result.stderr or "No output from MCP server"}
    try:
        response = json.loads(result.stdout.strip())
        if "error" in response:
            return {"status": "error", "error": str(response["error"])}
        return {"status": "ok", "result": response.get("result", {})}
    except json.JSONDecodeError:
        return {"status": "error", "error": f"Invalid JSON response: {result.stdout[:200]}"}


def dispatch_taskobject(payload: dict) -> dict:
    """Dispatch a TaskObject envelope.

    Returns a standardized result dict with status, result/error, and metadata.
    """
    error = _validate_taskobject(payload)
    if error:
        return {"status": "error", "error": error, "task_id": payload.get("id", "")}

    tool_name = payload["target"]["tool"]
    params = payload["target"].get("params", {})

    result = _mcp_call(tool_name, params)
    result["task_id"] = payload.get("id", "")
    result["dispatched_at"] = _utc_now()
    result["source"] = payload.get("context", {}).get("source", "unknown")
    return result


def call_via_taskobject(tool_name: str, params: dict, source: str = "runtime-bridge") -> dict:
    """Wrap a native MCP call in a TaskObject envelope and dispatch."""
    envelope = {
        "id": str(uuid.uuid4()),
        "intent": "query",
        "context": {"source": source, "description": f"TaskObject-wrapped call to {tool_name}"},
        "target": {"service": "runtime", "tool": tool_name, "params": params},
        "callback": {"channel": "stdout", "format": "json"},
        "ttl": 60,
        "priority": 2,
    }
    return dispatch_taskobject(envelope)
