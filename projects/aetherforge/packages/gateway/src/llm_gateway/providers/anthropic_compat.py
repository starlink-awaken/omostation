"""AnthropicCompatProvider — 通用 Anthropic API 兼容 Provider。

用于通过 Anthropic 兼容接口访问的第三方 Provider:
  - MiniMax (api.minimaxi.com/anthropic)
  - Zhipu GLM (open.bigmodel.cn/api/anthropic)
  - Kimi (api.kimi.com/coding)
  - 其他 Anthropic 兼容服务

用法::
    from llm_gateway.providers.anthropic_compat import AnthropicCompatProvider
    p = AnthropicCompatProvider(
        name="minimax",
        api_key="sk-xxx",
        base_url="https://api.minimaxi.com/anthropic",
        default_model="MiniMax-M2.7",
    )
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)


class AnthropicCompatProvider(LLMProvider):
    """通用 Anthropic 兼容 API Provider。

    通过 ``name`` 区分不同的第三方服务。
    """

    def __init__(
        self,
        name: str = "anthropic-compat",
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "claude-3-haiku-20240307",
    ) -> None:
        super().__init__()
        self._name = name
        self._api_key = api_key or ""
        self._base_url = base_url or ""
        self._default_model = default_model

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return self._default_model

    def available_models(self) -> list[str]:
        return [self._default_model]

    def is_available(self) -> bool:
        return bool(self._api_key) and bool(self._base_url)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def _build_body(self, request: LLMRequest) -> dict[str, Any]:
        messages = [{"role": "user", "content": request.prompt}]
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})

        body: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature:
            body["temperature"] = request.temperature
        return body

    def _parse_response(self, data: dict[str, Any], model: str) -> LLMResponse:
        content = ""
        input_tokens = 0
        output_tokens = 0

        content_blocks = data.get("content", [])
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    content += block.get("text", "")
        else:
            content = str(content_blocks)

        usage = data.get("usage", {})
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

        return LLMResponse(
            content=content or data.get("content", {}).get("text", ""),
            provider=self._name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=data.get("stop_reason", "stop"),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import httpx
        body = self._build_body(request)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    headers=self._build_headers(),
                    json=body,
                )
                resp.raise_for_status()
                return self._parse_response(resp.json(), request.model or self._default_model)
        except Exception as e:
            _log.error("%s generate failed: %s", self._name, e)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        import httpx
        body = self._build_body(request)
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self._base_url}/messages",
                    headers=self._build_headers(),
                    json=body,
                )
                resp.raise_for_status()
                return self._parse_response(resp.json(), request.model or self._default_model)
        except Exception as e:
            _log.error("%s complete failed: %s", self._name, e)
            raise
