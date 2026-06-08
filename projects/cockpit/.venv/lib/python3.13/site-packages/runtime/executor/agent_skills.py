"""Agent skill management, registration, execution, and caching.

Maps to TS source: agentmesh/packages/engine/src/agent-runner-skills.ts

Provides:
  - SkillsManager: wraps SkillRegistry + SkillExecutor with caching, stats, trace IDs
  - Skill result caching with TTL and LRU-style eviction
  - Execution statistics tracking per skill
  - MessageBus event integration
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from runtime.executor.workflow_skills import (
    SkillConfig,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutor,
    SkillRegistry,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class SkillExecutionStats:
    """Aggregate execution statistics across all skills."""
    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    avg_duration_ms: float = 0.0
    by_skill: dict[str, int] = field(default_factory=dict)


@dataclass
class SkillCacheEntry:
    """A single cache entry with timestamp for TTL checking."""
    result: SkillExecutionResult
    timestamp: float = 0.0
    hash_key: str = ""


@dataclass
class SkillsIntegrationConfig:
    """Configuration for SkillsManager behaviour."""
    cache_enabled: bool = True
    cache_max_size: int = 100
    cache_ttl_ms: int = 300_000       # 5 minutes
    default_timeout_ms: int = 30_000   # 30 seconds


# ---------------------------------------------------------------------------
# SkillsManager
# ---------------------------------------------------------------------------


class SkillsManager:
    """Manages skill lifecycle: registration, execution, caching, and monitoring."""

    def __init__(self, config: SkillsIntegrationConfig | None = None) -> None:
        self._config = config or SkillsIntegrationConfig()
        self._registry: SkillRegistry = SkillRegistry()
        self._executor: SkillExecutor = SkillExecutor(self._registry)
        self._cache: dict[str, SkillCacheEntry] = {}
        self._stats = SkillExecutionStats()
        self._current_trace_id: str | None = None
        self._message_bus: Any = None

    # ------------------------------------------------------------------
    # Registration & Query
    # ------------------------------------------------------------------

    async def register_skill(self, config: SkillConfig) -> str:
        return self._registry.register(config)

    async def unregister_skill(self, skill_id: str, version: str | None = None) -> None:
        self._registry.unregister(skill_id, version)
        self._clear_cache_for_skill(skill_id)

    async def get_skill(self, skill_id: str) -> SkillConfig | None:
        return self._registry.get(skill_id)

    async def has_skill(self, skill_id: str) -> bool:
        return self._registry.has(skill_id)

    async def query_skills(self) -> list[SkillConfig]:
        return self._registry.list()

    async def search_skills(self, query: str) -> list[SkillConfig]:
        return self._registry.search(query)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_skill(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        cache_key = self._generate_cache_key(request)

        if self._config.cache_enabled:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        self._stats.total_executions += 1
        start = time.perf_counter()

        try:
            if self._current_trace_id is None:
                self._current_trace_id = self.generate_trace_id()

            result = await self._executor.execute(request)
            duration = (time.perf_counter() - start) * 1000

            if result.status == "completed":
                self._stats.successful += 1
            else:
                self._stats.failed += 1

            self._update_avg_duration(duration)

            sid = request.skill_id
            self._stats.by_skill[sid] = self._stats.by_skill.get(sid, 0) + 1

            if self._config.cache_enabled and result.status == "completed":
                self._set_to_cache(cache_key, result)

            self._emit_event("skill:executed", {
                "skill_id": request.skill_id,
                "status": result.status,
                "duration_ms": duration,
            })

            return result
        except Exception:
            self._stats.failed += 1
            raise

    async def execute_skill_batch(self, requests: list[SkillExecutionRequest]) -> list[SkillExecutionResult]:
        return await self._executor.execute_batch(requests)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _generate_cache_key(self, request: SkillExecutionRequest) -> str:
        raw = f"{request.skill_id}:{sorted(str(request.inputs.items()))}"
        return str(hash(raw))

    def _get_from_cache(self, key: str) -> SkillExecutionResult | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        age = (time.time() - entry.timestamp) * 1000
        if age > self._config.cache_ttl_ms:
            del self._cache[key]
            return None
        return entry.result

    def _set_to_cache(self, key: str, result: SkillExecutionResult) -> None:
        if len(self._cache) >= self._config.cache_max_size:
            first = next(iter(self._cache))
            if first is not None:
                del self._cache[first]
        self._cache[key] = SkillCacheEntry(result=result, timestamp=time.time(), hash_key=key)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _clear_cache_for_skill(self, skill_id: str) -> None:
        to_delete = [k for k, v in self._cache.items() if v.result.skill_id == skill_id]
        for k in to_delete:
            del self._cache[k]

    def get_cache_size(self) -> int:
        return len(self._cache)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_execution_stats(self) -> SkillExecutionStats:
        from copy import deepcopy
        return deepcopy(self._stats)

    def reset_stats(self) -> None:
        self._stats = SkillExecutionStats()

    def _update_avg_duration(self, duration_ms: float) -> None:
        total = self._stats.total_executions
        current = self._stats.avg_duration_ms
        self._stats.avg_duration_ms = (current * (total - 1) + duration_ms) / total

    # ------------------------------------------------------------------
    # Trace ID
    # ------------------------------------------------------------------

    def generate_trace_id(self) -> str:
        self._current_trace_id = uuid.uuid4().hex
        return self._current_trace_id

    def get_current_trace_id(self) -> str | None:
        return self._current_trace_id

    def set_current_trace_id(self, trace_id: str) -> None:
        self._current_trace_id = trace_id

    def clear_trace_id(self) -> None:
        self._current_trace_id = None

    # ------------------------------------------------------------------
    # MessageBus
    # ------------------------------------------------------------------

    def set_message_bus(self, message_bus: Any) -> None:
        self._message_bus = message_bus

    def get_message_bus(self) -> Any | None:
        return self._message_bus

    def _emit_event(self, event: str, payload: dict[str, Any]) -> None:
        if self._message_bus is None:
            return
        try:
            self._message_bus.send({
                "id": uuid.uuid4().hex,
                "from": "SkillsManager",
                "to": "*",
                "type": "event",
                "priority": 1,
                "payload": {"event": event, **payload},
                "context_shards": [],
                "timestamp": time.time(),
                "trace_id": self._current_trace_id,
            })
        except Exception:
            pass  # fire-and-forget

    # ------------------------------------------------------------------
    # Direct Access
    # ------------------------------------------------------------------

    def get_registry(self) -> SkillRegistry:
        return self._registry

    def get_executor(self) -> SkillExecutor:
        return self._executor

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def dispose(self) -> None:
        self._cache.clear()
        self._registry._skills.clear()
        self._stats = SkillExecutionStats()
        self._current_trace_id = None
        self._message_bus = None

    def is_disposed(self) -> bool:
        return len(self._registry._skills) == 0


def create_skills_manager(config: SkillsIntegrationConfig | None = None) -> SkillsManager:
    """Factory function matching the TS createSkillsManager export."""
    return SkillsManager(config)
