"""DeepSeek provider — DeepSeek API via OpenAI-compatible interface.

Extends OpenAIProvider with DeepSeek-specific defaults:
  - base_url: https://api.deepseek.com/v1
  - default_model: deepseek-chat (or BOS_DEEPSEEK_MODEL env)

Environment variables:
    DEEPSEEK_API_KEY:  DeepSeek API key
    BOS_DEEPSEEK_MODEL:  Model name (default: deepseek-chat)
"""

from __future__ import annotations

import logging
import os

from .openai_provider import OpenAIProvider

_log = logging.getLogger(__name__)


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek LLM provider via OpenAI-compatible API.

    Extends OpenAIProvider with DeepSeek-specific defaults.
    """

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def available_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner"]

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        _api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        _model = default_model or os.environ.get("BOS_DEEPSEEK_MODEL", "deepseek-chat")
        _base_url = base_url or "https://api.deepseek.com/v1"
        super().__init__(api_key=_api_key, default_model=_model, base_url=_base_url)
        self._api_key = _api_key

    def is_available(self) -> bool:
        if not self._api_key or self._api_key == "MOCK_KEY":
            return False
        try:
            import openai  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            _log.debug("openai SDK not installed — DeepSeekProvider unavailable")
            return False
