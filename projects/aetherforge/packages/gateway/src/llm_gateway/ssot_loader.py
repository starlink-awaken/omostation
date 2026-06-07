import glob
import os
from collections.abc import AsyncIterator
from typing import Any

import yaml

from .provider import LLMRequest
from .providers.base import BaseLLMProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider
from .registry import ModelRegistry
from .types import ChatOptions, ChatResult, ModelDescriptor, StreamChunk


class SSOTProviderAdapter(BaseLLMProvider):
    """Adapter to map an L0 M1 compute_engine config to BaseLLMProvider."""

    def __init__(self, m1_config: dict):
        self._config = m1_config
        self._name = m1_config.get("id", "unknown")
        self._type = m1_config.get("engine_type", "unknown")
        self.base_url = m1_config.get("base_url")
        self.cost_multiplier = float(m1_config.get("cost_multiplier", 1.0))
        self.protocols = m1_config.get("supported_protocols", [])

        self._underlying = None
        if "openai" in self.protocols:
            self._underlying = OpenAIProvider(base_url=self.base_url)
            self._provider_type = "openai"
        elif self._type == "local_daemon" or "ollama" in self.protocols:
            self._underlying = OllamaProvider(base_url=self.base_url)
            self._provider_type = "ollama"
        else:
            self._provider_type = "unknown"

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_type(self) -> str:
        return self._provider_type

    async def discover(self) -> list[ModelDescriptor]:
        if not self._underlying:
            return []

        model_names = self._underlying.available_models()
        cost = {"input": self.cost_multiplier, "output": self.cost_multiplier}

        descriptors = []
        for m in model_names:
            descriptors.append(
                ModelDescriptor(
                    id=f"{self.name}/{m}",
                    name=m,
                    provider=self.name,
                    capabilities=["chat"],
                    cost_per_1k_tokens=cost,
                )
            )
        return descriptors

    def _build_request(self, model: str, messages: list[dict[str, Any]], options: ChatOptions | None) -> LLMRequest:
        real_model = model.split("/")[-1] if "/" in model else model

        context = list(messages)
        prompt = ""
        if context and context[-1].get("role") == "user":
            prompt = context.pop()["content"]

        sys_prompts = [msg["content"] for msg in context if msg.get("role") == "system"]
        sys_prompt = "\n".join(sys_prompts)
        context = [msg for msg in context if msg.get("role") != "system"]

        req = LLMRequest(
            prompt=prompt or " ",
            system_prompt=sys_prompt,
            model=real_model,
            context=context,
        )
        if options:
            if options.temperature is not None:
                req.temperature = options.temperature
            if options.max_tokens is not None:
                req.max_tokens = options.max_tokens
        return req

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        if not self._underlying:
            raise RuntimeError(f"Provider {self.name} has no underlying implementation.")

        req = self._build_request(model, messages, options)
        resp = await self._underlying.generate(req)

        return ChatResult(
            id="",
            model=model,
            content=resp.content,
            finish_reason=resp.finish_reason,
            usage={"prompt_tokens": resp.input_tokens, "completion_tokens": resp.output_tokens},
        )

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if not self._underlying:
            raise RuntimeError(f"Provider {self.name} has no underlying implementation.")

        req = self._build_request(model, messages, options)

        async for chunk_text in self._underlying.stream_generate(req):
            yield StreamChunk(
                model=model,
                content=chunk_text,
            )


def load_ssot_models(registry: ModelRegistry, m1_dir: str) -> None:
    """Load L0 M1 models from YAML and register them into the given ModelRegistry."""
    pattern = os.path.join(m1_dir, "*.yaml")
    for filepath in glob.glob(pattern):
        with open(filepath) as f:
            try:
                config = yaml.safe_load(f)
            except Exception as e:
                import logging
                logging.warning(f"Failed to load yaml {filepath}: {e}")
                continue

            if config and isinstance(config, dict):
                if config.get("type") == "compute_engine" and config.get("status") == "active":
                    provider = SSOTProviderAdapter(config)
                    registry.register(provider)
