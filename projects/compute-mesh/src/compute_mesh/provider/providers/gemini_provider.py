"""Gemini provider — Google Gemini 1.5/2.0 via google-generativeai SDK.

Environment variables:
    GOOGLE_API_KEY:  Google AI Studio API key.

The provider is unavailable when:
- ``api_key`` is empty or ``"MOCK_KEY"``
- The ``google-generativeai`` package is not installed
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

from ..provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    _with_llm_retry,
)

_log = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider via the ``google-generativeai`` SDK (optional dependency)."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    def available_models(self) -> list[str]:
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._api_key: str = api_key or os.environ.get("GOOGLE_API_KEY", "")

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if not self._api_key or self._api_key == "MOCK_KEY":
            return False
        try:
            import google.generativeai  # type: ignore[import-untyped]  # noqa: F401

            return True
        except ImportError:
            _log.debug("google-generativeai SDK not installed — GeminiProvider unavailable")
            return False

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            import google.generativeai as genai  # type: ignore[import]

            genai.configure(api_key=self._api_key)
            model_name = request.model or self.available_models()[0]
            model = genai.GenerativeModel(model_name)
            response = _with_llm_retry(
                lambda: model.generate_content(request.prompt),
                max_retries=3,
                base_delay=1.0,
            )
            return LLMResponse(
                content=response.text,
                provider=self.provider_name,
                model=model_name,
                input_tokens=getattr(getattr(response, "usage_metadata", None), "prompt_token_count", 0) or 0,
                output_tokens=getattr(getattr(response, "usage_metadata", None), "candidates_token_count", 0) or 0,
                finish_reason="stop",
            )
        except Exception as exc:
            _log.error("GeminiProvider.generate failed: %s", exc)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        # Gemini's SDK doesn't have a clean sync vs async split in the
        # same way — delegate to generate via asyncio.run for the sync path.
        import asyncio

        return asyncio.run(self.generate(request))

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            import google.generativeai as genai  # type: ignore[import]

            genai.configure(api_key=self._api_key)
            model_name = request.model or self.available_models()[0]
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(request.prompt, stream=True)
            for chunk in response:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as exc:
            _log.warning("GeminiProvider.stream_generate failed: %s", exc)
            raise
