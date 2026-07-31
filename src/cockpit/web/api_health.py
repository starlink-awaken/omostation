"""Health Summary API endpoints.

提供系统健康概览数据。

Routes:
    GET /api/health/summary  → 系统健康概览
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = WORKSPACE_ROOT
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"


def run_l4_script(script_name: str, args: list[str] | None = None) -> dict | None:
    """运行 L4-kernel 脚本并返回 JSON 结果。"""
    script_path = L4_KERNEL_DIR / "scripts" / script_name
    if not script_path.exists():
        return None

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Script {script_name} failed: {result.stderr}")
            return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:  # defensive fallback
        print(f"Error running {script_name}: {e}")
        return None


def read_runtime_services() -> list[dict]:
    """Read the runtime service probe without manufacturing a service count."""
    try:
        from cockpit.adapters.runtime import i0_services

        raw = i0_services() if i0_services else []
    except Exception as e:  # defensive fallback
        print(f"Runtime service probe failed: {e}")
        return []

    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("services") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def is_active_service(service: dict) -> bool:
    if service.get("port_listening") is True:
        return True
    return service.get("status") in {"running", "active", "idle", "configured"} and service.get("health") not in {
        "unhealthy",
        "error",
        "unreachable",
    }


def read_active_task_count() -> int | None:
    """Read the canonical OMO active queue; L4 signals are not task counts."""
    active_dir = WORKSPACE_DIR / ".omo" / "tasks" / "active"
    try:
        if not active_dir.is_dir():
            return None
        return sum(1 for path in active_dir.glob("*.yaml") if path.is_file())
    except OSError:
        return None


@router.get("/api/health/summary")
async def get_health_summary():
    """获取系统健康概览。"""
    # 获取 L4 域健康数据
    l4_data = run_l4_script("health_monitor.py", ["--output", "json"])

    # 获取真实运行探针；L4 信号不是服务数量，不能互相替代。
    services_data = run_l4_script("signal_analysis.py", ["--hours", "24", "--output", "json"])
    runtime_services = read_runtime_services()

    # 计算健康概览。任何缺失的数据源都显式降级，不返回伪造的满分。
    active_services = sum(1 for service in runtime_services if is_active_service(service))
    total_services = len(runtime_services)
    health_score = round(active_services / total_services * 100) if total_services else 0
    active_tasks = read_active_task_count()
    active_tasks_source = "omo" if active_tasks is not None else "unavailable"
    today_requests = 0
    degraded_reasons: list[str] = []

    if l4_data:
        # 从 L4 健康数据计算健康分数
        healthy_count = l4_data.get("healthy_count", 0)
        total_domains = l4_data.get("total_domains", 1)
        health_score = int(healthy_count / total_domains * 100) if total_domains > 0 else 100

        # L4 domains and their signals remain diagnostic only; task count comes from OMO.
    else:
        degraded_reasons.append("L4 health_monitor.py unavailable")

    if services_data:
        # 从信号分析获取服务状态
        today_requests = int(services_data.get("today_requests") or services_data.get("request_count") or 0)
    else:
        degraded_reasons.append("L4 signal_analysis.py unavailable")

    if not runtime_services:
        degraded_reasons.append("runtime service probe unavailable")
    if active_tasks is None:
        active_tasks = 0

    sources_available = sum(bool(source) for source in (l4_data, services_data, runtime_services))
    data_quality = "complete" if sources_available == 3 else "partial" if sources_available else "unavailable"

    return {
        "health_score": health_score,
        "health_score_change": 0,
        "active_services": active_services,
        "total_services": total_services,
        "active_tasks": active_tasks,
        "active_tasks_source": active_tasks_source,
        "today_requests": today_requests,
        "today_requests_change": 0,
        "data_quality": data_quality,
        "degraded_reasons": degraded_reasons,
    }
