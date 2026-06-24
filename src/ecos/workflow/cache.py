"""Workflow Step Cache — 步骤级内存缓存（TTL + 线程安全）

用于缓存工作流步骤的执行结果，减少重复执行。
设计原则：
  - 轻量：仅内存缓存，无外部依赖
  - 线程安全：threading.RLock 保护共享状态
  - 按需 TTL：每步可独立配置过期时间
  - 批量失效：按工作流粒度清除

每个缓存条目结构：
  {
    "value": dict,       # 步骤执行结果
    "cached_at": float,  # time.monotonic() 写入时间戳
    "ttl": int,          # 过期秒数
  }
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger("ecos.workflow.cache")

# ── 缓存存储 ────────────────────────────────────────────────────────────────

_cache: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()  # 保证并发安全


def _make_key(workflow_name: str, step_index: int, params: dict | None = None) -> str:
    """生成缓存键。

    键格式: {workflow_name}:{step_index}[:{params_hash}]
    当 params 不同时，同一工作流的同一步骤视为不同缓存条目。
    """
    key = f"{workflow_name}:{step_index}"
    if params:
        # 对 params 做确定性 hash，简短且可读
        stable = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
        h = hashlib.sha256(stable.encode()).hexdigest()[:12]
        key = f"{key}:{h}"
    return key


def get(workflow_name: str, step_index: int, params: dict | None = None) -> dict | None:
    """获取缓存的步骤执行结果。

    如果缓存存在且未过期，返回结果 dict。
    如果不存在或已过期，返回 None。
    """
    key = _make_key(workflow_name, step_index, params)
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None

        elapsed = time.monotonic() - entry["cached_at"]
        ttl = entry.get("ttl", 0)
        if ttl > 0 and elapsed >= ttl:
            # 已过期，清除这个条目
            del _cache[key]
            logger.debug("Cache expired: %s (%.1fs > %ds)", key, elapsed, ttl)
            return None

        elapsed_s = time.monotonic() - entry["cached_at"]
        logger.debug("Cache hit: %s (age=%.1fs, ttl=%ds)", key, elapsed_s, ttl)
        return dict(entry["value"])  # 返回副本，避免外部修改


def set(
    workflow_name: str,
    step_index: int,
    result: dict,
    ttl: int = 0,
    params: dict | None = None,
) -> None:
    """缓存步骤执行结果。

    Args:
        workflow_name: 工作流名称
        step_index: 步骤索引（从 0 开始）
        result: 执行结果 dict（会被复制存储）
        ttl: 缓存过期秒数。0 表示不缓存。
        params: 执行参数（用于差异化缓存键）
    """
    if ttl <= 0:
        return  # TTL <= 0 = 不缓存

    key = _make_key(workflow_name, step_index, params)
    with _lock:
        _cache[key] = {
            "value": dict(result),  # 存储副本，隔离外部修改
            "cached_at": time.monotonic(),
            "ttl": ttl,
        }
    logger.debug("Cache set: %s (ttl=%ds)", key, ttl)


def invalidate(workflow_name: str) -> int:
    """使指定工作流的所有缓存条目失效。

    用于手动清除缓存（如工作流定义变更后）。

    Returns:
        清除的缓存条目数量
    """
    prefix = f"{workflow_name}:"
    with _lock:
        keys = [k for k in _cache if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
    if keys:
        logger.info("Cache invalidated: %s (%d entries)", workflow_name, len(keys))
    return len(keys)


def invalidate_all() -> int:
    """使全部缓存条目失效。"""
    with _lock:
        count = len(_cache)
        _cache.clear()
    if count:
        logger.info("Cache fully invalidated: %d entries", count)
    return count


def status() -> dict[str, Any]:
    """返回缓存当前状态统计。

    用于 workflow_cache_status MCP tool。
    """
    with _lock:
        total = len(_cache)
        now = time.monotonic()
        entries = []
        for key, entry in sorted(_cache.items()):
            elapsed = now - entry["cached_at"]
            remaining = max(0, entry["ttl"] - elapsed)
            entries.append(
                {
                    "key": key,
                    "age_s": round(elapsed, 1),
                    "ttl_s": entry["ttl"],
                    "remaining_s": round(remaining, 1),
                }
            )

    return {
        "total_entries": total,
        "entries": entries,
    }
