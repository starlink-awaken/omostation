"""Immutable, serializable core domain models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class NodeState(StrEnum):
    UNKNOWN = "unknown"
    PROBING = "probing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    RECOVERING = "recovering"


class NodeDiagnosticCode(StrEnum):
    """Safe aggregate outcomes from cached backend catalog refreshes."""

    NOT_PROBED = "not_probed"
    AUTHORIZATION_DENIED = "authorization_denied"
    STALE = "stale"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    INCOMPATIBLE = "incompatible"
    MODEL_UNAVAILABLE = "model_unavailable"
    RUNTIME_UNKNOWN = "runtime_unknown"
    GENERATION_NOT_READY = "generation_not_ready"
    AVAILABLE = "available"
    PROBE_FAILED = "probe_failed"


class JobState(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    R0 = "r0"
    R1 = "r1"
    R2 = "r2"


class RouteProfile(StrEnum):
    INTERACTIVE = "interactive"
    QUALITY = "quality"
    BATCH = "batch"
    ECO = "eco"


class BackendKind(StrEnum):
    OMLX_APP = "omlx_app"
    LM_STUDIO = "lm_studio"
    LM_LINK = "lm_link"
    OLLAMA = "ollama"


class DomainModel(BaseModel):
    """Shared strict and immutable behavior for domain values."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class HealthSnapshot(DomainModel):
    state: NodeState
    observed_at: datetime
    stale: bool
    detail: str | None = None

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class Node(DomainModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1)
    platform: str
    tailscale_identity: str | None = None
    control_endpoint: str | None = None
    inference_endpoints: tuple[str, ...] = ()
    capabilities: frozenset[str] = frozenset()
    memory_gb: float | None = Field(default=None, gt=0)
    health: HealthSnapshot
    fresh: bool | None = None
    authorized: bool | None = None
    available: bool | None = None
    loaded: bool | None = None
    ready: bool | None = None
    last_observed_at: datetime | None = None


class NodeDiagnosticOutcome(DomainModel):
    code: NodeDiagnosticCode
    count: int = Field(ge=1)


class NodeDiagnosticReport(DomainModel):
    """Read-only node health explanation with no network identity or error text."""

    node: Node
    outcomes: tuple[NodeDiagnosticOutcome, ...]


class BackendInstance(DomainModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    node_id: str = Field(min_length=1)
    kind: BackendKind
    protocol_version: str
    capabilities: frozenset[str] = frozenset()
    context_limit: int | None = Field(default=None, gt=0)
    thinking_control: str | None = None
    streaming: bool
    controllable: bool


class ModelSpec(DomainModel):
    id: str = Field(min_length=1)
    role: str
    capabilities: frozenset[str] = frozenset()
    reasoning: bool = False
    aliases: frozenset[str] = frozenset()
    fresh: bool | None = None
    authorized: bool | None = None
    available: bool | None = None
    loaded: bool | None = None
    ready: bool | None = None
    last_observed_at: datetime | None = None
    placement_states: tuple[PlacementRuntimeStatus, ...] = ()


class PlacementRuntimeStatus(DomainModel):
    placement_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    backend_id: str = Field(min_length=1)
    fresh: bool
    stale: bool
    authorized: bool
    available: bool
    loaded: bool
    ready: bool
    last_observed_at: datetime


class Placement(DomainModel):
    id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    backend_id: str = Field(min_length=1)
    backend_model_id: str = Field(min_length=1)
    model_path: str | None = None
    context_limit: int | None = Field(default=None, gt=0)
    quantization: str | None = None
    memory_gb: float | None = Field(default=None, gt=0)
    resident: bool = False
    load_cost_seconds: float | None = Field(default=None, ge=0)


class RouteRequest(DomainModel):
    request_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    profile: RouteProfile = RouteProfile.INTERACTIVE
    required_capabilities: frozenset[str] = frozenset()
    context_tokens: int = Field(ge=0)
    thinking_requested: bool = False


class RouteDecision(DomainModel):
    request_id: str = Field(min_length=1)
    selected_placement_id: str | None
    candidates: tuple[str, ...]
    candidate_scores: Mapping[str, float] = Field(default_factory=dict)
    rejected: Mapping[str, str]
    fallback_chain: tuple[str, ...]
    config_version: str
    explanation: str
    thinking_authorized: bool = False

    @field_validator("candidate_scores", "rejected")
    @classmethod
    def freeze_mapping(cls, value: Mapping[str, object]) -> Mapping[str, object]:
        return MappingProxyType(dict(value))

    @field_serializer("candidate_scores", "rejected")
    def serialize_mapping(self, value: Mapping[str, object]) -> dict[str, object]:
        return dict(value)


class Job(DomainModel):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    initiator: str = Field(min_length=1)
    risk: RiskLevel
    state: JobState
    progress: float = Field(ge=0, le=1)
    created_at: datetime
    updated_at: datetime
    log_reference: str | None = None
    rollback_reference: str | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("job timestamps must be timezone-aware")
        return value
