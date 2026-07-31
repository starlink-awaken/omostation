"""Metrics Trend API endpoints.

提供指标趋势数据。

Routes:
    GET /api/metrics/trend  → 指标趋势
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query

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


@router.get("/api/metrics/trend")
async def get_metrics_trend(
    range: str = Query("24h", description="时间范围: 1h, 6h, 24h, 7d"),
):
    """获取指标趋势。"""
    # 获取 L4 健康数据
    l4_data = run_l4_script("health_monitor.py", ["--output", "json"])
    if not l4_data:
        return {
            "health_score": [],
            "requests": [],
            "error_rate": [],
            "data_quality": "unavailable",
            "degraded_reasons": ["L4 health_monitor.py unavailable", "historical metric source unavailable"],
        }

    healthy_count = l4_data.get("healthy_count", 0)
    total_domains = l4_data.get("total_domains", 0)
    health_score = round(healthy_count / total_domains * 100) if total_domains else 0
    return {
        "health_score": [{"timestamp": datetime.now(UTC).isoformat(), "value": health_score}],
        "requests": [],
        "error_rate": [],
        "data_quality": "partial",
        "degraded_reasons": ["只有当前健康快照，暂无历史请求和错误率数据"],
    }
