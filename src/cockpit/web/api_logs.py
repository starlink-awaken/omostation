"""Logs API endpoints.

提供日志查看功能。

Routes:
    GET /api/logs  → 日志列表
"""

from __future__ import annotations

import json
import re
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
_LOG_LEVEL_PATTERNS = (
    ("fatal", re.compile(r"\b(?:fatal|critical|panic)\b", re.IGNORECASE)),
    ("error", re.compile(r"\b(?:error|exception|traceback|failed|failure)\b", re.IGNORECASE)),
    ("warning", re.compile(r"\b(?:warn|warning)\b", re.IGNORECASE)),
    ("debug", re.compile(r"\bdebug\b", re.IGNORECASE)),
)


def _infer_log_level(line: str) -> str:
    """Infer a useful level from common plain-text log markers."""
    for level, pattern in _LOG_LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return "info"


def _log_timestamp(log_file: Path, line: str) -> str:
    """Preserve an embedded ISO timestamp and fall back to file mtime."""
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2}T[^\s\]]+)", line)
    if match:
        return match.group(1)
    try:
        return datetime.fromtimestamp(log_file.stat().st_mtime, UTC).isoformat()
    except OSError:
        return datetime.now(UTC).isoformat()


def _read_log_entries(log_file: Path, source: str, max_lines: int) -> list[dict]:
    """Read bounded plain-text entries while preserving their severity."""
    entries: list[dict] = []
    try:
        with log_file.open(encoding="utf-8", errors="replace") as handle:
            for raw_line in handle.readlines()[:max_lines]:
                line = raw_line.strip()
                if not line:
                    continue
                entries.append(
                    {
                        "timestamp": _log_timestamp(log_file, line),
                        "level": _infer_log_level(line),
                        "source": source,
                        "message": line,
                    }
                )
    except OSError:
        return []
    return entries


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
            logs.extend(_read_log_entries(log_file, "l4-kernel", 100))

    # 从 runtime 日志获取
    runtime_logs_dir = WORKSPACE_DIR / "runtime" / "logs"
    if runtime_logs_dir.exists():
        for log_file in sorted(runtime_logs_dir.glob("*.log"), reverse=True)[:3]:
            logs.extend(_read_log_entries(log_file, "runtime", 50))

    return logs


@router.get("/api/logs")
async def get_logs(
    level: str | None = Query(
        None,
        pattern="^(fatal|error|warning|debug|info)$",
        description="日志级别过滤",
    ),
    source: str | None = Query(None, min_length=1, max_length=100, description="日志来源过滤"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
):
    """获取日志列表。"""
    logs = get_logs_from_files()

    # 过滤
    if level:
        logs = [item for item in logs if item["level"] == level]
    if source:
        logs = [item for item in logs if item["source"] == source]

    total = len(logs)

    # 限制数量
    logs = logs[:limit]

    return {
        "items": logs,
        "total": total,
    }
