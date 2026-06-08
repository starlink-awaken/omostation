from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..types import ChatOptions, ChatResult, ModelDescriptor, StreamChunk


class BaseLLMProvider(ABC):
    """Abstract base class for LLM model providers.

    .. deprecated::
        Use :class:`llm_gateway.provider.LLMProvider` instead.
        This class is kept for backward compatibility with
        ``registry.py`` and legacy adapter providers.

    Prefer :mod:`llm_gateway.provider` for new provider implementations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider type string."""

    @abstractmethod
    async def discover(self) -> list[ModelDescriptor]:
        """Discover available models from this provider."""

    async def health(self) -> bool:
        """Check if the provider is healthy. Override for custom checks."""
        return True

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        """Send a chat completion request and return the result."""

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion. Default: one-shot then stop.
        Override for true streaming providers.
        """
        result = await self.chat(model, messages, options)
        yield StreamChunk(
            id=result.id,
            model=result.model,
            content=result.content,
            finish_reason=result.finish_reason,
        )

    def configure(self, **kwargs: Any) -> None:
        """Configure the provider. Default no-op."""
