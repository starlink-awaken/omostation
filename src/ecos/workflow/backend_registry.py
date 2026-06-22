"""Backend Registry — 动态后端注册与路由

每个 backend 是一个可调用对象，接受 (m1_node, params) 并返回 dict。
通过注册机制而非硬编码来支持多后端。
"""

from __future__ import annotations

import logging
import importlib
from typing import Any, Callable

logger = logging.getLogger("ecos.workflow.backend_registry")

# 后端注册表: name → {"module_path", "entrypoint", "instance"}
_backends: dict[str, dict[str, Any]] = {}

# ── 默认后端：沿用现有的硬编码 action 执行器 ──

def _default_executor(m1_node: dict, params: dict | None = None) -> dict:
    """默认后端：通过硬编码 subprocess 执行 step action

    向后兼容，保留现有 execute_workflow() 行为。
    新 workflow 通过 execution.backend 字段指定其他后端。
    """
    from ecos.workflow.executor import _execute_step

    results = {"steps": [], "passed": 0, "failed": 0}
    steps = m1_node.get("steps", [])
    params = params or {}

    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"step-{i}")
        action = step.get("action", "")
        try:
            step_result = _execute_step(action, params)
            ok = step_result.get("passed", True)
            results["steps"].append({
                "name": step_name,
                "status": "ok" if ok else "failed",
                "result": step_result,
            })
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            results["steps"].append({"name": step_name, "status": "error", "error": str(e)})
            results["failed"] += 1
            on_failure = step.get("on_failure") or \
                (m1_node.get("execution", {}).get("on_failure")) or "continue"
            if on_failure == "abort":
                break

    return results


# ── 注册/解析 API ──

def register(name: str, module_path: str, entrypoint: str = "execute",
             description: str = "") -> None:
    """注册一个 workflow backend

    Args:
        name: 后端名称 (在 M1 的 execution.backend 字段使用)
        module_path: Python 模块路径 (如 "metaos.core.workflow")
        entrypoint: 模块内的可调用对象名 (默认 "execute")
        description: 描述信息
    """
    _backends[name] = {
        "module_path": module_path,
        "entrypoint": entrypoint,
        "description": description,
        "instance": None,  # lazy loaded
    }
    logger.info("Backend registered: %s → %s.%s", name, module_path, entrypoint)


def resolve(m1_node: dict) -> Callable:
    """根据 M1 节点解析出对应的后端执行函数

    优先级:
    1. execution.backend 字段指定的后端
    2. 默认后端 (default)
    """
    backend_name = (
        m1_node.get("execution", {}).get("backend")
        or m1_node.get("execution", {}).get("mode")  # 兼容旧格式
        or "default"
    )

    if backend_name == "default":
        return _default_executor

    backend_info = _backends.get(backend_name)
    if not backend_info:
        logger.warning("Backend '%s' not registered, falling back to default", backend_name)
        return _default_executor

    # Lazy load
    if backend_info["instance"] is None:
        try:
            mod = importlib.import_module(backend_info["module_path"])
            func = getattr(mod, backend_info["entrypoint"])
            backend_info["instance"] = func
        except (ImportError, AttributeError) as e:
            logger.error("Failed to load backend '%s': %s", backend_name, e)
            return _default_executor

    return backend_info["instance"]


def list_backends() -> list[dict[str, str]]:
    """列出所有已注册的后端"""
    return [
        {
            "name": name,
            "module_path": info["module_path"],
            "entrypoint": info["entrypoint"],
            "description": info["description"],
            "loaded": info["instance"] is not None,
        }
        for name, info in _backends.items()
    ]


def get_backend(name: str) -> dict[str, Any] | None:
    """获取单个后端信息"""
    return _backends.get(name)


def _auto_register_backends():
    """自动注册已知可用的 workflow backends

    通过 try/except 实现可选依赖——缺失不报错。
    必须在 register() 和 get_backend() 之后调用。
    """
    # metaos backend (可选依赖)
    try:
        register("metaos", "metaos.core.workflow", "run",
                 description="MetaOS DAG workflow engine (asyncio)")
    except Exception:
        pass

    # Agora MCP Backend (ecos 内部模块，必注册)
    try:
        register("agora", "ecos.workflow.agora_mcp_backend", "execute",
                 description="Agora MCP routing backend (跨层经 I0)")
    except Exception:
        pass

    # Symphony Protocol Backend (ecos 内部模块——状态机编排)
    try:
        register("symphony", "ecos.workflow.backends.symphony", "execute",
                 description="Symphony State Machine — 协议级阶段跃迁编排 (L0)")
    except Exception:
        pass

    # Swarm Engine Backend (通过 aetherforge/swarm_engine 可选接入)
    try:
        register("swarm", "ecos.workflow.backends.swarm", "execute",
                 description="Swarm multi-agent task orchestration engine (aetherforge)")
    except Exception:
        pass

    # Runtime Executor Backend (通过 runtime.executor 可选接入)
    try:
        register("runtime", "ecos.workflow.backends.runtime", "execute",
                 description="Runtime project lifecycle orchestrator (INIT→DELIVERY)")
    except Exception:
        pass


_auto_register_backends()
