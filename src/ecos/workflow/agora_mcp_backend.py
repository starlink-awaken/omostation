"""Agora MCP Backend — 通过 Agora MCP 工具路由工作流步骤

不依赖直接 Python import。通过 HTTP 调用 Agora 的 resolve_bos_uri MCP 工具，
将工作流步骤路由到对应的后端服务（metaos、runtime、swarm 等）。

遵循 X1-C02: 跨层调用必须经过 I0/Agora
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("ecos.workflow.agora_backend")

# Agora MCP Gateway 地址
_AGORA_MCP_URL = "http://127.0.0.1:7422"
_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")


def execute(m1_node: dict, params: dict | None = None) -> dict:
    """通过 Agora MCP 执行工作流

    每步的 action 映射为 BOS URI 调用，通过 Agora 路由到后端。
    如果 Agora 不可用，优雅降级为默认后端行为。
    """
    import httpx

    steps = m1_node.get("steps", [])
    params = params or {}
    results: dict[str, Any] = {
        "steps": [],
        "passed": 0,
        "failed": 0,
    }

    # 从 execution 配置获取超时
    execution = m1_node.get("execution", {})
    timeout = execution.get("timeout", 120)

    from ecos.workflow.circuit_breaker import (
        is_available as _cb_available,
    )
    from ecos.workflow.circuit_breaker import (
        trip as _cb_trip,
    )

    # ── 熔断检查：如果 Agora MCP 最近不可达，直接降级 ──
    if _cb_available("agora", "mcp-gateway"):
        # 检查 Agora 是否可达
        try:
            with httpx.Client(trust_env=False) as client:
                r = client.get(f"{_AGORA_MCP_URL}/health", timeout=2)
                if r.status_code != 200:
                    logger.warning(
                        "Agora MCP unreachable (HTTP %d), falling back to default",
                        r.status_code,
                    )
                    _cb_trip("agora", "mcp-gateway")
                    return _fallback_default(m1_node, params)
        except Exception as e:  # defensive fallback
            logger.warning("Agora MCP uncontactable: %s, falling back to default", e)
            _cb_trip("agora", "mcp-gateway")
            return _fallback_default(m1_node, params)
    else:
        logger.info("Agora circuit breaker OPEN, skip health check → fallback directly")
        return _fallback_default(m1_node, params)

    # Agora 可用，开始路由
    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"step-{i}")
        action = step.get("action", "")
        agent_role = step.get("agent_role", "default")

        # 构建 BOS URI
        # 优先使用 step 中定义的 output BOS URI
        # 否则用 action 名称推导
        bos_uri = _step_to_bos_uri(step, action)

        logger.info("Routing via Agora: %s → %s", step_name, bos_uri)

        try:
            headers = {}
            if _AGORA_API_KEY:
                headers["Authorization"] = f"Bearer {_AGORA_API_KEY}"
            with httpx.Client(trust_env=False, headers=headers) as client:
                resp = client.post(
                    f"{_AGORA_MCP_URL}/v1/tools/call",
                    json={
                        "name": "resolve_bos_uri",
                        "arguments": {
                            "uri": bos_uri,
                            "arguments": {
                                "task": params.get("task", ""),
                                "context": params.get("context", ""),
                                "agent_role": agent_role,
                            },
                        },
                    },
                    timeout=timeout,
                )

            if resp.status_code == 200:
                data = resp.json()
                ok = data.get("success", True) or data.get("status") in (
                    "ok",
                    "completed",
                )
                results["steps"].append(
                    {
                        "name": step_name,
                        "status": "ok" if ok else "failed",
                        "bos_uri": bos_uri,
                        "result": data,
                    }
                )
                if ok:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
            else:
                results["steps"].append(
                    {
                        "name": step_name,
                        "status": "failed",
                        "bos_uri": bos_uri,
                        "error": f"Agora returned HTTP {resp.status_code}",
                    }
                )
                results["failed"] += 1

                on_failure = (
                    step.get("on_failure") or execution.get("on_failure") or "continue"
                )
                if on_failure == "abort":
                    logger.warning("Step %s failed, aborting workflow", step_name)
                    break

        except Exception as e:  # defensive fallback
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "error",
                    "error": f"Agora call failed: {e}",
                }
            )
            results["failed"] += 1

    return results


def _step_to_bos_uri(step: dict, action: str) -> str:
    """将 step 的 action 映射为 BOS URI

    优先级:
    1. step.output 中第一个 bos:// URI
    2. action 名称推导
    """
    # 从 output 中找 bos:// URI
    output = step.get("output", [])
    if isinstance(output, list):
        for o in output:
            if isinstance(o, str) and o.startswith("bos://"):
                return o
    elif isinstance(output, str) and output.startswith("bos://"):
        return output

    # 从 action 名称推导
    action_to_bos = {
        "research": "bos://analysis/minerva/research",
        "search": "bos://memory/kos/search",
        "deep_read": "bos://analysis/minerva/research",
        "decompose": "bos://analysis/minerva/research",
        "multi_source_search": "bos://memory/kos/search",
        "entity_extraction": "bos://analysis/codeanalyze/scan",
        "cross_analyze": "bos://analysis/minerva/research",
        "counter_argument": "bos://analysis/minerva/research",
        "quality_gate": "bos://governance/quality/audit",
        "build_dag": "bos://governance/metaos/gate",
        "topological_sort": "bos://governance/metaos/gate",
        "parallel_execute": "bos://governance/metaos/gate",
        "monitor_nodes": "bos://governance/metaos/gate",
        "cascade_results": "bos://governance/metaos/gate",
        "chat": "bos://capability/agent-runtime/chat",
        "run_task": "bos://capability/agent-runtime/run-task",
        "health_check": "bos://governance/omo/audit",
    }
    return action_to_bos.get(action, f"bos://forge/exec/{action}")


def _fallback_default(m1_node: dict, params: dict | None = None) -> dict:
    """Agora 不可用时的优雅降级"""
    from ecos.workflow.backend_registry import _default_executor

    logger.info("Agora unavailable, falling back to default backend")
    return _default_executor(m1_node, params)
