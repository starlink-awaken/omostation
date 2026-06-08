"""Anthropic provider — Claude Messages API (optional anthropic SDK).

Environment variables:
    ANTHROPIC_API_KEY:  Anthropic API key.

The provider is unavailable when:
- ``api_key`` is empty or ``"MOCK_KEY"``
- The ``anthropic`` package is not installed
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    _with_llm_retry,
)

_log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Claude API provider via the ``anthropic`` SDK (optional dependency)."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def available_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
        ]

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        super().__init__()
        self._api_key: str = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.default_model: str = default_model
        self._client: Any | None = None
        self._async_client: Any | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if not self._api_key or self._api_key == "MOCK_KEY":
            return False
        try:
            import anthropic  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            _log.debug("anthropic SDK not installed — AnthropicProvider unavailable")
            return False

    # ------------------------------------------------------------------
    # Clients (lazy)
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _get_async_client(self) -> Any:
        if self._async_client is None:
            import anthropic

            self._async_client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._async_client

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_async_client()
            messages: list[dict] = list(request.context) + [{"role": "user", "content": request.prompt}]  # noqa: RUF005
            model = request.model or self.default_model
            response = await client.messages.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens=request.max_tokens,
                system=request.system_prompt or "You are a helpful assistant.",
                messages=messages,
            )
            content: str = response.content[0].text if response.content else ""
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason or "stop",
            )
        except Exception as exc:
            _log.error("AnthropicProvider.generate failed: %s", exc)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()
            messages: list[dict] = list(request.context) + [{"role": "user", "content": request.prompt}]  # noqa: RUF005
            model = request.model or self.default_model
            response = _with_llm_retry(
                lambda: client.messages.create(  # type: ignore[attr-defined]
                    model=model,
                    max_tokens=request.max_tokens,
                    system=request.system_prompt or "You are a helpful assistant.",
                    messages=messages,
                ),
                max_retries=3,
                base_delay=1.0,
            )
            content: str = response.content[0].text if response.content else ""
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason or "stop",
            )
        except Exception as exc:
            _log.error("AnthropicProvider.complete failed: %s", exc)
            raise

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            client = self._get_async_client()
            model = request.model or self.default_model
            messages: list[dict] = list(request.context) + [{"role": "user", "content": request.prompt}]  # noqa: RUF005
            async with client.messages.stream(  # type: ignore[attr-defined]
                model=model,
                max_tokens=request.max_tokens,
                system=request.system_prompt or "You are a helpful assistant.",
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            _log.error("AnthropicProvider.stream_generate failed: %s", exc)
            raise
