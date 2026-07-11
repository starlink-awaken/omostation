"""L4 Domain Health API endpoints.

提供 L4 域健康状态、趋势分析和信号分析的 API 接口。

Routes:
    GET /api/l4/health      → L4 域健康状态
    GET /api/l4/trend       → 历史趋势分析
    GET /api/l4/signals     → 跨域信号分析
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

# L4-kernel 项目路径 (硬编码，因为 cockpit 和 l4-kernel 是兄弟目录)
WORKSPACE_DIR = Path("/Users/xiamingxing/Workspace")
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"
L4_CONFIG_PATH = L4_KERNEL_DIR / "l4_domain_paths.toml"


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


def _unavailable_payload(script_name: str, shape: dict) -> dict:
    return {
        **shape,
        "data_quality": "unavailable",
        "source": "l4-kernel-script",
        "degraded_reasons": [
            f"L4 {script_name} unavailable",
            f"缺少或未加载 L4 路径配置：{L4_CONFIG_PATH}",
        ],
        "configuration": {
            "path": str(L4_CONFIG_PATH),
            "exists": L4_CONFIG_PATH.exists(),
            "next_action": "按 l4-kernel 的 [domain_paths] 契约补齐本机路径，再重试。",
        },
    }


def _live_payload(data: dict) -> dict:
    return {**data, "data_quality": data.get("data_quality", "live"), "source": "l4-kernel-script"}


@router.get("/api/l4/health")
async def get_l4_health():
    """获取 L4 域健康状态。"""
    data = run_l4_script("health_monitor.py", ["--output", "json"])
    if data:
        return _live_payload(data)
    else:
        return _unavailable_payload("health_monitor.py", {
            "timestamp": "",
            "total_domains": 0,
            "document_domains": 0,
            "domains": [],
            "healthy_count": 0,
            "unhealthy_count": 0,
            "health_rate": "N/A",
        })


@router.get("/api/l4/trend")
async def get_l4_trend():
    """获取 L4 域历史趋势分析。"""
    data = run_l4_script("health_trend.py", ["--days", "7", "--output", "json"])
    if data:
        return _live_payload(data)
    else:
        return _unavailable_payload("health_trend.py", {
            "total_records": 0,
            "date_range": {"start": None, "end": None},
            "trends": {},
            "anomalies": [],
        })


@router.get("/api/l4/signals")
async def get_l4_signals():
    """获取 L4 域跨域信号分析。"""
    data = run_l4_script("signal_analysis.py", ["--hours", "72", "--output", "json"])
    if data:
        return _live_payload(data)
    else:
        return _unavailable_payload("signal_analysis.py", {
            "total_signals": 0,
            "by_domain": {},
            "by_type": {},
            "patterns": [],
            "risks": [],
        })
