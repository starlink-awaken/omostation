"""Context shard manager — distributed context for efficient token usage.

Migrated from agentmesh context-shard-manager.ts.

Each agent loads only the context shards relevant to its task plus a
global summary, keeping total context within 60% of the available window.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class ShardScope(StrEnum):
    GLOBAL_SUMMARY = "global-summary"
    MODULE = "module"
    TASK = "task"


SCOPE_PRIORITY: dict[ShardScope, int] = {
    ShardScope.GLOBAL_SUMMARY: 0,
    ShardScope.TASK: 1,
    ShardScope.MODULE: 2,
}

DEFAULT_MAX_WINDOW = 200_000
WINDOW_USAGE_LIMIT = 0.6
SUMMARY_MAX_TOKENS = 2000


@dataclass
class ContextShard:
    shard_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    scope: ShardScope = ShardScope.TASK
    content: str = ""
    token_count: int = 0
    module_name: str = ""
    last_updated: float = field(default_factory=time.time)


@dataclass
class AssembleResult:
    shards: list[ContextShard]
    total_tokens: int
    within_limit: bool


@dataclass
class ShardStats:
    total_shards: int = 0
    total_tokens: int = 0
    by_scope: dict[str, int] = field(default_factory=dict)
    avg_tokens_per_shard: float = 0.0


class ContextShardManager:
    """Manage context shards for efficient token usage."""

    def __init__(self, max_window: int = DEFAULT_MAX_WINDOW) -> None:
        self._shards: dict[str, ContextShard] = {}
        self._max_window = max_window

    # -- CRUD -------------------------------------------------------------

    def create_shard(
        self,
        scope: ShardScope,
        content: str,
        module_name: str | None = None,
    ) -> ContextShard:
        shard = ContextShard(
            scope=scope,
            content=content,
            token_count=self._estimate_tokens(content),
        )
        if module_name:
            shard.module_name = module_name
        self._shards[shard.shard_id] = shard
        return shard

    def get_shard(self, shard_id: str) -> ContextShard | None:
        return self._shards.get(shard_id)

    def update_shard(self, shard_id: str, content: str) -> None:
        shard = self._shards.get(shard_id)
        if shard is None:
            raise ValueError(f"Shard not found: {shard_id}")
        shard.content = content
        shard.token_count = self._estimate_tokens(content)
        shard.last_updated = time.time()

    def delete_shard(self, shard_id: str) -> None:
        self._shards.pop(shard_id, None)

    # -- Query ------------------------------------------------------------

    def get_shards_by_scope(self, scope: ShardScope) -> list[ContextShard]:
        return [s for s in self._shards.values() if s.scope == scope]

    def get_shards_by_module(self, module_name: str) -> list[ContextShard]:
        return [s for s in self._shards.values() if s.module_name == module_name]

    # -- Assembly ---------------------------------------------------------

    def assemble_context(
        self,
        shard_ids: list[str],
        max_window: int | None = None,
    ) -> AssembleResult:
        effective_window = max_window if max_window is not None else self._max_window
        token_budget = int(effective_window * WINDOW_USAGE_LIMIT)
        collected: dict[str, ContextShard] = {}
        for sid in shard_ids:
            shard = self._shards.get(sid)
            if shard:
                collected[sid] = shard
        global_summary = self._get_global_summary()
        if global_summary and global_summary.shard_id not in collected:
            collected[global_summary.shard_id] = global_summary
        shards = sorted(collected.values(), key=lambda s: SCOPE_PRIORITY.get(s.scope, 99))
        total_tokens = sum(s.token_count for s in shards)
        return AssembleResult(
            shards=shards,
            total_tokens=total_tokens,
            within_limit=total_tokens <= token_budget,
        )

    # -- Compression ------------------------------------------------------

    def compress_shard(self, shard_id: str, target_tokens: int) -> ContextShard:
        shard = self._shards.get(shard_id)
        if shard is None:
            raise ValueError(f"Shard not found: {shard_id}")
        if shard.token_count <= target_tokens:
            return shard
        indicator = "[...truncated]"
        indicator_tokens = self._estimate_tokens(indicator)
        content_tokens = max(0, target_tokens - indicator_tokens)
        max_chars = content_tokens * 4
        shard.content = shard.content[:max_chars] + indicator
        shard.token_count = self._estimate_tokens(shard.content)
        shard.last_updated = time.time()
        return shard

    # -- Summary ----------------------------------------------------------

    def _get_global_summary(self) -> ContextShard | None:
        for shard in self._shards.values():
            if shard.scope == ShardScope.GLOBAL_SUMMARY:
                return shard
        return None

    def set_global_summary(self, content: str) -> ContextShard:
        estimated = self._estimate_tokens(content)
        if estimated > SUMMARY_MAX_TOKENS:
            max_chars = SUMMARY_MAX_TOKENS * 4
            content = content[:max_chars]
        existing = self._get_global_summary()
        if existing:
            existing.content = content
            existing.token_count = self._estimate_tokens(content)
            existing.last_updated = time.time()
            return existing
        return self.create_shard(ShardScope.GLOBAL_SUMMARY, content)

    # -- Stats ------------------------------------------------------------

    def get_stats(self) -> ShardStats:
        total_tokens = 0
        by_scope: dict[str, int] = {}
        for shard in self._shards.values():
            total_tokens += shard.token_count
            by_scope[shard.scope.value] = by_scope.get(shard.scope.value, 0) + 1
        n = len(self._shards)
        return ShardStats(
            total_shards=n,
            total_tokens=total_tokens,
            by_scope=by_scope,
            avg_tokens_per_shard=total_tokens / n if n > 0 else 0.0,
        )

    # -- Token estimation ------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    # -- Housekeeping ----------------------------------------------------

    def prune_stale(self, max_age_ms: float) -> int:
        cutoff = time.time() * 1000 - max_age_ms
        removed = 0
        stale = [sid for sid, s in self._shards.items() if s.last_updated * 1000 < cutoff]
        for sid in stale:
            self._shards.pop(sid, None)
            removed += 1
        return removed

    def clear(self) -> None:
        self._shards.clear()
