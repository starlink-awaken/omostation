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

def _parse_retry_config(execution: dict) -> dict:
    """解析 retry 配置

    向后兼容:
      max_retries: 3              # 简单整数 = 最多 3 次重试
      retry:
        max_attempts: 3           # 完整配置
        policy: on_failure        # on_failure | always
        backoff:
          initial_delay: 1.0
          multiplier: 2.0
          max_delay: 60.0
    """
    retry = execution.get("retry", {})
    max_retries = execution.get("max_retries", 0)

    if isinstance(retry, dict) and retry.get("max_attempts"):
        return {
            "max_attempts": int(retry["max_attempts"]),
            "policy": retry.get("policy", "on_failure"),
            "backoff": {
                "initial_delay": float(retry.get("backoff", {}).get("initial_delay", 1.0)),
                "multiplier": float(retry.get("backoff", {}).get("multiplier", 2.0)),
                "max_delay": float(retry.get("backoff", {}).get("max_delay", 60.0)),
                "jitter": float(retry.get("backoff", {}).get("jitter", 0.1)),
            },
        }

    if max_retries and isinstance(max_retries, (int, float)):
        return {
            "max_attempts": int(max_retries),
            "policy": "on_failure",
            "backoff": {"initial_delay": 1.0, "multiplier": 2.0, "max_delay": 30.0, "jitter": 0.0},
        }

    return {}


def _compute_backoff_delay(attempt: int, config: dict) -> float:
    """计算退避延迟（秒）"""
    backoff = config.get("backoff", {})
    delay = backoff.get("initial_delay", 1.0) * (backoff.get("multiplier", 2.0) ** (attempt - 1))
    delay = min(delay, backoff.get("max_delay", 60.0))
    jitter = backoff.get("jitter", 0.0)
    if jitter > 0:
        import random
        delay *= 1 + random.uniform(-jitter, jitter)
    return delay


def _should_retry(policy: str, step_result: dict, exception: Exception | None) -> bool:
    """判断是否应重试"""
    if exception:
        return policy in ("on_error", "always")
    if not step_result.get("passed", True):
        return policy in ("on_failure", "always")
    return False


def _default_executor(m1_node: dict, params: dict | None = None) -> dict:
    """默认后端：通过硬编码 subprocess 执行 step action

    向后兼容，保留现有 execute_workflow() 行为。
    新 workflow 通过 execution.backend 字段指定其他后端。
    """
    from ecos.workflow.executor import _execute_step
    import time

    results = {"steps": [], "passed": 0, "failed": 0}
    steps = m1_node.get("steps", [])
    params = params or {}
    execution_config = m1_node.get("execution", {})
    retry_config = _parse_retry_config(execution_config)

    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"step-{i}")
        action = step.get("action", "")

        max_attempts = retry_config.get("max_attempts", 0)
        policy = retry_config.get("policy", "on_failure")
        attempt = 0
        last_error: str | None = None
        step_result = None

        while attempt < max(max_attempts, 1):
            attempt += 1
            try:
                step_result = _execute_step(action, params, step=step)
                ok = step_result.get("passed", True)
                if ok:
                    break
                if attempt >= max_attempts or not _should_retry(policy, step_result, None):
                    break
                delay = _compute_backoff_delay(attempt, retry_config)
                logger.info("Retrying step '%s' (attempt %d/%d) after %.1fs",
                            step_name, attempt, max_attempts, delay)
                time.sleep(delay)
            except Exception as e:
                last_error = str(e)
                if attempt >= max_attempts or not _should_retry(policy, {}, e):
                    break
                delay = _compute_backoff_delay(attempt, retry_config)
                logger.info("Retrying step '%s' after error (attempt %d/%d): %s",
                            step_name, attempt, max_attempts, e)
                time.sleep(delay)

        if step_result is not None:
            ok = step_result.get("passed", True) and last_error is None
        else:
            ok = False

        attempt_info = f" (attempt {attempt}/{max_attempts})" if max_attempts > 1 else ""

        if ok:
            results["steps"].append({
                "name": step_name + attempt_info if attempt > 1 else step_name,
                "status": "ok",
                "result": step_result,
            })
            results["passed"] += 1
        elif step_result is not None:
            results["steps"].append({
                "name": step_name + attempt_info if attempt > 1 else step_name,
                "status": "failed",
                "result": step_result,
            })
            results["failed"] += 1
            on_failure = (step.get("on_failure")
                          or execution_config.get("on_failure")
                          or "continue")
            if on_failure == "abort":
                break
        else:
            results["steps"].append({
                "name": step_name + attempt_info if attempt > 1 else step_name,
                "status": "error",
                "error": last_error or "未知错误",
            })
            results["failed"] += 1
            on_failure = (step.get("on_failure")
                          or execution_config.get("on_failure")
                          or "continue")
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

    _ensure_backends_registered()
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
    _ensure_backends_registered()
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
    _ensure_backends_registered()
    return _backends.get(name)


# ── 惰性后端注册 ──
_backends_registered = False


def _ensure_backends_registered() -> None:
    """惰性注册已知可用的 workflow backends

    避免 import 时副作用——只在首次查询后端时注册。
    通过 try/except 实现可选依赖——缺失不报错。
    """
    global _backends_registered
    if _backends_registered:
        return
    _backends_registered = True

    # metaos backend (可选依赖)
    for mod_path, entry, name, desc in [
        ("ecos.workflow.agora_mcp_backend", "execute", "agora",
         "Agora MCP routing backend (跨层经 I0)"),
        ("ecos.workflow.backends.symphony", "execute", "symphony",
         "Symphony State Machine — 协议级阶段跃迁编排 (L0)"),
        ("ecos.workflow.backends.swarm", "execute", "swarm",
         "Swarm multi-agent task orchestration engine (aetherforge)"),
        ("ecos.workflow.backends.runtime", "execute", "runtime",
         "Runtime project lifecycle orchestrator (INIT→DELIVERY)"),
        ("metaos.core.workflow", "run", "metaos",
         "MetaOS DAG workflow engine (asyncio)"),
        # Dynamic (LLM-driven) — ecos 内置
        ("ecos.workflow.dynamic_backend", "execute", "dynamic",
         "Dynamic mode — LLM 驱动的动态工作流编排"),
    ]:
        try:
            register(name, mod_path, entry, description=desc)
        except Exception:
            # 可选依赖缺失不报错
            pass
