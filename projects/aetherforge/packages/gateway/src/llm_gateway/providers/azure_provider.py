"""Azure OpenAI provider — GPT-4o/turbo via Azure OpenAI Service.

Environment variables:
    AZURE_OPENAI_API_KEY:     Azure OpenAI API key.
    AZURE_OPENAI_ENDPOINT:    Azure OpenAI endpoint (e.g. ``https://xxx.openai.azure.com``).
    AZURE_OPENAI_API_VERSION: API version (default ``2024-10-01-preview``).
    AZURE_OPENAI_DEPLOYMENT:  Default deployment name (default ``gpt-4o``).

Uses the ``openai`` SDK with Azure-specific configuration.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)

_AZURE_DEFAULT_API_VERSION = "2024-10-01-preview"


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider via the ``openai`` SDK with Azure endpoint."""

    @property
    def provider_name(self) -> str:
        return "azure"

    def available_models(self) -> list[str]:
        return [
            os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            "gpt-4o-mini",
            "gpt-4-turbo",
        ]

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        api_version: str | None = None,
        deployment: str | None = None,
    ) -> None:
        super().__init__()
        self._api_key: str = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self._endpoint: str = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self._api_version: str = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", _AZURE_DEFAULT_API_VERSION)
        self._deployment: str = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.default_model: str = self._deployment
        self._client: Any | None = None
        self._async_client: Any | None = None

    def is_available(self) -> bool:
        if not self._api_key or self._api_key == "MOCK_KEY":
            return False
        if not self._endpoint:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self) -> Any:
        if self._client is None:
            import openai
            self._client = openai.AzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._endpoint,
                api_version=self._api_version,
            )
        return self._client

    def _get_async_client(self) -> Any:
        if self._async_client is None:
            import openai
            self._async_client = openai.AsyncAzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._endpoint,
                api_version=self._api_version,
            )
        return self._async_client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = self._get_async_client()
        model = request.model or self.default_model

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            kwargs["messages"].insert(0, {"role": "system", "content": request.system_prompt})
        if request.stop_sequences:
            kwargs["stop"] = request.stop_sequences

        try:
            resp = await client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                provider="azure",
                model=model,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
                finish_reason=choice.finish_reason or "stop",
            )
        except Exception as e:
            _log.error("Azure OpenAI generate failed: %s", e)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        model = request.model or self.default_model

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            kwargs["messages"].insert(0, {"role": "system", "content": request.system_prompt})

        try:
            resp = client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                provider="azure",
                model=model,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
                finish_reason=choice.finish_reason or "stop",
            )
        except Exception as e:
            _log.error("Azure OpenAI complete failed: %s", e)
            raise

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        client = self._get_async_client()
        model = request.model or self.default_model
        messages = [{"role": "user", "content": request.prompt}]
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})

        try:
            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True,
                max_tokens=request.max_tokens, temperature=request.temperature,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            _log.error("Azure OpenAI stream failed: %s", e)
            raise
