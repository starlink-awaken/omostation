from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path

from agora.tools.base import (
    _HAS_RESULT_BUS,
    JSONDict,
    ToolContext,
    _json_object,
    _read_json_object,
    _require,
    _ResultBus,
    _TaskResult,
)

_log = logging.getLogger(__name__)


def tool_ping(params: JSONDict, ctx: ToolContext) -> JSONDict:
    return {"pong": True, "worker_id": "server"}


def tool_post_result(params: JSONDict, ctx: ToolContext) -> JSONDict:
    task_id = str(_require(params, "task_id"))
    worker_id = str(_require(params, "worker_id"))
    if not (_HAS_RESULT_BUS and _TaskResult is not None and _ResultBus is not None):
        return {
            "accepted": False,
            "task_id": task_id,
            "error": "result_bus_unavailable",
        }

    result = _TaskResult(
        task_id=task_id,
        worker_id=worker_id,
        success=bool(params.get("success", False)),
        output=str(params.get("output", "")),
        quality_score=float(params.get("quality_score", 0.0)),
        eu_consumed=float(params.get("eu_consumed", 0.0)),
        duration_s=float(params.get("duration_s", 0.0)),
        error=str(params.get("error", "")),
    )
    try:
        _ResultBus.get_instance().post_result(result)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        _log.warning("[MCPServer] ResultBus post failed: %s", exc)
        return {
            "accepted": False,
            "task_id": task_id,
            "error": f"result_bus_delivery_failed: {exc}",
        }
    return {"accepted": True, "task_id": task_id}


def tool_get_task_info(params: JSONDict, ctx: ToolContext) -> JSONDict:
    worker_id = str(_require(params, "worker_id"))
    registry_path = Path(ctx.data_dir) / "worker_registry.json"
    if not registry_path.exists():
        return {"error": f"Worker '{worker_id}' not found — registry missing"}
    with ctx.file_lock:
        try:
            registry = _read_json_object(registry_path)
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            return {"error": f"Registry read error: {exc}"}
    worker_info = _json_object(registry.get(worker_id))
    if worker_info is None:
        return {"error": f"Worker '{worker_id}' not found"}
    return worker_info


def tool_broadcast_event(params: JSONDict, ctx: ToolContext) -> JSONDict:
    event_type = str(_require(params, "event_type"))
    source_worker_id = str(_require(params, "source_worker_id"))
    payload = params.get("payload", {})
    event_id, timestamp = str(uuid.uuid4()), time.time()
    record = {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "source_worker_id": source_worker_id,
        "payload": payload,
    }
    data_dir = Path(ctx.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with ctx.file_lock:
        with (data_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return {"event_id": event_id, "timestamp": timestamp}
