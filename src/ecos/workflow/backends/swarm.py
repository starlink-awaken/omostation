"""Swarm Backend Adapter — subprocess 模式桥接 aetherforge/swarm 引擎

适配策略 (优先级降序)：
1. Agora MCP 路由 (agora_mcp_backend.py 复用)
2. subprocess 调用 aetherforge CLI (uv run --package aetherforge)
3. subprocess 调用 swarm-engine CLI (直接)
4. 明确返回不可用（不伪造成功）

关键原则：ecos 是 L0，不直接 import L2 包。所有跨层通过 CLI subprocess 或 MCP 路由。
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("ecos.workflow.backends.swarm")

__all__ = ["execute"]

# 可用的 CLI 入口（按优先级排序）
_CLI_PATHS: list[list[str]] = [
    # 1) 通过 uv 运行 aetherforge CLI (推荐)
    ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.swarm"],
    # 2) 直接 python3 调用
    [
        sys.executable,
        str(
            Path.home()
            / "Workspace"
            / "projects"
            / "aetherforge"
            / "packages"
            / "swarm"
            / "src"
            / "swarm_engine"
            / "cli.py"
        ),
    ],
    # 3) 全局安装的 aetherforge CLI
    [str(Path.home() / "bin" / "aetherforge"), "swarm"],
]


def execute(m1_node: dict, params: dict | None = None) -> dict:
    """Execute workflow steps as swarm tasks via subprocess.

    M1 workflow steps → aetherforge/swarm CLI calls.
    保留 agora MCP 路由为最高优先级。
    """
    steps = m1_node.get("steps", [])
    execution = m1_node.get("execution", {})
    params = params or {}

    results: dict[str, Any] = {
        "steps": [],
        "passed": 0,
        "failed": 0,
    }

    if not steps:
        logger.warning("Swarm backend: workflow has no steps")
        return results

    for i, step in enumerate(steps):
        step_name = step.get("name", f"step-{i + 1}")
        action = step.get("action", "")
        agent_role = step.get("agent_role", "default")

        result = _execute_step_swarm(step_name, action, agent_role, step, params)

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
            if result.get("mode") == "unavailable":
                results["mode"] = "unavailable"
                results["error_code"] = "BACKEND_UNAVAILABLE"
                results["error"] = result.get("error", "Swarm backend unavailable")
            on_failure = (
                step.get("on_failure") or execution.get("on_failure") or "continue"
            )
            if on_failure == "abort":
                break

    return results


def _execute_step_swarm(
    step_name: str,
    action: str,
    agent_role: str,
    step: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Execute a single step via swarm MCP first, then fallback to subprocess."""
    goal = step.get("description") or step.get("name") or action or "task"

    # ── 熔断检查：如果 Agora MCP 已不可达，直接走 subprocess 降级 ──
    from ecos.workflow.circuit_breaker import is_available as _cb_available

    if _cb_available("swarm", "agora-mcp"):
        # ── 第一防线：尝试通过 Agora MCP 发起 RPC 路由调用 ──
        _AGORA_MCP_URL = "http://127.0.0.1:7422"
        logger.info(
            "Swarm backend: Attempting RPC call via Agora MCP for goal: %s", goal
        )
        try:
            import os

            import httpx

            _AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")
            headers = {}
            if _AGORA_API_KEY:
                headers["Authorization"] = f"Bearer {_AGORA_API_KEY}"

            client_kwargs = {"trust_env": False, "timeout": 120.0}
            if headers:
                client_kwargs["headers"] = headers

            with httpx.Client(**client_kwargs) as client:
                payload = {
                    "name": "resolve_bos_uri",
                    "arguments": {
                        "uri": "bos://capability/swarm/run",
                        "arguments": {
                            "goal": goal,
                            "params": params,
                        },
                    },
                }
                resp = client.post(f"{_AGORA_MCP_URL}/v1/tools/call", json=payload)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    if resp_json.get("status") == "ok":
                        result_data = resp_json.get("result", {})
                        if (
                            isinstance(result_data, dict)
                            and result_data.get("status") == "failed"
                        ):
                            logger.warning(
                                "Agora MCP call returned business error: %s. Falling back to subprocess.",
                                result_data.get("error"),
                            )
                        else:
                            logger.info(
                                "Successfully executed swarm task via Agora MCP RPC"
                            )
                            return {"ok": True, "data": result_data}
                    else:
                        logger.warning(
                            "Agora MCP call failed in gateway: %s. Falling back to subprocess.",
                            resp_json.get("error", "Unknown error"),
                        )
                else:
                    logger.warning(
                        "Agora MCP Gateway returned HTTP %d. Falling back to subprocess.",
                        resp.status_code,
                    )
        except Exception as e:  # defensive fallback
            logger.warning(
                "Agora MCP RPC call failed or unavailable: %s. Falling back to subprocess.",
                e,
            )

    # ── 第二防线：优雅降级为本地 CLI Subprocess 直调 ──
    for cli_cmd in _CLI_PATHS:
        try:
            cmd = [*cli_cmd, "run", "--goal", goal, "--json"]
            if params.get("workflow_run_id"):
                cmd.extend(["--workflow-run-id", str(params["workflow_run_id"])])
            if params.get("trace_id"):
                cmd.extend(["--trace-id", str(params["trace_id"])])
            logger.debug("Swarm subprocess: %s", " ".join(cmd))

            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=Path.home(),
            )
            if r.returncode == 0 and r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    return {"ok": True, "data": data}
                except json.JSONDecodeError:
                    # stdout 不是 JSON, 直接返回原始输出
                    return {"ok": True, "data": {"output": r.stdout.strip()}}
            elif r.returncode != 0 and r.stderr:
                logger.debug("Swarm CLI error (retrying): %s", r.stderr[:200])
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("Swarm CLI not available: %s", e)

    # 所有 CLI 不可用 → 明确失败，不把记录当成执行
    logger.info("Swarm backend: no CLI available")
    return {
        "ok": False,
        "mode": "unavailable",
        "error_code": "BACKEND_UNAVAILABLE",
        "error": "Swarm engine CLI unavailable; step was not executed",
        "data": {"step": step_name, "action": action, "mode": "unavailable"},
    }
