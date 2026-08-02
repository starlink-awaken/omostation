from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from agora.core.config import get_api_port
from agora.tools.base import (
    _HAS_PSUTIL,
    JSONDict,
    ToolContext,
    _json_object,
    _psutil,
    _read_json_object,
)

_log = logging.getLogger(__name__)


def tool_get_swarm_health(params: JSONDict, ctx: ToolContext) -> JSONDict:
    uptime = time.time() - ctx.start_time
    try:
        eu_balance = float(os.environ.get("BOS_EU_BALANCE", "0"))
    except ValueError:
        eu_balance = 0.0
    workers: list[JSONDict] = []
    registry_path = Path(ctx.data_dir) / "worker_registry.json"
    if registry_path.exists():
        try:
            with ctx.file_lock:
                registry = _read_json_object(registry_path)
            for wid, info in registry.items():
                worker_info = _json_object(info)
                if worker_info is None:
                    continue
                workers.append(
                    {
                        "id": wid,
                        "role": worker_info.get("role", "unknown"),
                        "status": worker_info.get("status", "unknown"),
                        "eu_usage": float(worker_info.get("eu_usage", 0.0)),
                    }
                )
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            _log.warning("[MCPServer] worker registry read failed: %s", exc)
    wc, active = len(workers), sum(1 for w in workers if w.get("status") == "active")
    overall = (
        "healthy"
        if wc and active == wc
        else ("degraded" if wc == 0 or active > 0 else "unhealthy")
    )
    return {
        "overall": overall,
        "worker_count": wc,
        "workers": workers,
        "eu_balance": eu_balance,
        "mcp_server_uptime": round(uptime, 3),
    }


def tool_get_system_resources(params: JSONDict, ctx: ToolContext) -> JSONDict:
    uptime = time.time() - ctx.start_time
    if _HAS_PSUTIL and _psutil is not None:
        try:
            cpu, vm, disk = (
                _psutil.cpu_percent(interval=None),
                _psutil.virtual_memory(),
                _psutil.disk_usage("/"),
            )
            return {
                "cpu_percent": round(cpu, 2),
                "memory_used_mb": round(vm.used / 1_048_576, 2),
                "memory_total_mb": round(vm.total / 1_048_576, 2),
                "disk_used_gb": round(disk.used / 1_073_741_824, 2),
                "uptime_seconds": round(uptime, 3),
            }
        except (OSError, ValueError) as exc:
            _log.warning("[MCPServer] psutil read failed: %s", exc)
    return {
        "cpu_percent": 0.0,
        "memory_used_mb": 0.0,
        "memory_total_mb": 0.0,
        "disk_used_gb": 0.0,
        "uptime_seconds": round(uptime, 3),
    }


def tool_get_metrics_snapshot(params: JSONDict, ctx: ToolContext) -> JSONDict:
    try:
        eu_balance = float(os.environ.get("BOS_EU_BALANCE", "0"))
    except ValueError:
        eu_balance = 0.0
    daemon_port = get_api_port()
    tasks_total = tasks_success = active_workers = p99_latency_ms = 0.0
    try:
        req = urllib.request.Request(
            f"http://localhost:{daemon_port}/metrics", headers={"Accept": "text/plain"}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            text = resp.read().decode("utf-8")
        for line in text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            try:
                val = float(line.split()[-1])
            except ValueError:
                continue
            if line.startswith("bos_tasks_total"):
                tasks_total += val
                if 'status="success"' in line:
                    tasks_success = val
            elif line.startswith("bos_workers_active "):
                active_workers = val
            elif line.startswith("bos_eu_balance "):
                eu_balance = val
            elif (
                'quantile="0.99"' in line
                and "bos_http_request_duration_seconds" in line
            ):
                p99_latency_ms = val * 1000
    except (OSError, ValueError, TypeError):
        pass
    success_rate = (tasks_success / tasks_total) if tasks_total > 0 else 0.0
    return {
        "eu_balance": eu_balance,
        "active_workers": active_workers,
        "tasks_total": tasks_total,
        "tasks_success_rate": round(success_rate, 4),
        "p99_latency_ms": round(p99_latency_ms, 3),
    }
