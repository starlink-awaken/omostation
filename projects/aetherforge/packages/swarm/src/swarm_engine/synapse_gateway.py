"""GatewaySynapse — bridges aetherforge-gateway providers into the swarm.

Allows the swarm engine to use the gateway's unified provider layer
(Ollama, OpenAI, Anthropic, etc.) instead of its own native synapses.

This is a "strangler fig" adapter — existing synapse_*.py files remain
for backward compatibility; new code should use GatewaySynapse.
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class GatewaySynapse:
    """Swarm-compatible synapse that delegates to aetherforge-gateway's providers.

    Usage::

        from swarm_engine.synapse_gateway import GatewaySynapse

        synapse = GatewaySynapse()

        # List available models across all providers
        models = synapse.discover_models()

        # Generate text (auto-selects best provider)
        result = synapse.generate("llama3", "Hello!")

        # Use a specific provider
        result = synapse.generate("gpt-4", "Hello!", provider="openai")
    """

    def __init__(self) -> None:
        self.status = "active"

    # ── Provider access ───────────────────────────────────────────────────────

    @staticmethod
    def _get_provider(provider_name: str = ""):
        """Get a gateway provider by name, or the first available."""
        from llm_gateway.detection import create_provider, detect_backends

        if provider_name:
            provider = create_provider(provider_name)
            if provider and provider.is_available():
                return provider

        backends = detect_backends()
        return backends[0] if backends else None

    # ── Synapse-compatible API ────────────────────────────────────────────────

    def discover_models(self) -> list[dict[str, Any]]:
        """Discover available models across all providers.

        Returns a list of dicts compatible with synapse expectations::

            [{"name": "llama3", "provider": "ollama", ...}]
        """
        from llm_gateway.detection import detect_backends

        models: list[dict[str, Any]] = []
        for provider in detect_backends():
            provider_name = provider.provider_name
            for model_name in provider.available_models():
                models.append({
                    "name": model_name,
                    "provider": provider_name,
                    "status": "available",
                })
        return models

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> dict[str, Any]:
        """Execute text generation via the gateway provider layer.

        Args:
            model: Model name (e.g. ``"llama3"``, ``"gpt-4"``).
            prompt: The user prompt.
            system: Optional system prompt.
            options: Optional dict with ``temperature``, ``max_tokens``, etc.

        Returns:
            A dict with keys ``"response"`` (str), ``"model"`` (str),
            ``"provider"`` (str), ``"tokens_in"`` (int), ``"tokens_out"`` (int).
        """
        from llm_gateway.detection import create_provider, detect_backends
        from llm_gateway.provider import LLMRequest

        # Try to find a provider that has this model
        provider = None
        for p in detect_backends():
            if model in p.available_models() or not provider:
                provider = p

        if not provider or not provider.is_available():
            return {
                "status": "error",
                "message": f"No available provider for model '{model}'",
            }

        req = LLMRequest(
            prompt=prompt,
            model=model or getattr(provider, "default_model", ""),
            system_prompt=system or "",
            max_tokens=(options or {}).get("max_tokens", 1024),
            temperature=(options or {}).get("temperature", 0.7),
        )

        try:
            resp = provider.complete(req)
            return {
                "status": "success",
                "response": resp.content,
                "model": resp.model or model,
                "provider": resp.provider or provider.provider_name,
                "tokens_in": resp.input_tokens,
                "tokens_out": resp.output_tokens,
                "finish_reason": resp.finish_reason,
            }
        except Exception as e:
            _log.exception("GatewaySynapse generate failed")
            return {"status": "error", "message": str(e)}

    # ── Health ────────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Report health status of the gateway provider layer."""
        from llm_gateway.detection import detect_backends

        providers = detect_backends()
        return {
            "status": "active",
            "providers": [
                {"name": p.provider_name, "available": p.is_available()}
                for p in providers
            ],
            "total_available": sum(1 for p in providers if p.is_available()),
        }
