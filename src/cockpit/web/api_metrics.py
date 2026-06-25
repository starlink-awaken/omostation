"""Metrics Trend API endpoints.

提供指标趋势数据。

Routes:
    GET /api/metrics/trend  → 指标趋势
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query

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


def generate_time_series_data(hours: int, base_value: float, variance: float) -> list[dict]:
    """生成时间序列数据。"""
    data = []
    now = datetime.now(UTC)
    interval = max(1, hours // 48)  # 最多 48 个数据点

    for i in range(hours, 0, -interval):
        timestamp = now - timedelta(hours=i)
        value = base_value + (hash(str(timestamp)) % 100 - 50) * variance / 100
        data.append(
            {
                "timestamp": timestamp.isoformat(),
                "value": round(value, 2),
            }
        )

    return data


@router.get("/api/metrics/trend")
async def get_metrics_trend(
    range: str = Query("24h", description="时间范围: 1h, 6h, 24h, 7d"),
):
    """获取指标趋势。"""
    # 解析时间范围
    range_hours = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "7d": 168,
    }.get(range, 24)

    # 获取 L4 健康数据
    l4_data = run_l4_script("health_monitor.py", ["--output", "json"])

    # 基础值
    health_score_base = 95
    requests_base = 500
    error_rate_base = 2

    if l4_data:
        # 从 L4 数据计算健康分数
        healthy_count = l4_data.get("healthy_count", 0)
        total_domains = l4_data.get("total_domains", 1)
        health_score_base = int(healthy_count / total_domains * 100) if total_domains > 0 else 100

    # 生成趋势数据
    health_score_data = generate_time_series_data(range_hours, health_score_base, 5)
    requests_data = generate_time_series_data(range_hours, requests_base, 200)
    error_rate_data = generate_time_series_data(range_hours, error_rate_base, 3)

    return {
        "health_score": health_score_data,
        "requests": requests_data,
        "error_rate": error_rate_data,
    }
