"""Executor ↔ Runtime Matrix 桥接

将 runtime executor 的执行状态桥接到 Runtime Matrix 可观测体系：
1. 注册 executor 为 Matrix 中的服务条目
2. 上报任务执行状态到 matrix_state.json
3. 提供健康检查端点集成
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runtime.executor.config import EXEC_LOG_FILE, log
from runtime.matrix import RUNTIME_HOME

_MATRIX_STATE_FILE = RUNTIME_HOME / "matrix_state.json"


def _load_matrix_state() -> dict[str, Any]:
    """加载当前的 Matrix 状态文件。"""
    if _MATRIX_STATE_FILE.exists():
        try:
            return json.loads(_MATRIX_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"services": {}, "updated_at": ""}


def _save_matrix_state(state: dict[str, Any]) -> None:
    """保存 Matrix 状态文件。"""
    _MATRIX_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(UTC).isoformat()
    _MATRIX_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def register_executor_service(port: int | None = None) -> None:
    """将 executor 注册到 Matrix 状态。

    在 Matrix 的 services 字典中添加/更新 executor 条目，
    使 runtime_health MCP 工具能够报告 executor 状态。
    """
    state = _load_matrix_state()
    services = state.setdefault("services", {})

    services["runtime-executor"] = {
        "name": "runtime-executor",
        "type": "executor",
        "status": "healthy",
        "port": port,
        "log_path": str(EXEC_LOG_FILE),
        "start_command": "python3 -m runtime.executor.runtime",
        "notes": "Agent Runtime executor — 无状态任务执行引擎",
        "registered_at": datetime.now(UTC).isoformat(),
    }
    _save_matrix_state(state)
    log.info("Matrix bridge: runtime-executor registered")


def report_execution(
    task_id: str,
    status: str,
    tokens_used: int = 0,
    duration_sec: float = 0.0,
    error: str | None = None,
) -> None:
    """上报任务执行结果到 Matrix 状态。

    在 Matrix 状态中记录最近执行摘要，便于 runtime_health 工具
    和 Matrix Scheduler 进行可观测性分析。
    """
    state = _load_matrix_state()
    services = state.setdefault("services", {})
    executor = services.setdefault("runtime-executor", {})

    executions = executor.setdefault("executions", [])
    executions.append({
        "task_id": task_id,
        "status": status,
        "tokens_used": tokens_used,
        "duration_sec": round(duration_sec, 2),
        "error": error,
        "at": datetime.now(UTC).isoformat(),
    })
    # 只保留最近 50 条
    if len(executions) > 50:
        executions[:] = executions[-50:]

    # 更新汇总统计
    total = len(executions)
    ok_count = sum(1 for e in executions if e["status"] == "ok")
    fail_count = total - ok_count
    total_tokens = sum(e.get("tokens_used", 0) for e in executions)
    total_duration = sum(e.get("duration_sec", 0) for e in executions)

    executor["summary"] = {
        "total_executions": total,
        "ok": ok_count,
        "fail": fail_count,
        "total_tokens": total_tokens,
        "total_duration_sec": round(total_duration, 2),
        "last_updated": datetime.now(UTC).isoformat(),
    }
    executor["status"] = "degraded" if fail_count > ok_count else "healthy"

    _save_matrix_state(state)


def get_executor_health() -> dict[str, Any]:
    """返回 executor 健康状态（供 Matrix/CLI 查询）。"""
    state = _load_matrix_state()
    executor = state.get("services", {}).get("runtime-executor", {})
    summary = executor.get("summary", {})
    return {
        "status": executor.get("status", "unknown"),
        "registered": "registered_at" in executor,
        "summary": summary,
        "last_execution": executor.get("executions", [None])[-1],
    }
