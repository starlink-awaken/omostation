"""Unified Base Knowledge Adapter Framework (Adapter Slimming & Consolidation)."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from knowledge.models import KnowledgeDocument, SyncEvent

logger = logging.getLogger("knowledge.adapter")

T = TypeVar("T")


class AdapterHealth:
    """适配器健康状态."""

    def __init__(self, name: str, is_alive: bool = True, latency_ms: float = 0.0, details: str = "") -> None:
        self.name = name
        self.is_alive = is_alive
        self.latency_ms = latency_ms
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "healthy" if self.is_alive else "unhealthy",
            "latency_ms": self.latency_ms,
            "details": self.details,
        }


class BaseKnowledgeAdapter(ABC):
    """统一知识工程适配器抽象基类 (BaseKnowledgeAdapter).

    统一收敛外源接入 (iris)、方法论编译 (sophia)、长文本抽取 (minerva) 与工具编排 (forge) 的样板逻辑：
    - 标准初始化与健康检查
    - 安全容灾执行与降级重试 (Circuit Breaker Safe Execution)
    - 统一数据结构输入输出与双擎同步事件记录
    """

    def __init__(self, name: str, domain: str = "common", config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.domain = domain
        self.config = config or {}
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_open_time = 0.0
        self.failure_threshold = self.config.get("failure_threshold", 5)
        self.recovery_timeout_sec = self.config.get("recovery_timeout_sec", 30.0)

    @abstractmethod
    def health_check(self) -> AdapterHealth:
        """执行端点连通性健康探测."""
        raise NotImplementedError

    @abstractmethod
    def ingest(self, raw_input: Any) -> list[KnowledgeDocument]:
        """将原始输入解析/提取为标准 KnowledgeDocument 列表."""
        raise NotImplementedError

    def execute_safe(self, action_name: str, fn: Callable[[], T], fallback: T | None = None) -> T | None:
        """带断路器容灾与耗时统计的安全执行包装."""
        now = time.monotonic()
        if self._circuit_open:
            if now - self._circuit_open_time > self.recovery_timeout_sec:
                # 尝试半开状态恢复
                logger.info(f"[{self.name}] Circuit half-open, attempting recovery on '{action_name}'")
                self._circuit_open = False
            else:
                logger.warning(f"[{self.name}] Circuit OPEN, short-circuiting '{action_name}' to fallback")
                return fallback

        t0 = time.monotonic()
        try:
            res = fn()
            self._consecutive_failures = 0
            return res
        except Exception as exc:
            self._consecutive_failures += 1
            elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
            logger.error(f"[{self.name}] Error executing '{action_name}' ({elapsed_ms}ms, failures={self._consecutive_failures}): {exc}")
            if self._consecutive_failures >= self.failure_threshold:
                self._circuit_open = True
                self._circuit_open_time = now
                logger.critical(f"[{self.name}] Failure threshold reached. Circuit tripped OPEN for {self.recovery_timeout_sec}s!")
            return fallback

    def create_sync_event(self, doc_id: str, action: str = "upsert", payload: dict[str, Any] | None = None) -> SyncEvent:
        """生成标准双擎同步审计事件."""
        import uuid
        return SyncEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            doc_id=doc_id,
            action=action,
            source=self.name,
            target="gbrain_postgres",
            payload=payload or {},
            status="pending",
        )
