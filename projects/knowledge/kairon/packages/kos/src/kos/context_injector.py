"""上下文注入器 — 从 D_KnowledgeIntegration 提取并适配到 kos。

将知识查询结果注入 Agent 任务 Prompt，支持三级降级策略：
- Level 1: 重试 3 次，间隔 100ms
- Level 2: 降级到基础 prompt（无知识增强）
- Level 3: 定期检测 MemoryGraph 恢复
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

_log = logging.getLogger(__name__)

# 最大注入三元组数量，防止 prompt 膨胀
_MAX_INJECT_TRIPLES = 20
# 最大 prompt 段长度 (字符)
_MAX_KNOWLEDGE_SECTION = 2000

# 降级配置
_MAX_RETRY_COUNT = 3
_RETRY_INTERVAL_MS = 100
_DEGRADED_MODE_CHECK_INTERVAL = 30.0


# ── 本地数据模型 (共享自 kos.query_service) ─────────────────


@dataclass
class KnowledgeTriple:
    """知识三元组"""

    subject: str
    predicate: str
    obj: str
    metadata: dict[str, Any]

    def to_tuple(self) -> tuple[str, str, str, dict[str, Any]]:
        return (self.subject, self.predicate, self.obj, self.metadata)


# ── No-Op 回退 ───────────────────────────────────────────────


class _NoOpKnowledgeQueryService:
    async def query_knowledge(
        self,
        query: str,
        query_type: str = "semantic",
        limit: int = 100,
        min_quality: float = 0.6,
        time_window_hours: int | None = None,
    ) -> list:
        return []

    async def semantic_search(self, query_text: str, limit: int = 100, time_window_hours: int | None = None) -> list:
        return []

    def get_query_stats(self) -> dict:
        return {}


class _NoOpFreshnessManager:
    def is_fresh(self, subject: str, category: str = "default") -> bool:
        _ = (subject, category)
        return True

    def filter_by_time_window(self, triples: list, hours: int) -> list:
        _ = hours
        return triples

    def get_freshness_stats(self) -> dict:
        return {}


# ── 主类 ─────────────────────────────────────────────────────


class HarvestContextInjector:
    """将知识检索结果注入任务 Prompt。

    工作流:
    1. 根据 persona + task_msg 推导知识查询
    2. 从 MemoryGraph 检索相关三元组（带降级保护）
    3. 按时效性过滤
    4. 格式化为 Prompt 片段并注入

    降级策略:
    - Level 1: 重试 3 次，间隔 100ms
    - Level 2: 降级到基础 prompt（无知识增强）
    - Level 3: 定期检测 MemoryGraph 恢复
    """

    def __init__(self, memory_graph: Any) -> None:
        self._factgraph = memory_graph
        try:
            from kos.freshness import FreshnessManager  # type: ignore[import-not-found]
            from kos.query_service import KnowledgeQueryService  # type: ignore[import-not-found]

            self._query_service: Any = KnowledgeQueryService(memory_graph)
            self._freshness: Any = FreshnessManager(memory_graph)
        except (ImportError, RuntimeError, ValueError, KeyError) as exc:
            _log.warning(
                "HarvestContextInjector: falling back to no-op services because resolution failed: %s",
                exc,
            )
            self._query_service = _NoOpKnowledgeQueryService()
            self._freshness = _NoOpFreshnessManager()
        self._inject_count = 0

        # 降级相关属性
        self._health_checker = None  # D_Memory fact_graph_health → stub 为 None
        self._degraded_mode = False
        self._degraded_since = 0.0
        self._retry_count = 0
        self._fallback_cache: dict[str, list] = {}
        self._lock = threading.Lock()
        self._last_health_check = 0.0

    async def inject_harvest_context(
        self,
        persona: str,
        task_msg: dict,
        workspace_path: str,
        knowledge_query: str | None = None,
    ) -> str:
        t0 = time.monotonic()
        triple_count = 0
        error_msg = ""

        try:
            is_healthy = await self._check_factgraph_health_async()

            if not is_healthy:
                _log.warning("HarvestContextInjector: MemoryGraph unhealthy, using degraded mode")
                self._enter_degraded_mode()

            query = knowledge_query or self._derive_query(persona, task_msg)
            if not query:
                prompt = self._build_prompt(persona, task_msg, workspace_path, [])
            else:
                triples = await self._retrieve_knowledge_with_retry(query)
                triple_count = len(triples)

                fresh_triples = self._filter_fresh(triples)

                if self._degraded_mode and fresh_triples:
                    self._exit_degraded_mode()

                prompt = self._build_prompt(persona, task_msg, workspace_path, fresh_triples)

            elapsed_ms = (time.monotonic() - t0) * 1000
            self._inject_count += 1

            self._log_injection(
                success=True,
                duration_ms=elapsed_ms,
                triple_count=triple_count,
                persona=persona,
            )

            _log.info(
                "ContextInjector: injected %d triples in %.1fms (degraded=%s, total injections: %d)",
                triple_count,
                elapsed_ms,
                self._degraded_mode,
                self._inject_count,
            )
            return prompt

        except (OSError, ValueError, KeyError, RuntimeError, TypeError) as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            error_msg = str(exc)

            self._log_injection(
                success=False,
                duration_ms=elapsed_ms,
                triple_count=triple_count,
                error_message=error_msg,
                persona=persona,
            )

            _log.error(f"ContextInjector: injection failed after {elapsed_ms:.1f}ms: {exc}")
            raise

    async def _check_factgraph_health_async(self) -> bool:
        # 健康检查器已 stub 为 None，默认健康
        if self._health_checker is None:
            return True

        now = time.time()
        with self._lock:
            if now - self._last_health_check < 5.0:
                return not self._degraded_mode

        is_healthy = self._health_checker.is_healthy()

        with self._lock:
            self._last_health_check = now
            if not is_healthy and self._degraded_mode:
                if now - self._degraded_since > _DEGRADED_MODE_CHECK_INTERVAL:
                    is_healthy = self._health_checker.force_recheck()

        return is_healthy

    async def _retrieve_knowledge_with_retry(self, query: str) -> list:
        self._retry_count = 0

        for attempt in range(_MAX_RETRY_COUNT):
            try:
                results = await self._query_service.query_knowledge(
                    query=query,
                    query_type="semantic",
                    limit=_MAX_INJECT_TRIPLES,
                    time_window_hours=168,
                )

                if attempt > 0:
                    _log.info(
                        "HarvestContextInjector: knowledge retrieval succeeded on attempt %d",
                        attempt + 1,
                    )

                return cast("list[Any]", results)

            except (
                ImportError,
                AttributeError,
                TypeError,
                ValueError,
                OSError,
                RuntimeError,
            ) as exc:
                self._retry_count += 1
                _log.warning(
                    "Knowledge retrieval attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )

                if attempt < _MAX_RETRY_COUNT - 1:
                    await asyncio.sleep(_RETRY_INTERVAL_MS / 1000.0)
                else:
                    _log.error(
                        "HarvestContextInjector: all %d retrieval attempts failed",
                        _MAX_RETRY_COUNT,
                    )

        return []

    def _enter_degraded_mode(self) -> None:
        with self._lock:
            if not self._degraded_mode:
                self._degraded_mode = True
                self._degraded_since = time.time()
                _log.warning("HarvestContextInjector: ENTERING DEGRADED MODE - no knowledge enhancement")

    def _exit_degraded_mode(self) -> None:
        with self._lock:
            if self._degraded_mode:
                degraded_duration = time.time() - self._degraded_since
                self._degraded_mode = False
                self._degraded_since = 0.0
                _log.info(
                    "HarvestContextInjector: EXITING DEGRADED MODE after %.1fs - knowledge injection restored",
                    degraded_duration,
                )

    def _log_injection(
        self,
        success: bool,
        duration_ms: float,
        triple_count: int = 0,
        error_message: str = "",
        persona: str = "",
    ) -> None:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": "inject_context",
            "status": "success" if success else "failure",
            "duration_ms": round(duration_ms, 2),
            "triple_count": triple_count,
            "error": error_message,
            "persona": persona,
        }
        _log.info(json.dumps(log_entry, ensure_ascii=False))

    def _derive_query(self, persona: str, task_msg: dict) -> str:
        parts: list[str] = []
        if persona:
            parts.append(persona)
        content = task_msg.get("content", "")
        if isinstance(content, str) and content:
            parts.append(content[:100])
        task_type = task_msg.get("type", "")
        if task_type:
            parts.append(task_type)
        return " ".join(parts).strip()

    async def _retrieve_knowledge(self, query: str) -> list[tuple]:
        try:
            results = await self._query_service.query_knowledge(
                query=query,
                query_type="semantic",
                limit=_MAX_INJECT_TRIPLES,
                time_window_hours=168,
            )
            return cast("list[tuple[Any, ...]]", results)
        except (ImportError, AttributeError, TypeError, ValueError, OSError, RuntimeError) as exc:
            _log.warning("Knowledge retrieval failed (degrading gracefully): %s", exc)
            return []

    def _filter_fresh(self, triples: list) -> list:
        fresh = []
        for t in triples:
            subject = t.subject if hasattr(t, "subject") else (t[0] if t else "")
            try:
                if self._freshness.is_fresh(str(subject)):
                    fresh.append(t)
            except (AttributeError, TypeError, ValueError, KeyError):
                fresh.append(t)
        return fresh[:_MAX_INJECT_TRIPLES]

    def _build_prompt(
        self,
        persona: str,
        task_msg: dict,
        workspace_path: str,
        triples: list,
    ) -> str:
        sections: list[str] = []

        if persona:
            sections.append(f"## Role\nYou are: {persona}")

        content = task_msg.get("content", "")
        if content:
            sections.append(f"## Task\n{content}")

        if workspace_path:
            sections.append(f"## Workspace\nPath: {workspace_path}")

        sections.append(self._build_memory_mount_section(workspace_path))

        if triples:
            knowledge_lines = ["## Relevant Knowledge"]
            for t in triples:
                if hasattr(t, "subject"):
                    line = f"- {t.subject} → {t.predicate} → {t.obj}"
                elif isinstance(t, (tuple, list)) and len(t) >= 3:
                    line = f"- {t[0]} → {t[1]} → {t[2]}"
                else:
                    line = f"- {t}"
                knowledge_lines.append(line)
                if len("\n".join(knowledge_lines)) > _MAX_KNOWLEDGE_SECTION:
                    break
            sections.append("\n".join(knowledge_lines))
        elif self._degraded_mode:
            sections.append("## Knowledge Status\n(Knowledge enhancement temporarily unavailable - using base prompt)")

        meta = {k: v for k, v in task_msg.items() if k != "content" and v}
        if meta:
            sections.append(f"## Context\n```json\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n```")

        return "\n\n".join(sections)

    def _build_memory_mount_section(self, workspace_path: str) -> str:
        scope = workspace_path or "runtime"
        return (
            "## Memory Mounts\n"
            f"- runtime mount: view ({scope})\n"
            "- shared mount: view (task-scoped)\n"
            "- knowledge mount: view (harvest-enhanced)"
        )

    def get_stats(self) -> dict:
        degraded_duration = 0.0
        if self._degraded_mode:
            degraded_duration = time.time() - self._degraded_since

        return {
            "total_injections": self._inject_count,
            "degraded_mode": self._degraded_mode,
            "degraded_duration_seconds": degraded_duration,
            "last_retry_count": self._retry_count,
            "health_checker_available": self._health_checker is not None,
        }


def get_context_injector(memory_graph: Any | None = None) -> HarvestContextInjector:
    """工厂函数：获取 HarvestContextInjector 实例。"""
    if memory_graph is None:
        try:
            from eidos.memory_graph import MemoryGraph  # type: ignore[reportMissingImports]

            memory_graph = MemoryGraph()
        except ImportError:
            return HarvestContextInjector(None)
    return HarvestContextInjector(memory_graph)
