"""Engine LLM — provider selection, retry, caching, batcher, rate limiter.

Ported from agentmesh llm/ subsystem.

"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterable
from typing import Any, Protocol

from runtime.executor.engine_types import (
    CacheConfig,
    CompletionChunk,
    CompletionOptions,
    CompletionRequest,
    CompletionResult,
    ProviderConfig,
    RateLimitConfig,
)

# ====================================================================
# LLM Provider Protocol
# ====================================================================


class LLMProvider(Protocol):
    """Protocol for LLM providers (Claude, OpenAI, custom)."""

    name: str
    provider_type: str

    async def complete(self, prompt: str, options: CompletionOptions | None = None) -> CompletionResult: ...

    async def stream(self, prompt: str, options: CompletionOptions | None = None) -> AsyncIterable[CompletionChunk]: ...

    async def is_available(self) -> bool: ...

    def get_config(self) -> ProviderConfig: ...


class ResponseCache:
    """LRU cache for LLM responses with TTL expiration."""

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._cache: OrderedDict[str, CompletionResult] = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _make_key(self, prompt: str, options: CompletionOptions | None) -> str:
        return f"{hash(prompt)}:{hash(str(options)) if options else ''}"

    def get(self, prompt: str, options: CompletionOptions | None = None) -> CompletionResult | None:
        if not self._config.enabled or (options and options.skip_cache):
            self._misses += 1
            return None
        key = self._make_key(prompt, options)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        now_ms = time.time() * 1000
        if now_ms - self._timestamps.get(key, 0) > self._config.ttl_ms:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
            self._evictions += 1
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        result = CompletionResult(
            content=entry.content,
            model=entry.model,
            provider=entry.provider,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            total_tokens=entry.total_tokens,
            cached=True,
        )
        return result

    def set(self, prompt: str, result: CompletionResult, options: CompletionOptions | None = None) -> None:
        if not self._config.enabled:
            return
        key = self._make_key(prompt, options)
        self._cache[key] = result
        self._timestamps[key] = time.time() * 1000
        while len(self._cache) > self._config.max_size:
            self._cache.popitem(last=False)
            self._evictions += 1

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "size": len(self._cache),
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }

    def clear(self) -> None:
        self._cache.clear()
        self._timestamps.clear()


class RateLimiter:
    """Token-bucket rate limiter for LLM API calls."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._tokens: float = float(self._config.requests_per_minute)
        self._last_refill: float = time.time()

    async def acquire(self) -> bool:
        if not self._config.enabled:
            return True
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    async def wait_and_acquire(self) -> None:
        while not await self.acquire():
            await asyncio.sleep(0.1)

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        rate = self._config.requests_per_minute / 60.0
        self._tokens = min(float(self._config.requests_per_minute), self._tokens + elapsed * rate)
        self._last_refill = now


class TokenTracker:
    """Track token usage across providers."""

    def __init__(self) -> None:
        self._usage: dict[str, dict[str, int]] = {}

    def record(self, provider: str, input_tokens: int, output_tokens: int) -> None:
        if provider not in self._usage:
            self._usage[provider] = {"input": 0, "output": 0}
        self._usage[provider]["input"] += input_tokens
        self._usage[provider]["output"] += output_tokens

    def report(self) -> dict[str, Any]:
        total_input = sum(v["input"] for v in self._usage.values())
        total_output = sum(v["output"] for v in self._usage.values())
        return {
            "by_provider": dict(self._usage),
            "total": {"input": total_input, "output": total_output},
        }

    def reset(self) -> None:
        self._usage.clear()


class ProviderManager:
    """Manage LLM provider registration, selection, and failover."""

    def __init__(self, primary_provider: str = "simulation") -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._primary = primary_provider

    def register(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str | None = None) -> LLMProvider:
        provider_name = name or self._primary
        provider = self._providers.get(provider_name)
        if provider is None:
            msg = f"Provider not found: {provider_name}"
            raise ValueError(msg)
        return provider

    def set_primary(self, name: str) -> None:
        if name not in self._providers:
            raise ValueError(f"Provider not found: {name}")
        self._primary = name

    async def get_available(self) -> LLMProvider | None:
        primary = self._providers.get(self._primary)
        if primary is not None and await primary.is_available():
            return primary
        for name, provider in self._providers.items():
            if name != self._primary and await provider.is_available():
                return provider
        return None

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def clear(self) -> None:
        self._providers.clear()


class RequestBatcher:
    """Batch multiple LLM requests into one for efficiency."""

    def __init__(self, max_batch_size: int = 10, max_wait_ms: int = 100) -> None:
        self._max_batch_size = max_batch_size
        self._max_wait_ms = max_wait_ms
        self._queue: list[tuple[CompletionRequest, asyncio.Future[CompletionResult]]] = []
        self._timer: asyncio.TimerHandle | None = None

    async def submit(self, request: CompletionRequest) -> CompletionResult:
        future: asyncio.Future[CompletionResult] = asyncio.get_event_loop().create_future()
        self._queue.append((request, future))
        if len(self._queue) >= self._max_batch_size:
            await self._flush()
        elif self._timer is None:
            loop = asyncio.get_event_loop()
            self._timer = loop.call_later(self._max_wait_ms / 1000.0, lambda: asyncio.ensure_future(self._flush()))
        return await future

    async def _flush(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        batch = self._queue[:]
        self._queue.clear()
        if not batch:
            return
        for req, future in batch:
            if not future.done():
                future.set_exception(RuntimeError("Batch processing not implemented"))
