"""Ollama provider — local LLM via REST API.

Uses ``requests`` for synchronous calls and ``httpx`` (when available)
for asynchronous / streaming calls.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    _with_llm_retry,
)

_log = logging.getLogger(__name__)

_OLLAMA_DEFAULT_MODEL = "llama3"
_OLLAMA_DEFAULT_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Local Ollama provider via the Ollama REST API."""

    @property
    def provider_name(self) -> str:
        return "ollama"

    def available_models(self) -> list[str]:
        return [_OLLAMA_DEFAULT_MODEL]

    def __init__(
        self,
        base_url: str = _OLLAMA_DEFAULT_URL,
        default_model: str = _OLLAMA_DEFAULT_MODEL,
    ) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401

            return True
        except ImportError:
            _log.debug("requests SDK not installed — OllamaProvider unavailable")
            return False

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": self._build_messages(request),
                        "stream": False,
                        "options": self._build_options(request),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return LLMResponse(
                    content=content,
                    provider=self.provider_name,
                    model=model,
                    input_tokens=data.get("prompt_eval_count", 0) or 0,
                    output_tokens=data.get("eval_count", 0) or 0,
                )
        except ImportError:
            # Fall back to requests + asyncio.to_thread
            import asyncio

            return await asyncio.to_thread(self._sync_generate_raw, request)
        except Exception as exc:
            _log.error("OllamaProvider.generate failed: %s", exc)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        try:
            import requests

            resp = _with_llm_retry(
                lambda: requests.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": self._build_messages(request),
                        "stream": False,
                        "options": self._build_options(request),
                    },
                    timeout=60,
                ),
                max_retries=3,
                base_delay=1.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=model,
                input_tokens=data.get("prompt_eval_count", 0) or 0,
                output_tokens=data.get("eval_count", 0) or 0,
            )
        except Exception as exc:
            _log.error("OllamaProvider.complete failed: %s", exc)
            return LLMResponse(
                content=f"[Ollama error: {exc}]",
                provider=self.provider_name,
                model=model,
            )

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        try:
            import httpx

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": self._build_messages(request),
                        "stream": True,
                        "options": self._build_options(request),
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        import json

                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        msg = chunk.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            yield content
        except Exception as exc:
            _log.error("OllamaProvider.stream_generate failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(self, request: LLMRequest) -> list[dict]:
        messages: list[dict] = list(request.context)
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def _build_options(self, request: LLMRequest) -> dict:
        options: dict = {
            "temperature": request.temperature,
        }
        if request.stop_sequences:
            options["stop"] = request.stop_sequences
        return options

    def _sync_generate_raw(self, request: LLMRequest) -> LLMResponse:
        """Sync fallback using ``requests`` (no httpx available)."""
        model = request.model or self.default_model
        import requests

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": self._build_messages(request),
                "stream": False,
                "options": self._build_options(request),
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=model,
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )
