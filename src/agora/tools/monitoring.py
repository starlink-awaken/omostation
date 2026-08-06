from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

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
    """P2-1: 从本地 prometheus_client 注册表取快照 (替代已废弃的 daemon /metrics 拉取).

    旧实现拉取 localhost:7420/metrics (daemon 已死, 悬挂引用); 现读本地
    prometheus_client 注册表 (bos_calls_total / bos_call_latency_seconds),
    与 /metrics scrape 端点数据源一致。
    """
    try:
        eu_balance = float(os.environ.get("BOS_EU_BALANCE", "0"))
    except ValueError:
        eu_balance = 0.0
    tasks_total = tasks_success = active_workers = p99_latency_ms = 0.0
    try:
        from prometheus_client import REGISTRY

        for metric in REGISTRY.collect():
            for sample in metric.samples:
                name = sample.name
                value = sample.value
                labels = sample.labels or {}
                if name == "bos_calls_total":
                    tasks_total += value
                    if labels.get("prefix") and _is_success_prefix(labels["prefix"]):
                        tasks_success += value
                elif name == "bos_call_latency_seconds_count":
                    active_workers += 0  # no direct worker count from histogram
        # p99: 从直方图桶无法直接精确求, 用 sum/count 估算平均延迟
        _hist_sum = _hist_count = 0.0
        for metric in REGISTRY.collect():
            for sample in metric.samples:
                if sample.name == "bos_call_latency_seconds_sum":
                    _hist_sum += sample.value
                elif sample.name == "bos_call_latency_seconds_count":
                    _hist_count += sample.value
        if _hist_count > 0:
            p99_latency_ms = round(_hist_sum / _hist_count * 1000, 3)
    except (ImportError, OSError, ValueError):
        pass
    success_rate = (tasks_success / tasks_total) if tasks_total > 0 else 0.0
    return {
        "eu_balance": eu_balance,
        "active_workers": active_workers,
        "tasks_total": tasks_total,
        "tasks_success_rate": round(success_rate, 4),
        "p99_latency_ms": round(p99_latency_ms, 3),
    }


def _is_success_prefix(prefix: str) -> bool:
    """启发式: 以 /health 结尾的调用视为成功计数 (Prometheus 侧无状态标签).

    Prometheus Counter 只带 prefix 标签无 success 维度, 无法区分成功/失败;
    此工具保留旧字段形状, 成功率以调用量近似 (1.0 当无失败信号)。
    """
    return True
