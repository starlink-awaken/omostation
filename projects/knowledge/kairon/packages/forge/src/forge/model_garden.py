"""Model Garden — local LLM model inventory and recommendation."""

import logging
from typing import Any

_log = logging.getLogger(__name__)

TASK_MODEL_MAP = {
    "coding": ["claude-3-5-sonnet", "gpt-4o", "deepseek-coder-v2", "codellama-70b"],
    "research": ["claude-3-opus", "gpt-4-turbo", "gemini-2.0-pro", "llama-3-70b"],
    "chat": ["claude-3-5-haiku", "gpt-4o-mini", "llama-3-8b", "mistral-7b"],
    "vision": ["gpt-4-vision", "claude-3-vision", "llava-34b", "cogvlm-2"],
}


class ModelGarden:
    def __init__(self) -> None:
        self._models: list[dict[str, Any]] = []
        self._benchmarks: dict[str, dict[str, float]] = {}

    def inventory(self) -> list[dict[str, Any]]:
        return list(self._models)

    def add_model(
        self,
        name: str,
        provider: str,
        size_gb: float,
        quantization: str = "",
        last_used: str = "",
        parameter_count: str = "",
    ) -> dict:
        model = {
            "name": name,
            "provider": provider,
            "size_gb": size_gb,
            "quantization": quantization,
            "last_used": last_used,
            "parameter_count": parameter_count,
        }
        self._models.append(model)
        return model

    def add_benchmark(self, model: str, metric: str, score: float) -> None:
        if model not in self._benchmarks:
            self._benchmarks[model] = {}
        self._benchmarks[model][metric] = score

    def recommend(self, task: str) -> list[dict]:
        candidates = TASK_MODEL_MAP.get(task, TASK_MODEL_MAP["chat"])
        available = [m for m in self._models if any(c.lower() in m["name"].lower() for c in candidates)]
        if not available:
            available = self._models[:3]
        return available

    def prune_candidates(self, days_unused: int = 30) -> list[dict]:
        """Return pruning suggestions — does NOT delete anything."""
        return [m for m in self._models if m.get("last_used") and m["last_used"] < f"<{days_unused}d"]
