"""
Pre-Emptive KV Cache and Model VRAM Budget Estimator for omlxc.

Calculates dynamic key-value cache memory expansion for long-context requests
(32k~128k) to prevent out-of-memory (OOM) kernel crashes and Metal/CUDA swap storms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelArchitectureMeta:
    """Transformer structural dimensions determining KV Cache memory growth."""

    model_id: str
    num_layers: int
    num_kv_heads: int
    head_dim: int
    bytes_per_elem: int = 2  # FP16 / BF16 = 2 bytes
    weights_vram_mb: float = 0.0

    @property
    def bytes_per_token(self) -> int:
        """KV Cache bytes per token = 2 (K+V) * layers * kv_heads * head_dim * dtype_bytes."""
        return 2 * self.num_layers * self.num_kv_heads * self.head_dim * self.bytes_per_elem


# Known profiles for local models in omostation cluster
DEFAULT_ARCH_PROFILES: Final[dict[str, ModelArchitectureMeta]] = {
    # 70B/72B class models
    "qwen-72b": ModelArchitectureMeta("qwen-72b", 80, 8, 128, 2, 42000.0),
    "deepseek-v3": ModelArchitectureMeta("deepseek-v3", 61, 8, 128, 2, 38000.0),
    # 27B~35B class models
    "qwen-3.8-27b": ModelArchitectureMeta("qwen-3.8-27b", 64, 8, 128, 2, 17500.0),
    "coding": ModelArchitectureMeta("coding", 64, 8, 128, 2, 17500.0),
    # 9B~14B class models
    "qwen-3.5-9b": ModelArchitectureMeta("qwen-3.5-9b", 32, 4, 128, 2, 6200.0),
    "gemma-9b": ModelArchitectureMeta("gemma-9b", 42, 8, 256, 2, 6800.0),
    # 2B~4B class lightweight models
    "gemma-4b": ModelArchitectureMeta("gemma-4b", 26, 4, 256, 2, 2800.0),
    "gemma-2b": ModelArchitectureMeta("gemma-2b", 18, 1, 256, 2, 1600.0),
}


class VRAMBudgetEstimator:
    """Estimates dynamic KV Cache growth and evaluates placement admission."""

    def __init__(self, custom_profiles: dict[str, ModelArchitectureMeta] | None = None) -> None:
        self._profiles = dict(DEFAULT_ARCH_PROFILES)
        if custom_profiles:
            self._profiles.update(custom_profiles)

    @property
    def registered_models(self) -> tuple[str, ...]:
        """List all model identifiers with registered architecture profiles."""
        return tuple(self._profiles.keys())

    def get_profile(self, model_id: str) -> ModelArchitectureMeta:
        """Resolve architecture profile or fallback to a standard 14B profile."""
        if model_id in self._profiles:
            return self._profiles[model_id]
        # Generic fallback: 32 layers, 4 kv heads, 128 head dim
        return ModelArchitectureMeta(model_id=model_id, num_layers=32, num_kv_heads=4, head_dim=128)

    def estimate_kv_cache_mb(
        self,
        model_id: str,
        context_tokens: int,
        max_output_tokens: int = 1024,
    ) -> float:
        """Calculate estimated KV Cache footprint in megabytes (MB)."""
        profile = self.get_profile(model_id)
        total_tokens = max(context_tokens + max_output_tokens, 1)
        total_bytes = profile.bytes_per_token * total_tokens
        return round(total_bytes / (1024.0 * 1024.0), 2)

    def estimate_total_vram_mb(
        self,
        model_id: str,
        context_tokens: int,
        max_output_tokens: int = 1024,
    ) -> float:
        """Calculate total VRAM needed (weights + KV Cache)."""
        profile = self.get_profile(model_id)
        kv_mb = self.estimate_kv_cache_mb(model_id, context_tokens, max_output_tokens)
        return round(profile.weights_vram_mb + kv_mb, 2)

    def check_headroom_admission(
        self,
        model_id: str,
        context_tokens: int,
        available_node_vram_mb: float,
        safe_headroom_ratio: float = 0.85,
        max_output_tokens: int = 1024,
    ) -> tuple[bool, float, str]:
        """
        Check if request KV Cache fits within available node memory budget.
        
        Returns (admitted, estimated_kv_mb, reason).
        """
        kv_mb = self.estimate_kv_cache_mb(model_id, context_tokens, max_output_tokens)
        safe_budget_mb = available_node_vram_mb * safe_headroom_ratio
        if kv_mb > safe_budget_mb:
            return (
                False,
                kv_mb,
                (
                    f"estimated KV Cache ({kv_mb} MB) exceeds safe node headroom "
                    f"({safe_budget_mb:.1f} MB out of {available_node_vram_mb:.1f} MB)"
                ),
            )
        return (
            True,
            kv_mb,
            f"admitted: {kv_mb} MB within safe headroom ({safe_budget_mb:.1f} MB)",
        )
