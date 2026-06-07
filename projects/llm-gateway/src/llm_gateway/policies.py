"""Model selection policies — scoring and routing rules."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .types import LoadInfo, ModelDescriptor, ModelRequest, ModelRoutePolicy

ScoreFn = Callable[[ModelDescriptor, ModelRequest], float]

_registry: dict[str, ScoreFn] = {}
REFERENCE_CTX = 128_000


def _register(name: str, fn: ScoreFn) -> None:
    _registry[name] = fn


def _get(name: str) -> ScoreFn:
    fn = _registry.get(name)
    if fn is None:
        raise KeyError(f"Unknown scheduling policy: {name!r}")
    return fn


# ---------------------------------------------------------------------------
# Built-in scoring strategies
# ---------------------------------------------------------------------------


def _score_cost_first(model: ModelDescriptor, _request: ModelRequest) -> float:
    if not model.cost_per_1k_tokens:
        return 1.0
    total_cost = model.cost_per_1k_tokens.get("input", 0) + model.cost_per_1k_tokens.get("output", 0)
    return max(0.0, 1.0 - total_cost / 0.1)


def _score_speed_first(model: ModelDescriptor, _request: ModelRequest) -> float:
    if model.avg_latency_ms is None:
        return 0.5
    return max(0.0, 1.0 - model.avg_latency_ms / 10000.0)


def _score_capability_first(model: ModelDescriptor, request: ModelRequest) -> float:
    cap_match = sum(1 for c in request.required_capabilities if c in model.capabilities)
    cap_score = cap_match / max(1, len(request.required_capabilities))
    ctx_score = min(1.0, model.context_window / REFERENCE_CTX)
    return cap_score * 0.6 + ctx_score * 0.4


def _score_balanced(model: ModelDescriptor, request: ModelRequest) -> float:
    cost_score = _score_cost_first(model, request)
    speed_score = _score_speed_first(model, request)
    cap_score = _score_capability_first(model, request)
    return cost_score * 0.3 + speed_score * 0.3 + cap_score * 0.4


_register("cost-first", _score_cost_first)
_register("speed-first", _score_speed_first)
_register("capability-first", _score_capability_first)
_register("balanced", _score_balanced)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class ScoredModel:
    """A model with its computed score and load penalty."""

    model: ModelDescriptor
    score: float
    load_penalty: float


def register_policy(name: str, fn: ScoreFn) -> None:
    """Register a custom scoring policy."""
    _register(name, fn)


def list_policies() -> list[str]:
    """List all registered policy names."""
    return list(_registry.keys())


def get_load_penalty(
    model_id: str,
    load_map: dict[str, LoadInfo],
    ttl_ms: float = 300_000.0,
) -> float:
    """Compute a load penalty (0.0-0.5) for a model based on active requests."""
    load = load_map.get(model_id)
    if not load:
        return 0.0
    if time.time() * 1000 - load.last_checked > ttl_ms:
        load_map.pop(model_id, None)
        return 0.0
    return min(0.5, load.active_requests * 0.1)


def score_models(
    models: list[ModelDescriptor],
    request: ModelRequest,
    policy: ModelRoutePolicy,
    load_map: dict[str, LoadInfo] | None = None,
) -> list[ScoredModel]:
    """Score and sort models by policy strategy, returning ScoredModel list."""
    fn = _get(policy.strategy)
    scored: list[ScoredModel] = []
    for m in models:
        score = fn(m, request)
        load_penalty = get_load_penalty(m.id, load_map) if load_map else 0.0
        scored.append(ScoredModel(model=m, score=score, load_penalty=load_penalty))
    scored.sort(key=lambda s: s.score - s.load_penalty, reverse=True)
    return scored
