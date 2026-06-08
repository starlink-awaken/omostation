"""Auto-detection of available LLM backends.

Inspired by ontoderive's ``detect_backend()`` and ssot's ``_detect_backends()``.

Priority:
  1. ``LLM_PROVIDER`` environment variable (explicit choice)
  2. Explicit configuration passed to :func:`create_provider`
  3. Environment sniffing (API key env vars)

Usage::

    from .detection import detect_backends, create_provider

    # Auto-detect all available providers
    providers = detect_backends()

    # Create a specific provider with explicit config
    provider = create_provider("openai", api_key="sk-...")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .provider import LLMProvider, NoneProvider

_log = logging.getLogger(__name__)


# Mapping of provider name → (import path, class name, needed env vars)
_PROVIDER_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "openai": (
        "llm_gateway.providers.openai_provider",
        "OpenAIProvider",
        ["OPENAI_API_KEY"],
    ),
    "anthropic": (
        "llm_gateway.providers.anthropic_provider",
        "AnthropicProvider",
        ["ANTHROPIC_API_KEY"],
    ),
    "gemini": (
        "llm_gateway.providers.gemini_provider",
        "GeminiProvider",
        ["GOOGLE_API_KEY"],
    ),
    "deepseek": (
        "llm_gateway.providers.deepseek_provider",
        "DeepSeekProvider",
        ["DEEPSEEK_API_KEY"],
    ),
    "ollama": (
        "llm_gateway.providers.ollama_provider",
        "OllamaProvider",
        [],
    ),
    "hitl": (
        "llm_gateway.providers.hitl_provider",
        "HitlLLMProvider",
        [],
    ),
    "azure": (
        "llm_gateway.providers.azure_provider",
        "AzureOpenAIProvider",
        ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    ),
    "bedrock": (
        "llm_gateway.providers.bedrock_provider",
        "BedrockProvider",
        ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    ),
    "vertex": (
        "llm_gateway.providers.vertex_provider",
        "VertexAIProvider",
        ["GOOGLE_CLOUD_PROJECT"],
    ),
    "minimax": (
        "llm_gateway.providers.anthropic_compat",
        "AnthropicCompatProvider",
        [],
    ),
    "zhipu": (
        "llm_gateway.providers.anthropic_compat",
        "AnthropicCompatProvider",
        [],
    ),
    "kimi": (
        "llm_gateway.providers.anthropic_compat",
        "AnthropicCompatProvider",
        [],
    ),
}


def _import_provider_class(provider_type: str) -> type[LLMProvider] | None:
    """Dynamically import a provider class by name."""
    entry = _PROVIDER_REGISTRY.get(provider_type)
    if entry is None:
        return None
    module_path, class_name, _ = entry
    try:
        import importlib

        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except ImportError:
        _log.debug("Could not import %s from %s", class_name, module_path)
        return None


def create_provider(provider_type: str, **kwargs: Any) -> LLMProvider:
    """Factory method to instantiate a provider by name.

    Parameters
    ----------
    provider_type:
        One of ``"openai"``, ``"anthropic"``, ``"gemini"``,
        ``"deepseek"``, ``"ollama"``, ``"hitl"``.
    **kwargs:
        Forwarded to the provider constructor (e.g. ``api_key``,
        ``default_model``, ``base_url``).

    Returns
    -------
    An LLMProvider instance. Returns ``NoneProvider`` if the provider
    type is unknown or its dependencies cannot be imported.
    """
    cls = _import_provider_class(provider_type)
    if cls is None:
        _log.warning("Unknown provider type: %s", provider_type)
        return NoneProvider()
    try:
        return cls(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:
        _log.warning("Failed to instantiate provider %s: %s", provider_type, exc)
        return NoneProvider()


def detect_backends() -> list[LLMProvider]:
    """Auto-detect available LLM backends and return a prioritized list.

    Detection priority:
      1. If ``LLM_PROVIDER`` env var is set, only that provider is
         returned (if available).
      2. Otherwise, probe each registered provider by checking its
         required environment variables and SDK availability.

    Returns
    -------
    A list of :class:`LLMProvider` instances ready for use, ordered by
    priority (cloud-first, then local).
    """
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit:
        provider = create_provider(explicit)
        if provider is not None:
            return [provider]
        _log.warning(
            "LLM_PROVIDER=%s specified but could not be created — falling back to auto-detection",
            explicit,
        )

    # Probe priority order: cloud → local → fallback
    priority_order = ["openai", "anthropic", "gemini", "deepseek", "ollama", "hitl"]

    available: list[LLMProvider] = []
    for provider_type in priority_order:
        entry = _PROVIDER_REGISTRY.get(provider_type)
        if entry is None:
            continue
        _, _, needed_envs = entry

        # If env vars are required and missing, skip
        if needed_envs and not any(os.environ.get(var, "").strip() for var in needed_envs):
            continue

        provider = create_provider(provider_type)
        if provider is not None and provider.is_available():
            _log.debug("Detected provider: %s", provider_type)
            available.append(provider)

    if not available:
        _log.info("No LLM backends detected — returning NoneProvider as fallback")
        available.append(NoneProvider())

    return available
