"""Model Registry — provider and model lifecycle management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from .circuit_breaker import CircuitBreakerRegistry
from .providers.base import BaseLLMProvider
from .retry import RetryConfig, with_retry
from .types import ChatOptions, ChatResult, ModelDescriptor, StreamChunk

_log = logging.getLogger(__name__)


class ModelRegistry:
    """Registry managing providers, discovered models, circuit breakers, and retry.

    Integrates circuit breakers per-provider and optional retry logic.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseLLMProvider] = {}
        self._models: dict[str, tuple[ModelDescriptor, str]] = {}
        self.circuit_breaker = CircuitBreakerRegistry()
        self.retry_config: RetryConfig | None = None
        self._scheduler_ref: Any = None

    # ------------------------------------------------------------------
    # Provider registration
    # ------------------------------------------------------------------

    def register(self, provider: BaseLLMProvider) -> None:
        """Register a single provider."""
        self._providers[provider.name] = provider

    def register_many(self, providers: list[BaseLLMProvider]) -> None:
        """Register multiple providers."""
        for p in providers:
            self.register(p)

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

    async def refresh(self) -> list[ModelDescriptor]:
        """Discover models from all registered providers."""
        self._models.clear()
        all_models: list[ModelDescriptor] = []
        tasks = [(name, provider.discover()) for name, provider in self._providers.items()]
        results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
        for (name, _), result in zip(tasks, results):
            if isinstance(result, BaseException):
                _log.warning("[ModelRegistry] discover failed for %s: %s", name, result)
                continue
            for m in result:
                self._models[m.id] = (m, name)
                all_models.append(m)
        return all_models

    # ------------------------------------------------------------------
    # Model queries
    # ------------------------------------------------------------------

    def get_all(self) -> list[ModelDescriptor]:
        """Return all discovered models."""
        return [entry[0] for entry in self._models.values()]

    def list_models(self) -> list[ModelDescriptor]:
        """Legacy alias for get_all()."""
        return self.get_all()

    def get(self, model_id: str) -> ModelDescriptor | None:
        """Get a single model descriptor by ID."""
        entry = self._models.get(model_id)
        return entry[0] if entry else None

    # ------------------------------------------------------------------
    # Chat / streaming
    # ------------------------------------------------------------------

    def _get_provider_for(self, model_id: str) -> tuple[BaseLLMProvider, str] | None:
        entry = self._models.get(model_id)
        if not entry:
            return None
        _, provider_name = entry
        provider = self._providers.get(provider_name)
        if not provider:
            return None
        if not self.circuit_breaker.can_request(provider_name):
            raise RuntimeError(f"Circuit breaker open for provider {provider_name}")
        return provider, provider_name

    async def chat(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult | None:
        """Send a chat request through the registry with circuit breaker and retry."""
        p = self._get_provider_for(model_id)
        if not p:
            return None
        provider, provider_name = p
        try:
            if self.retry_config:
                result = await with_retry(
                    lambda: provider.chat(model_id, messages, options),
                    config=self.retry_config,
                )
            else:
                result = await provider.chat(model_id, messages, options)
            self.circuit_breaker.record_success(provider_name)
            return result
        except Exception:
            self.circuit_breaker.record_failure(provider_name)
            raise
        finally:
            if self._scheduler_ref is not None:
                self._scheduler_ref.release_load(model_id)

    async def chat_stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat response through the registry."""
        p = self._get_provider_for(model_id)
        if not p:
            raise RuntimeError(f"Model {model_id} not found or provider unavailable")
        provider, provider_name = p
        try:
            try:
                async for chunk in provider.stream(model_id, messages, options):  # type: ignore[attr-defined]
                    yield chunk
            except NotImplementedError:
                result = await provider.chat(model_id, messages, options)
                yield StreamChunk(
                    id=result.id,
                    model=result.model,
                    content=result.content,
                    finish_reason=result.finish_reason,
                )
            self.circuit_breaker.record_success(provider_name)
        except Exception:
            self.circuit_breaker.record_failure(provider_name)
            raise
        finally:
            if self._scheduler_ref is not None:
                self._scheduler_ref.release_load(model_id)

    # ------------------------------------------------------------------
    # Scheduler linkage
    # ------------------------------------------------------------------

    def set_scheduler(self, scheduler: Any) -> None:
        """Attach a scheduler for load tracking."""
        self._scheduler_ref = scheduler

    # ------------------------------------------------------------------
    # Provider access
    # ------------------------------------------------------------------

    def get_provider(self, model_id: str) -> BaseLLMProvider | None:
        """Get the provider that owns a model."""
        entry = self._models.get(model_id)
        if not entry:
            return None
        return self._providers.get(entry[1])

    def get_providers(self) -> list[BaseLLMProvider]:
        """Return all registered providers."""
        return list(self._providers.values())

    async def health_check(self, provider_name: str) -> bool:
        """Check health of a specific provider by name."""
        provider = self._providers.get(provider_name)
        if not provider:
            return False
        return await provider.health()
