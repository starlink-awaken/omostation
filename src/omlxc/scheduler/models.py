"""Immutable scheduler inputs, policies, and typed failures."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from omlxc.domain import RouteProfile


class RejectionCode(StrEnum):
    MODEL = "model_mismatch"
    AUTHORIZATION = "authorization_denied"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CAPABILITY = "capability_missing"
    CONTEXT = "context_exceeded"
    MEMORY = "memory_denied"
    NO_CAPACITY = "no_capacity"
    LOCAL_SECURITY = "local_security_denied"


class RouteFailureCode(StrEnum):
    NO_CANDIDATE = "no_candidate"
    NO_CAPACITY = "no_capacity"
    INVALID_SNAPSHOT = "invalid_snapshot"


def _validate_optional_number(
    name: str, value: float | None, *, minimum: float, maximum: float | None = None
) -> None:
    if value is None:
        return
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} must be finite and within range")


@dataclass(frozen=True, slots=True)
class RouteFailure:
    request_id: str
    code: RouteFailureCode
    rejected: Mapping[str, str]
    explanation: str
    config_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "rejected", MappingProxyType(dict(sorted(self.rejected.items()))))


@dataclass(frozen=True, slots=True)
class PlacementSnapshot:
    placement_id: str
    model_id: str
    backend_id: str
    backend_model_id: str
    node_id: str
    fresh: bool
    available: bool
    authorized: bool
    capabilities: frozenset[str]
    context_limit: int | None
    memory_admitted: bool | None
    loaded: bool
    ttft_ms: float | None
    throughput_tps: float | None
    queue_depth: int | None
    error_rate: float | None
    network_cost_ms: float | None
    affinity: float | None
    available_concurrency: int | None
    local: bool
    security_allowed: bool

    def __post_init__(self) -> None:
        if any(
            not value
            for value in (
                self.placement_id,
                self.model_id,
                self.backend_id,
                self.backend_model_id,
                self.node_id,
            )
        ):
            raise ValueError("placement identities must be non-empty")
        if self.context_limit is not None and self.context_limit <= 0:
            raise ValueError("context limit must be positive")
        if self.available_concurrency is not None and self.available_concurrency < 0:
            raise ValueError("available concurrency must be non-negative")
        _validate_optional_number("ttft_ms", self.ttft_ms, minimum=0)
        _validate_optional_number("throughput_tps", self.throughput_tps, minimum=0)
        _validate_optional_number("error_rate", self.error_rate, minimum=0, maximum=1)
        _validate_optional_number("network_cost_ms", self.network_cost_ms, minimum=0)
        _validate_optional_number("affinity", self.affinity, minimum=0, maximum=1)
        if self.queue_depth is not None and self.queue_depth < 0:
            raise ValueError("queue depth must be non-negative")


def is_static_eligible(placement: PlacementSnapshot) -> bool:
    """Return request-independent scheduler eligibility for catalog projections."""
    return (
        placement.authorized
        and placement.fresh
        and placement.available
        and placement.memory_admitted is True
        and placement.available_concurrency is not None
        and placement.available_concurrency > 0
        and placement.local
        and placement.security_allowed
    )


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    loaded: float
    ttft: float
    throughput: float
    queue: float
    error_rate: float
    network: float
    affinity: float

    def __post_init__(self) -> None:
        values = (
            tuple(self.__dict__.values())
            if hasattr(self, "__dict__")
            else (
                self.loaded,
                self.ttft,
                self.throughput,
                self.queue,
                self.error_rate,
                self.network,
                self.affinity,
            )
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("score weights must be finite and non-negative")
        if sum(values) <= 0:
            raise ValueError("at least one score weight must be positive")


@dataclass(frozen=True, slots=True)
class PerformanceDefaults:
    ttft_ms: float
    throughput_tps: float
    queue_depth: int
    error_rate: float
    network_cost_ms: float
    affinity: float

    def __post_init__(self) -> None:
        _validate_optional_number("ttft_ms", self.ttft_ms, minimum=0)
        _validate_optional_number("throughput_tps", self.throughput_tps, minimum=0)
        _validate_optional_number("error_rate", self.error_rate, minimum=0, maximum=1)
        _validate_optional_number("network_cost_ms", self.network_cost_ms, minimum=0)
        _validate_optional_number("affinity", self.affinity, minimum=0, maximum=1)
        if self.queue_depth < 0:
            raise ValueError("default queue depth must be non-negative")


@dataclass(frozen=True, slots=True)
class NormalizationBounds:
    ttft_ms: float = 5_000.0
    throughput_tps: float = 200.0
    queue_depth: int = 32
    network_cost_ms: float = 500.0

    def __post_init__(self) -> None:
        if (
            any(
                not math.isfinite(value) or value <= 0
                for value in (self.ttft_ms, self.throughput_tps, self.network_cost_ms)
            )
            or self.queue_depth <= 0
        ):
            raise ValueError("normalization bounds must be finite and positive")


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    profile: RouteProfile
    config_version: str
    weights: ScoreWeights
    defaults: PerformanceDefaults
    bounds: NormalizationBounds = NormalizationBounds()

    def __post_init__(self) -> None:
        if not self.config_version:
            raise ValueError("route policy config version is required")


def default_policies() -> Mapping[RouteProfile, RoutePolicy]:
    defaults = PerformanceDefaults(1_000.0, 20.0, 4, 0.05, 20.0, 0.0)
    policies = {
        RouteProfile.INTERACTIVE: RoutePolicy(
            RouteProfile.INTERACTIVE,
            "scheduler-v1",
            ScoreWeights(0.22, 0.30, 0.10, 0.12, 0.08, 0.10, 0.08),
            defaults,
        ),
        RouteProfile.QUALITY: RoutePolicy(
            RouteProfile.QUALITY,
            "scheduler-v1",
            ScoreWeights(0.10, 0.12, 0.18, 0.08, 0.20, 0.08, 0.24),
            defaults,
        ),
        RouteProfile.BATCH: RoutePolicy(
            RouteProfile.BATCH,
            "scheduler-v1",
            ScoreWeights(0.08, 0.08, 0.34, 0.22, 0.12, 0.06, 0.10),
            defaults,
        ),
        RouteProfile.ECO: RoutePolicy(
            RouteProfile.ECO,
            "scheduler-v1",
            ScoreWeights(0.28, 0.10, 0.10, 0.10, 0.12, 0.20, 0.10),
            defaults,
        ),
    }
    return MappingProxyType(policies)
