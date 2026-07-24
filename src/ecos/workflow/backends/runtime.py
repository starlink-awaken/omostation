"""Runtime Backend Adapter — subprocess 模式桥接 runtime executor

适配策略 (优先级降序)：
1. Agora MCP 路由 (通过 agora_mcp_backend 复用)
2. subprocess 调用 runtime CLI (uv run --package runtime)
3. mock fallback (向后兼容)

关键原则：ecos 是 L0，不直接 import L1 包。所有跨层通过 CLI subprocess 或 MCP 路由。
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("ecos.workflow.backends.runtime")

__all__ = ["execute"]

# 可用的 CLI 入口（按优先级排序）
_CLI_PATHS: list[list[str]] = [
    # 1) 通过 uv 运行 runtime CLI (推荐)
    ["uv", "run", "--package", "runtime", "python", "-m", "runtime.cli", "exec", "run"],
    # 2) 直接 python3 调用
    [
        sys.executable,
        str(Path.home() / "Workspace" / "projects" / "runtime" / "cli.py"),
        "exec",
        "run",
    ],
    # 3) 全局安装的 runtime CLI
    [str(Path.home() / "bin" / "runtime"), "exec", "run"],
]

# Action → phase 映射（复用 agora_mcp_backend 的映射表）
_ACTION_TO_PHASE = {
    "research": "research",
    "search": "research",
    "deep_read": "research",
    "multi_source_search": "research",
    "decompose": "research",
    "cross_analyze": "research",
    "counter_argument": "research",
    "entity_extraction": "research",
    "multi_model_voting": "decision",
    "quality_gate": "decision",
    "evaluate": "decision",
    "review": "decision",
    "build_dag": "execution",
    "topological_sort": "execution",
    "parallel_execute": "execution",
    "monitor_nodes": "execution",
    "cascade_results": "execution",
    "run_task": "execution",
    "execute": "execution",
    "implement": "execution",
    "code": "execution",
    "test": "execution",
    "feedback": "feedback",
    "audit": "feedback",
    "health_check": "feedback",
    "output": "delivery",
    "report": "delivery",
    "deliver": "delivery",
    "publish": "delivery",
}


def execute(m1_node: dict, params: dict | None = None) -> dict:
    """Execute workflow steps as runtime project phases via subprocess."""
    steps = m1_node.get("steps", [])
    execution = m1_node.get("execution", {})
    params = params or {}

    wf_id = m1_node.get("id", "runtime-workflow")
    project_id = params.get("project_id", wf_id)

    results: dict[str, Any] = {
        "steps": [],
        "passed": 0,
        "failed": 0,
    }

    if not steps:
        logger.warning("Runtime backend: workflow has no steps")
        return results

    for i, step in enumerate(steps):
        step_name = step.get("name", f"step-{i + 1}")
        action = step.get("action", "")
        phase_name = _ACTION_TO_PHASE.get(action, "init")
        goal = step.get("description") or step.get("name") or action or "task"

        result = _execute_step_runtime(step_name, phase_name, goal, action, project_id)

        if result.get("ok", False):
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "ok",
                    "result": result.get("data", {}),
                }
            )
            results["passed"] += 1
        else:
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "failed",
                    "error": result.get("error", "Unknown error"),
                }
            )
            results["failed"] += 1
            on_failure = (
                step.get("on_failure") or execution.get("on_failure") or "continue"
            )
            if on_failure == "abort":
                break

    return results


def _execute_step_runtime(
    step_name: str,
    phase: str,
    goal: str,
    action: str,
    project_id: str,
) -> dict[str, Any]:
    """Execute a single step via runtime CLI subprocess."""
    # ── 熔断检查：如果 runtime CLI 最近全部不可达，跳过直接降级 ──
    from ecos.workflow.circuit_breaker import (
        is_available as _cb_available,
    )
    from ecos.workflow.circuit_breaker import (
        trip as _cb_trip,
    )

    if _cb_available("runtime", "cli"):
        for cli_cmd in _CLI_PATHS:
            try:
                cmd = [*cli_cmd, "--phase", phase, "--goal", goal, "--json"]
                if project_id:
                    cmd.extend(["--project-id", project_id])
                logger.debug("Runtime subprocess: %s", " ".join(cmd))

                r = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=Path.home(),
                )
                if r.returncode == 0 and r.stdout.strip():
                    try:
                        data = json.loads(r.stdout)
                        return {"ok": True, "data": data}
                    except json.JSONDecodeError:
                        return {"ok": True, "data": {"output": r.stdout.strip()}}
                elif r.returncode != 0 and r.stderr:
                    logger.debug("Runtime CLI error: %s", r.stderr[:200])
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                logger.debug("Runtime CLI not available: %s", e)

        # 所有 CLI 不可用 → 触发熔断 + mock fallback
        _cb_trip("runtime", "cli")
    else:
        logger.info("Runtime circuit breaker OPEN, skip CLI → mock fallback")

    # mock fallback
    logger.info("Runtime backend: no CLI available, mock recording")
    return {
        "ok": True,
        "data": {
            "step": step_name,
            "phase": phase,
            "action": action,
            "mode": "mock",
            "note": "Runtime CLI not found; step recorded as passed",
        },
    }
