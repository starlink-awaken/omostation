"""PricingRegistry — 模型定价注册与查询。

数据来源优先级:
  1. L0 M1 YAML (model/pricing 命名空间)
  2. 内置默认值 (覆盖主流模型)
  3. 用户自定义 (aetherforge.yaml / credentials DB)

用法::

    from llm_gateway.pricing import PricingRegistry

    pricing = PricingRegistry()
    cost = pricing.get_cost("gpt-4o")  # → {"input": 0.0025, "output": 0.01}
    models = pricing.search(capability="vision")  # → 支持 vision 的模型列表
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

M1_MODEL_DIR = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "model"


@dataclass
class ModelPrice:
    """Pricing and capability info for a single model."""

    model_id: str = ""
    provider: str = ""
    display_name: str = ""
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    context_window: int = 4096
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def cost_per_1k(self) -> dict[str, float]:
        return {"input": self.cost_per_1k_input, "output": self.cost_per_1k_output}

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "display_name": self.display_name or self.model_id,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "context_window": self.context_window,
            "capabilities": self.capabilities,
        }


# ── Built-in default pricing (covers most common models) ─────────────────────

_DEFAULT_PRICING: list[dict[str, Any]] = [
    # OpenAI
    {"model_id": "gpt-4o", "provider": "openai", "cost_in": 0.0025, "cost_out": 0.01, "ctx": 128000, "caps": ["chat", "vision", "tools"]},
    {"model_id": "gpt-4o-mini", "provider": "openai", "cost_in": 0.00015, "cost_out": 0.0006, "ctx": 128000, "caps": ["chat", "vision", "tools"]},
    {"model_id": "gpt-4-turbo", "provider": "openai", "cost_in": 0.01, "cost_out": 0.03, "ctx": 128000, "caps": ["chat", "vision"]},
    {"model_id": "gpt-3.5-turbo", "provider": "openai", "cost_in": 0.0005, "cost_out": 0.0015, "ctx": 16384, "caps": ["chat"]},
    # Anthropic
    {"model_id": "claude-3-5-sonnet-20241022", "provider": "anthropic", "cost_in": 0.003, "cost_out": 0.015, "ctx": 200000, "caps": ["chat", "vision"]},
    {"model_id": "claude-3-opus-20240229", "provider": "anthropic", "cost_in": 0.015, "cost_out": 0.075, "ctx": 200000, "caps": ["chat", "vision"]},
    {"model_id": "claude-3-haiku-20240307", "provider": "anthropic", "cost_in": 0.00025, "cost_out": 0.00125, "ctx": 200000, "caps": ["chat"]},
    # Google
    {"model_id": "gemini-1.5-pro", "provider": "gemini", "cost_in": 0.00125, "cost_out": 0.005, "ctx": 1000000, "caps": ["chat", "vision", "embedding"]},
    {"model_id": "gemini-1.5-flash", "provider": "gemini", "cost_in": 0.000075, "cost_out": 0.0003, "ctx": 1000000, "caps": ["chat", "vision"]},
    {"model_id": "gemini-2.0-flash", "provider": "gemini", "cost_in": 0.0001, "cost_out": 0.0004, "ctx": 1000000, "caps": ["chat", "vision", "tools"]},
    # DeepSeek
    {"model_id": "deepseek-chat", "provider": "deepseek", "cost_in": 0.0005, "cost_out": 0.0015, "ctx": 65536, "caps": ["chat"]},
    {"model_id": "deepseek-reasoner", "provider": "deepseek", "cost_in": 0.001, "cost_out": 0.002, "ctx": 65536, "caps": ["chat", "reasoning"]},
    # Ollama (local = free)
    {"model_id": "llama3", "provider": "ollama", "cost_in": 0.0, "cost_out": 0.0, "ctx": 8192, "caps": ["chat"]},
    {"model_id": "llama3.1", "provider": "ollama", "cost_in": 0.0, "cost_out": 0.0, "ctx": 131072, "caps": ["chat"]},
    {"model_id": "qwen3.5:9b", "provider": "ollama", "cost_in": 0.0, "cost_out": 0.0, "ctx": 262144, "caps": ["chat", "tools", "thinking"]},
    {"model_id": "qwen3.5:4b", "provider": "ollama", "cost_in": 0.0, "cost_out": 0.0, "ctx": 262144, "caps": ["chat", "vision", "tools", "thinking"]},
    # HITL
    {"model_id": "human-expert", "provider": "hitl", "cost_in": 999.0, "cost_out": 999.0, "ctx": 999999, "caps": ["chat", "human"]},
]


class PricingRegistry:
    """Central registry for model pricing data.

    Thread-safe. Loads from multiple sources with priority.
    """

    def __init__(self) -> None:
        self._prices: dict[str, ModelPrice] = {}  # key: f"{provider}/{model_id}"
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_defaults()
        self._load_m1_yamls()
        self._loaded = True

    def _load_defaults(self) -> None:
        """Load built-in default pricing."""
        for entry in _DEFAULT_PRICING:
            mp = ModelPrice(
                model_id=entry["model_id"],
                provider=entry["provider"],
                cost_per_1k_input=entry["cost_in"],
                cost_per_1k_output=entry["cost_out"],
                context_window=entry.get("ctx", 4096),
                capabilities=entry.get("caps", []),
                display_name=entry.get("display_name", entry["model_id"]),
            )
            key = f"{mp.provider}/{mp.model_id}"
            self._prices[key] = mp

    def _load_m1_yamls(self) -> None:
        """Load pricing from L0 M1 model/ YAMLs if available."""
        if not M1_MODEL_DIR.is_dir():
            return
        import yaml
        for yaml_file in M1_MODEL_DIR.glob("MODEL-PRICING-*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    mp = ModelPrice(
                        model_id=entry.get("model_id", ""),
                        provider=entry.get("provider", ""),
                        cost_per_1k_input=float(entry.get("cost_per_1k_input", entry.get("cost_in", 0))),
                        cost_per_1k_output=float(entry.get("cost_per_1k_output", entry.get("cost_out", 0))),
                        context_window=int(entry.get("context_window", entry.get("ctx", 4096))),
                        capabilities=entry.get("capabilities", entry.get("caps", [])),
                        display_name=entry.get("display_name", ""),
                        metadata=entry,
                    )
                    if mp.model_id and mp.provider:
                        key = f"{mp.provider}/{mp.model_id}"
                        self._prices[key] = mp  # YAML overrides defaults
            except Exception as exc:
                _log.debug("Failed to load pricing YAML %s: %s", yaml_file, exc)

    # ── Public API ───────────────────────────────────────────────────────────

    def get_price(self, model_id: str, provider: str = "") -> ModelPrice | None:
        """Get pricing for a specific model.

        Args:
            model_id: Model identifier (e.g. ``"gpt-4o"``).
            provider: Optional provider filter.

        Returns:
            ``ModelPrice`` or ``None`` if not found.
        """
        self._ensure_loaded()
        # Try exact match first
        if provider:
            key = f"{provider}/{model_id}"
            if key in self._prices:
                return self._prices[key]
        # Fallback: search by model_id only
        for key, mp in self._prices.items():
            if mp.model_id == model_id or key.endswith(f"/{model_id}"):
                return mp
        return None

    def get_cost(self, model_id: str, provider: str = "") -> dict[str, float]:
        """Get cost per 1K tokens for a model.

        Returns ``{"input": 0.0, "output": 0.0}`` if not found.
        """
        mp = self.get_price(model_id, provider)
        if mp:
            return mp.cost_per_1k
        return {"input": 0.0, "output": 0.0}

    def search(self, capability: str = "", provider: str = "") -> list[ModelPrice]:
        """Search models by capability and/or provider."""
        self._ensure_loaded()
        results = []
        for mp in self._prices.values():
            if provider and mp.provider != provider:
                continue
            if capability and capability not in mp.capabilities:
                continue
            results.append(mp)
        return sorted(results, key=lambda x: x.cost_per_1k_input)

    def list_all(self) -> list[ModelPrice]:
        """List all known models with pricing."""
        self._ensure_loaded()
        return sorted(self._prices.values(), key=lambda x: (x.provider, x.model_id))

    def register(self, mp: ModelPrice) -> None:
        """Register (or override) a model's pricing."""
        key = f"{mp.provider}/{mp.model_id}"
        self._prices[key] = mp

    def get_stats(self) -> dict[str, Any]:
        self._ensure_loaded()
        return {
            "total_models": len(self._prices),
            "providers": list({mp.provider for mp in self._prices.values()}),
        }
