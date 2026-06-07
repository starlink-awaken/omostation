"""LLM Gateway v0.4 — unified LLM provider abstraction layer.

Stable Public API
=================

Core types (always available):
  * :class:`LLMProvider` — abstract base class for providers
  * :class:`LLMRequest` — request dataclass
  * :class:`LLMResponse` — response dataclass (includes token tracking)

Provider discovery:
  * :func:`detect_backends` — auto-detect available LLM providers
  * :func:`create_provider` — create a specific provider by name

Error types:
  * :exc:`LLMError` — base exception
  * :exc:`LLMRetryExhaustedError` — retry exhausted

Tool types:
  * :class:`ToolSchema` — tool definition schema
  * :class:`ToolCall` — tool call in request
  * :class:`ToolResult` — tool result in response

Backward Compatibility
======================

For minerva/ssot/ontoderive consumers, use:
  * :mod:`llm_gateway.compat` — legacy provider aliases

Version: 0.4.0
"""

import builtins  # noqa: F401

from .detection import create_provider, detect_backends
from .provider import (
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMRetryExhaustedError,
    MockLLMProvider,
    NoneProvider,
    ToolCall,
    ToolResult,
    ToolSchema,
)
from .providers.anthropic_provider import AnthropicProvider
from .providers.deepseek_provider import DeepSeekProvider
from .providers.gemini_provider import GeminiProvider
from .providers.hitl_provider import HitlLLMProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider
from .ssot_loader import load_ssot_models

__version__ = "0.4.0"

__all__ = (  # noqa: RUF022
    # ── Stable public API ──
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMError",
    "LLMRetryExhaustedError",
    "ToolSchema",
    "ToolCall",
    "ToolResult",
    "create_provider",
    "detect_backends",
    "load_ssot_models",
    # ── Concrete providers ──
    "AnthropicProvider",
    "DeepSeekProvider",
    "GeminiProvider",
    "HitlLLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    # ── Testing ──
    "MockLLMProvider",
    "NoneProvider",
)
