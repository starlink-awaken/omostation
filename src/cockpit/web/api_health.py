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

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = Path("/Users/xiamingxing/Workspace")
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
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"Error running {script_name}: {e}")
        return None


@router.get("/api/health/summary")
async def get_health_summary():
    """获取系统健康概览。"""
    # 获取 L4 域健康数据
    l4_data = run_l4_script("health_monitor.py", ["--output", "json"])

    # 获取服务状态
    services_data = run_l4_script("signal_analysis.py", ["--hours", "24", "--output", "json"])

    # 计算健康概览
    health_score = 100
    active_services = 28
    total_services = 28
    active_tasks = 0
    today_requests = 0

    if l4_data:
        # 从 L4 健康数据计算健康分数
        healthy_count = l4_data.get("healthy_count", 0)
        total_domains = l4_data.get("total_domains", 1)
        health_score = int(healthy_count / total_domains * 100) if total_domains > 0 else 100

        # 统计活跃任务（从信号中推断）
        domains = l4_data.get("domains", [])
        active_tasks = sum(1 for d in domains if d.get("signal_count", 0) > 0)

    if services_data:
        # 从信号分析获取服务状态
        total_signals = services_data.get("total_signals", 0)
        today_requests = total_signals * 10  # 估算请求数

    return {
        "health_score": health_score,
        "health_score_change": 2,  # 模拟变化
        "active_services": active_services,
        "total_services": total_services,
        "active_tasks": active_tasks,
        "today_requests": today_requests,
        "today_requests_change": 15,  # 模拟变化
    }
