"""Model Scheduler — dynamic model selection with load awareness.

Uses the two-phase ``RouterPipeline`` (Filter → Score) for selection.
Supports multi-level fallback chains and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from .policies import RouterPipeline, score_models as _legacy_score
from .rate_limiter import RateLimiter
from .registry import ModelRegistry
from .types import (
    DEFAULT_SCHEDULER_CONFIG,
    FallbackRule,
    LoadInfo,
    ModelRequest,
    ModelRoutePolicy,
    ModelSelection,
    SchedulerConfig,
)

_log = logging.getLogger(__name__)


class ModelScheduler:
    """Dynamic model scheduler with load-aware, policy-driven selection.

    Selects the optimal model for a :class:`ModelRequest` using the
    two-phase ``RouterPipeline`` (Filter → Score).  Supports multi-level
    fallback chains and optional rate limiting.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: SchedulerConfig | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or DEFAULT_SCHEDULER_CONFIG
        self._load_map: dict[str, LoadInfo] = {}
        self._refresh_task: asyncio.Task[None] | None = None
        self._rate_limiter = rate_limiter
        self._fallback_cooldowns: dict[str, float] = {}  # model → cooldown until

    @classmethod
    def from_m1_dir(cls, m1_dir: str, config: SchedulerConfig | None = None) -> ModelScheduler:
        from .ssot_loader import load_ssot_models
        registry = ModelRegistry()
        load_ssot_models(registry, m1_dir)
        return cls(registry, config)

    @property
    def rate_limiter(self) -> RateLimiter | None:
        return self._rate_limiter

    def set_rate_limiter(self, rl: RateLimiter) -> None:
        self._rate_limiter = rl

    # ── Core selection ───────────────────────────────────────────────────────

    async def select_model(
        self,
        request: ModelRequest,
        policy: ModelRoutePolicy | None = None,
    ) -> ModelSelection | None:
        """Select the best model for *request*.

        Algorithm:
          1. Use ``RouterPipeline`` (Filter → Score) with the policy's strategy
          2. Apply fallback chain if primary selection fails or hits rate limit
          3. Return the best available model or ``None``
        """
        merged_policy = policy or ModelRoutePolicy(strategy=self._config.default_policy)
        candidates = self._registry.get_all()

        # Try primary strategy
        selection = self._select_with_pipeline(candidates, request, merged_policy)
        if selection:
            return selection

        # Try fallback chain
        if merged_policy.fallback_chain:
            for rule in merged_policy.fallback_chain:
                # Check cooldown
                cooldown_key = f"{rule.model}:{rule.strategy}"
                if cooldown_key in self._fallback_cooldowns:
                    if time.time() < self._fallback_cooldowns[cooldown_key]:
                        _log.debug("Fallback %s in cooldown, skipping", cooldown_key)
                        continue

                fb_policy = ModelRoutePolicy(
                    strategy=rule.strategy,
                    priority=[rule.model] if rule.model else [],
                )
                selection = self._select_with_pipeline(candidates, request, fb_policy)
                if selection:
                    selection.reasoning += f" | fallback({rule.model}, {rule.strategy})"
                    return selection

                # Mark cooldown
                self._fallback_cooldowns[cooldown_key] = time.time() + (rule.cooldown_ms / 1000)

        return None

    def _select_with_pipeline(
        self,
        candidates: list,
        request: ModelRequest,
        policy: ModelRoutePolicy,
    ) -> ModelSelection | None:
        """Run the RouterPipeline and return the best selection, or None."""
        pipeline = RouterPipeline.from_strategy(policy.strategy, self._load_map)

        # Priority short-circuit
        if policy.priority:
            priority_map = {mid: i for i, mid in enumerate(policy.priority)}
            sorted_cands = sorted(candidates, key=lambda m: priority_map.get(m.id, 999))
            best = sorted_cands[0]
            return ModelSelection(
                model=best,
                provider_name=best.provider,
                confidence=1.0,
                reasoning=f"Matched priority order: {best.id}",
            )

        scored = pipeline.select(candidates, request, load_map=self._load_map)
        if not scored:
            return None

        best = scored[0]

        # Rate limit check
        if self._rate_limiter and not self._rate_limiter.acquire(best.model.id):
            _log.warning("Model %s rate limited, skipping", best.model.id)
            return None

        self._record_load(best.model.id)

        return ModelSelection(
            model=best.model,
            provider_name=best.model.provider,
            confidence=max(0.0, min(1.0, best.score - best.load_penalty)),
            reasoning=(
                f"Scored {best.score:.2f} (penalty: {best.load_penalty:.2f}): "
                f"{policy.strategy}"
            ),
        )

    # ── Load tracking ────────────────────────────────────────────────────────

    def _record_load(self, model_id: str) -> None:
        existing = self._load_map.get(model_id)
        self._load_map[model_id] = LoadInfo(
            model_id=model_id,
            active_requests=(existing.active_requests if existing else 0) + 1,
            avg_latency_ms=existing.avg_latency_ms if existing else 0.0,
            last_checked=time.time() * 1000,
        )

    def release_load(self, model_id: str) -> None:
        load = self._load_map.get(model_id)
        if load:
            load.active_requests = max(0, load.active_requests - 1)

    # ── Auto refresh ─────────────────────────────────────────────────────────

    def start_auto_refresh(self, interval_ms: int = 30_000) -> Callable[[], None]:
        self.stop_auto_refresh()

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval_ms / 1000)
                try:
                    await self._registry.refresh()
                except Exception as exc:
                    _log.warning("[ModelScheduler] auto-refresh failed: %s", exc)

        self._refresh_task = asyncio.create_task(_loop())

        def dispose() -> None:
            self.stop_auto_refresh()
        return dispose

    def stop_auto_refresh(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    # ── Quota rates ──────────────────────────────────────────────────────────

    def load_quota_rates(self) -> int:
        CACHE_PATH = Path.home() / ".runtime" / "cache" / "quota_rates.json"
        if not CACHE_PATH.exists():
            return 0
        import json
        try:
            with open(CACHE_PATH) as f:
                data = json.load(f)
        except (json.JSONDecodeError, Exception):
            return 0
        rates = data.get("rates", {})
        updated = 0
        for model in self._registry.get_all():
            model_id_short = model.id.split("/")[-1]
            if model_id_short in rates:
                r = rates[model_id_short]
                if r.get("input") is not None:
                    model.cost_per_1k_tokens["input"] = r["input"]
                    model.cost_per_1k_tokens["output"] = r.get("output", r["input"])
                    updated += 1
        return updated

    # ── Status ───────────────────────────────────────────────────────────────

    def get_all_loads(self) -> list[LoadInfo]:
        return list(self._load_map.values())
