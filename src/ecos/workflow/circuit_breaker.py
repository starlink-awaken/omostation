"""Backend Circuit Breaker — 后端不可达缓存（防止重复超时堆积）

当 backend 调用失败（超时/连接错误），记录为"不可达"状态并设置短 TTL（默认 10s）。
在 TTL 内，后续调用直接降级到 fallback，不再尝试已失效的后端。

设计原则：
  - 轻量：无外部依赖，与 workflow cache 同层
  - 线程安全：threading.RLock
  - 短 TTL：默认 10s，避免长时间阻断
  - 自动恢复：TTL 过期后自动重新探测

使用场景：
  - Agora MCP HTTP 调用超时
  - Swarm CLI subprocess 超时
  - 任何可能会挂起的后端调用
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger("ecos.workflow.circuit_breaker")

# ── 电路存储 ────────────────────────────────────────────────────────────────

# backend_name → {"unreachable_since": float, "ttl": int}
_circuits: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()

DEFAULT_TTL = 10  # 默认熔断 TTL（秒）


def _make_key(backend_name: str, target: str = "") -> str:
    """生成熔断键。

    key = backend_name[:target]
    当 backend 有多个目标时用 target 区分。
    """
    if target:
        return f"{backend_name}:{target}"
    return backend_name


def is_available(backend_name: str, target: str = "") -> bool:
    """检查后端是否可用（未被熔断）。"""
    key = _make_key(backend_name, target)
    with _lock:
        circuit = _circuits.get(key)
        if circuit is None:
            return True  # 没有被熔断，可用

        elapsed = time.monotonic() - circuit["unreachable_since"]
        ttl = circuit.get("ttl", DEFAULT_TTL)
        if elapsed >= ttl:
            # TTL 已过期，清除熔断状态
            del _circuits[key]
            logger.info("Circuit breaker reset: %s (after %.1fs)", key, elapsed)
            return True

        remaining = ttl - elapsed
        logger.debug("Circuit breaker OPEN: %s (%.1fs remaining)", key, remaining)
        return False


def trip(backend_name: str, target: str = "", ttl: int = DEFAULT_TTL) -> None:
    """触发熔断：记录后端不可达。

    Args:
        backend_name: 后端名称（如 "agora", "swarm"）
        target: 目标标识（如 URL, step name）
        ttl: 熔断持续时间（秒）
    """
    key = _make_key(backend_name, target)
    with _lock:
        _circuits[key] = {
            "unreachable_since": time.monotonic(),
            "ttl": ttl,
        }
    logger.info("Circuit breaker TRIPPED: %s (ttl=%ds)", key, ttl)


def reset(backend_name: str, target: str = "") -> None:
    """手动重置熔断状态（后端恢复后调用）。

    如果 target 为空，重置该 backend 下所有熔断（前缀匹配）。
    """
    key = _make_key(backend_name, target)
    with _lock:
        if target:
            _circuits.pop(key, None)
        else:
            # 前缀匹配：清除所有以 backend_name 开头的电路
            keys = [
                k
                for k in _circuits
                if k.startswith(f"{backend_name}:") or k == backend_name
            ]
            for k in keys:
                del _circuits[k]
    logger.info("Circuit breaker RESET: %s", key)


def reset_all() -> int:
    """重置所有熔断。返回清除数量。"""
    with _lock:
        count = len(_circuits)
        _circuits.clear()
    if count:
        logger.info("Circuit breaker RESET ALL: %d entries", count)
    return count


def status() -> dict[str, Any]:
    """返回当前熔断状态。"""
    with _lock:
        now = time.monotonic()
        entries = []
        for key, circuit in sorted(_circuits.items()):
            elapsed = now - circuit["unreachable_since"]
            remaining = max(0, circuit["ttl"] - elapsed)
            entries.append(
                {
                    "key": key,
                    "unreachable_since_s": round(elapsed, 1),
                    "ttl_s": circuit["ttl"],
                    "remaining_s": round(remaining, 1),
                }
            )

    return {
        "total_tripped": len(entries),
        "circuits": entries,
    }
