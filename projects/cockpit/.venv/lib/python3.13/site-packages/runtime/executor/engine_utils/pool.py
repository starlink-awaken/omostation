"""Generic object pool for reusing expensive objects.

Migrated from agentmesh dsl/object-pool.ts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class ObjectPool[T]:
    """Generic pool that acquires and releases objects of type T.

    Reduces allocation overhead for frequently-created objects such
    as lexers, parsers, or LLM client handles.
    """

    def __init__(
        self,
        factory: Callable[[], T],
        reset: Callable[[T], None] | None = None,
        max_size: int = 10,
    ) -> None:
        self._pool: list[T] = []
        self._factory = factory
        self._reset = reset
        self._max_size = max_size
        self._stats = {
            "acquire_count": 0,
            "hit_count": 0,
            "miss_count": 0,
            "release_count": 0,
            "discard_count": 0,
        }

    @classmethod
    def with_options(
        cls,
        factory: Callable[[], T],
        reset: Callable[[T], None] | None = None,
        max_size: int = 10,
        initial_size: int = 0,
    ) -> ObjectPool[T]:
        pool = cls(factory, reset, max_size)
        for _ in range(initial_size):
            pool._pool.append(factory())
        return pool

    def acquire(self) -> T:
        self._stats["acquire_count"] += 1
        if self._pool:
            self._stats["hit_count"] += 1
            return self._pool.pop()
        self._stats["miss_count"] += 1
        return self._factory()

    def release(self, obj: T) -> None:
        self._stats["release_count"] += 1
        if len(self._pool) < self._max_size:
            if self._reset is not None:
                self._reset(obj)
            self._pool.append(obj)
        else:
            self._stats["discard_count"] += 1

    def use(self, fn: Callable[[T], Any]) -> Any:
        obj = self.acquire()
        try:
            return fn(obj)
        finally:
            self.release(obj)

    async def use_async(self, fn: Callable[[T], Any]) -> Any:
        obj = self.acquire()
        try:
            return await fn(obj)
        finally:
            self.release(obj)

    def clear(self) -> None:
        self._pool.clear()

    @property
    def size(self) -> int:
        return len(self._pool)

    @property
    def max_size(self) -> int:
        return self._max_size

    def get_stats(self) -> dict:
        total = self._stats["acquire_count"]
        return {
            **self._stats,
            "hit_rate": self._stats["hit_count"] / total if total > 0 else 0.0,
            "current_size": len(self._pool),
        }

    def reset_stats(self) -> None:
        for k in self._stats:
            self._stats[k] = 0
