"""Logs API endpoints.

提供日志查看功能。

Routes:
    GET /api/logs  → 日志列表
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


def get_logs_from_files() -> list[dict]:
    """从日志文件获取日志。"""
    logs = []

    # 从 L4-kernel 日志获取
    logs_dir = L4_KERNEL_DIR / "logs"
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.log"), reverse=True)[:5]:
            try:
                with open(log_file) as f:
                    for line in f.readlines()[:100]:  # 每个文件最多 100 行
                        line = line.strip()
                        if line:
                            logs.append(
                                {
                                    "timestamp": datetime.now(UTC).isoformat(),
                                    "level": "info",
                                    "source": "l4-kernel",
                                    "message": line,
                                }
                            )
            except Exception:  # noqa: S112  # defensive fallback
                continue

    # 从 runtime 日志获取
    runtime_logs_dir = WORKSPACE_DIR / "runtime" / "logs"
    if runtime_logs_dir.exists():
        for log_file in sorted(runtime_logs_dir.glob("*.log"), reverse=True)[:3]:
            try:
                with open(log_file) as f:
                    for line in f.readlines()[:50]:  # 每个文件最多 50 行
                        line = line.strip()
                        if line:
                            logs.append(
                                {
                                    "timestamp": datetime.now(UTC).isoformat(),
                                    "level": "info",
                                    "source": "runtime",
                                    "message": line,
                                }
                            )
            except Exception:  # noqa: S112  # defensive fallback
                continue

    return logs


@router.get("/api/logs")
async def get_logs(
    level: str | None = Query(None, description="日志级别过滤"),
    source: str | None = Query(None, description="日志来源过滤"),
    limit: int = Query(100, description="返回数量限制"),
):
    """获取日志列表。"""
    logs = get_logs_from_files()

    # 过滤
    if level:
        logs = [item for item in logs if item["level"] == level]
    if source:
        logs = [item for item in logs if item["source"] == source]

    # 限制数量
    logs = logs[:limit]

    return {
        "items": logs,
        "total": len(logs),
    }
