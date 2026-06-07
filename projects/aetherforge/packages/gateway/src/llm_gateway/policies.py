"""Model selection policies — two-phase filter/score scheduling framework.

Architecture (inspired by K8s Scheduling Framework)::

    Candidate models
         │
         ▼
    ┌─────────────┐
    │  Filter      │  Remove ineligible models (hard constraints)
    │  phase       │  - NodeOnlineFilter: only online nodes
    └──────┬──────┘   - CapacityFilter: has room
           │          - BudgetFilter: within cost budget
           ▼
    ┌─────────────┐
    │  Score       │  Rank remaining models (soft preferences)
    │  phase       │  - CostScore: cheaper is better
    └──────┬──────┘   - SpeedScore: faster is better
           │          - CapabilityScore: best capability match
           ▼
    ┌─────────────┐
    │  Select      │  Pick highest-scored + apply load penalty
    └─────────────┘

Usage::

    from llm_gateway.policies import RouterPipeline

    pipeline = RouterPipeline()
    pipeline.add_filter(OnlineFilter())
    pipeline.add_filter(CapacityFilter(max_load=0.9))
    pipeline.add_score(CostScore())
    pipeline.add_score(SpeedScore())

    best = pipeline.select(candidates, request)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .types import LoadInfo, ModelDescriptor, ModelRequest, ModelRoutePolicy

# ── Backward-compatible legacy API ──────────────────────────────────────────

ScoreFn = callable  # legacy: Callable[[ModelDescriptor, ModelRequest], float]

_legacy_registry: dict[str, ScoreFn] = {}
REFERENCE_CTX = 128_000


def register_policy(name: str, fn: ScoreFn) -> None:
    """[Legacy] Register a custom scoring policy.

    Deprecated: Use ``RouterPipeline.add_score()`` instead.
    """
    _legacy_registry[name] = fn


def list_policies() -> list[str]:
    """List all registered policy names (legacy + plugin)."""
    legacy = list(_legacy_registry.keys())
    plugins = [name for name, _ in _plugin_registry.items()]
    return list(set(legacy + plugins))


# ── Plugin base classes ────────────────────────────────────────────────────


class RouterFilter(ABC):
    """Filter plugin: remove ineligible candidates (hard constraint).

    Subclasses implement :meth:`filter` returning a pruned list.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def filter(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
    ) -> list[ModelDescriptor]:
        """Return only models that satisfy this filter."""


class RouterScore(ABC):
    """Score plugin: assign a score to a single candidate (soft preference).

    Subclasses implement :meth:`score` returning a float (higher = better).
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def score(
        self,
        model: ModelDescriptor,
        request: ModelRequest,
    ) -> float:
        """Score *model* for *request* (0.0–1.0, higher is better)."""


# ── Built-in Filter plugins ────────────────────────────────────────────────


class OnlineFilter(RouterFilter):
    """Filter: only models marked as available."""

    def filter(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
    ) -> list[ModelDescriptor]:
        return [m for m in models if m.is_available]


class CapacityFilter(RouterFilter):
    """Filter: models with capacity (load below threshold).

    Args:
        max_load: Maximum load factor (0.0–1.0). Default 0.95.
        load_map: Optional shared load tracking dict.
    """

    def __init__(self, max_load: float = 0.95, load_map: dict[str, LoadInfo] | None = None) -> None:
        self.max_load = max_load
        self._load_map = load_map

    def filter(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
    ) -> list[ModelDescriptor]:
        if self._load_map is None:
            return models
        return [
            m for m in models
            if self._load_map.get(m.id, LoadInfo()).active_requests / max(1, m.context_window) < self.max_load
        ]


class BudgetFilter(RouterFilter):
    """Filter: models within cost budget.

    Args:
        max_cost_per_1k: Maximum acceptable cost per 1K tokens.
    """

    def __init__(self, max_cost_per_1k: float = 0.1) -> None:
        self.max_cost = max_cost_per_1k

    def filter(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
    ) -> list[ModelDescriptor]:
        request_budget = request.metadata.get("max_cost", self.max_cost) if hasattr(request, "metadata") and request.metadata else self.max_cost
        return [
            m for m in models
            if not m.cost_per_1k_tokens
            or (m.cost_per_1k_tokens.get("input", 0) + m.cost_per_1k_tokens.get("output", 0)) <= request_budget
        ]


class CapabilityFilter(RouterFilter):
    """Filter: only models that satisfy required capabilities."""

    def filter(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
    ) -> list[ModelDescriptor]:
        if not request.required_capabilities:
            return models
        return [
            m for m in models
            if all(c in m.capabilities for c in request.required_capabilities)
        ]


# ── Built-in Score plugins ─────────────────────────────────────────────────


class CostScore(RouterScore):
    """Score: cheaper is better (0.0–1.0)."""

    def score(self, model: ModelDescriptor, request: ModelRequest) -> float:
        if not model.cost_per_1k_tokens:
            return 1.0
        total = model.cost_per_1k_tokens.get("input", 0) + model.cost_per_1k_tokens.get("output", 0)
        return max(0.0, 1.0 - total / 0.1)


class SpeedScore(RouterScore):
    """Score: faster is better (0.0–1.0)."""

    def score(self, model: ModelDescriptor, request: ModelRequest) -> float:
        if model.avg_latency_ms is None:
            return 0.5
        return max(0.0, 1.0 - model.avg_latency_ms / 10000.0)


class CapabilityScore(RouterScore):
    """Score: best capability + context window match (0.0–1.0)."""

    def score(self, model: ModelDescriptor, request: ModelRequest) -> float:
        cap_match = sum(1 for c in request.required_capabilities if c in model.capabilities)
        cap_score = cap_match / max(1, len(request.required_capabilities))
        ctx_score = min(1.0, model.context_window / REFERENCE_CTX)
        return cap_score * 0.6 + ctx_score * 0.4


class BalancedScore(RouterScore):
    """Score: weighted combination of cost (0.3) + speed (0.3) + capability (0.4)."""

    def __init__(self) -> None:
        self._cost = CostScore()
        self._speed = SpeedScore()
        self._cap = CapabilityScore()

    def score(self, model: ModelDescriptor, request: ModelRequest) -> float:
        return (
            self._cost.score(model, request) * 0.3
            + self._speed.score(model, request) * 0.3
            + self._cap.score(model, request) * 0.4
        )


class ZoneAffinityScore(RouterScore):
    """Score: prefer models in the same network zone or topology.

    Supports both simple ``network_zone`` matching and four-layer
    ``topology labels`` (region/zone/rack/host) affinity.

    The ``preferred_zone`` can be a simple string (``"local"``,
    ``"cloud"``) for network_zone matching, or a dotted topology path
    (``"region:us-east-1.zone:us-east-1a"``) for four-layer matching.
    """

    def __init__(self, preferred_zone: str = "local") -> None:
        self._preferred = preferred_zone
        self._topology_labels: dict[str, str] = {}
        self._parse_preferred()

    def _parse_preferred(self) -> None:
        """Parse dotted topology labels from preferred_zone.

        ``"region:us-east-1.zone:us-east-1a"`` →
        ``{"region": "us-east-1", "zone": "us-east-1a"}``
        """
        if "." in self._preferred and ":" in self._preferred:
            for part in self._preferred.split("."):
                if ":" in part:
                    k, v = part.split(":", 1)
                    self._topology_labels[k.strip()] = v.strip()

    def score(self, model: ModelDescriptor, request: ModelRequest) -> float:
        # If topology labels are specified, use four-layer affinity
        if self._topology_labels:
            model_topology = model.metadata.get("topology", {}) if model.metadata else {}
            match_count = 0
            total = len(self._topology_labels)
            for k, v in self._topology_labels.items():
                if model_topology.get(k) == v:
                    match_count += 1
            return match_count / total if total > 0 else 0.0

        # Simple network_zone matching (backward compat)
        model_zone = model.metadata.get("network_zone", "cloud") if model.metadata else "cloud"
        return 1.0 if model_zone == self._preferred else 0.0


# ── Plugin registry ────────────────────────────────────────────────────────

# Maps strategy names → (filter, score) pairs, replicating the legacy API
_plugin_registry: dict[str, tuple[list[RouterFilter], list[RouterScore]]] = {
    "cost-first": ([OnlineFilter(), CapabilityFilter()], [CostScore()]),
    "speed-first": ([OnlineFilter(), CapabilityFilter()], [SpeedScore()]),
    "capability-first": ([OnlineFilter()], [CapabilityScore()]),
    "balanced": ([OnlineFilter(), CapabilityFilter()], [BalancedScore()]),
}


def _get_plugins_for(
    strategy: str,
) -> tuple[list[RouterFilter], list[RouterScore]]:
    """Get filter/score plugins for a named strategy."""
    plugins = _plugin_registry.get(strategy)
    if plugins:
        return plugins

    # Fallback: try legacy registry
    legacy_fn = _legacy_registry.get(strategy)
    if legacy_fn:
        class _LegacyAdapter(RouterScore):
            def score(self, model, request):
                return legacy_fn(model, request)
        return ([OnlineFilter(), CapabilityFilter()], [_LegacyAdapter()])

    raise KeyError(f"Unknown scheduling strategy: {strategy!r}")


# ── Pipeline ───────────────────────────────────────────────────────────────


@dataclass
class ScoredModel:
    """A model with its computed score and optional load penalty."""

    model: ModelDescriptor
    score: float
    load_penalty: float = 0.0


class RouterPipeline:
    """Two-phase filter/score scheduling pipeline.

    Usage::

        pipeline = RouterPipeline()
        pipeline.add_filter(OnlineFilter())
        pipeline.add_score(CostScore())
        pipeline.add_score(SpeedScore())

        ranked = pipeline.select(candidates, request)
        best = ranked[0] if ranked else None
    """

    def __init__(self) -> None:
        self._filters: list[RouterFilter] = []
        self._scores: list[RouterScore] = []
        self._load_map: dict[str, LoadInfo] = {}

    # ── Configuration ─────────────────────────────────────────────────────

    def add_filter(self, f: RouterFilter) -> RouterPipeline:
        """Append a filter plugin."""
        self._filters.append(f)
        return self

    def add_score(self, s: RouterScore) -> RouterPipeline:
        """Append a score plugin."""
        self._scores.append(s)
        return self

    def set_load_map(self, load_map: dict[str, LoadInfo]) -> None:
        """Attach a shared load map for load-aware scoring."""
        self._load_map = load_map

    def clear(self) -> None:
        """Remove all filters and scores."""
        self._filters.clear()
        self._scores.clear()

    @classmethod
    def from_strategy(
        cls,
        strategy: str,
        load_map: dict[str, LoadInfo] | None = None,
    ) -> RouterPipeline:
        """Create a pipeline from a named strategy string.

        Supports legacy ``register_policy`` names and plugin-registered
        strategy names.
        """
        filters, scores = _get_plugins_for(strategy)
        pipeline = cls()
        for f in filters:
            pipeline.add_filter(f)
        for s in scores:
            pipeline.add_score(s)
        if load_map:
            pipeline.set_load_map(load_map)
        return pipeline

    # ── Execution ─────────────────────────────────────────────────────────

    def select(
        self,
        models: list[ModelDescriptor],
        request: ModelRequest,
        *,
        load_map: dict[str, LoadInfo] | None = None,
    ) -> list[ScoredModel]:
        """Run the full pipeline: Filter → Score → penalty → sort.

        Args:
            models: Candidate models.
            request: The scheduling request.
            load_map: Optional override for the load map.

        Returns:
            Ranked list of ScoredModel (highest score first).
        """
        lm = load_map or self._load_map

        # Phase 1: Filter (remove ineligible)
        candidates = list(models)
        for f in self._filters:
            candidates = f.filter(candidates, request)
            if not candidates:
                return []

        # Phase 2: Score + load penalty
        scored: list[ScoredModel] = []
        for m in candidates:
            total_score = 0.0
            for s in self._scores:
                total_score += s.score(m, request)
            avg_score = total_score / max(1, len(self._scores))

            load_penalty = _get_load_penalty(m.id, lm)
            scored.append(ScoredModel(model=m, score=avg_score, load_penalty=load_penalty))

        scored.sort(key=lambda sm: sm.score - sm.load_penalty, reverse=True)
        return scored


# ── Load penalty (shared) ──────────────────────────────────────────────────


def _get_load_penalty(
    model_id: str,
    load_map: dict[str, LoadInfo],
    ttl_ms: float = 300_000.0,
) -> float:
    """Compute a load penalty (0.0–0.5) for a model based on active requests."""
    load = load_map.get(model_id)
    if not load:
        return 0.0
    if time.time() * 1000 - load.last_checked > ttl_ms:
        load_map.pop(model_id, None)
        return 0.0
    return min(0.5, load.active_requests * 0.1)


# ── Legacy API wrappers (backward compatible) ──────────────────────────────


def score_models(
    models: list[ModelDescriptor],
    request: ModelRequest,
    policy: ModelRoutePolicy,
    load_map: dict[str, LoadInfo] | None = None,
) -> list[ScoredModel]:
    """[Legacy] Score and sort models by policy strategy.

    Delegates to :class:`RouterPipeline` internally.
    """
    pipeline = RouterPipeline.from_strategy(policy.strategy, load_map)
    return pipeline.select(models, request, load_map=load_map)
