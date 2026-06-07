from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderConfig:
    """Provider connection configuration."""

    base_url: str = ""
    api_key: str = ""
    timeout: int = 60


@dataclass
class ChatOptions:
    """Options for a chat completion call."""

    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


@dataclass
class ChatResult:
    """Result of a chat completion call."""

    id: str = ""
    model: str = ""
    content: str = ""
    finish_reason: str = "stop"
    usage: dict[str, int] | None = None


@dataclass
class StreamChunk:
    """A single streaming chunk from a chat completion call."""

    id: str = ""
    model: str = ""
    content: str = ""
    finish_reason: str | None = None


@dataclass
class ModelDescriptor:
    """Describes a model discovered from a provider."""

    id: str = ""
    name: str = ""
    provider: str = ""
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 4096
    is_available: bool = True
    cost_per_1k_tokens: dict[str, float] | None = None
    avg_latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackRule:
    """A single fallback rule with strategy and timeout."""

    model: str = ""
    """Model name to fall back to."""
    strategy: str = "balanced"
    """Scoring strategy for this fallback level."""
    timeout_ms: int = 30_000
    """Max wait before triggering the next fallback."""
    cooldown_ms: int = 10_000
    """Min time before retrying this fallback after a failure."""


@dataclass
class ModelRoutePolicy:
    """Routing policy for model selection."""

    strategy: str = "balanced"
    priority: list[str] = field(default_factory=list)
    fallback_chain: list[FallbackRule] = field(default_factory=list)
    """Multi-level fallback chain. Each entry: model + strategy + timeout."""


@dataclass
class ModelRequest:
    """A request to the model scheduler."""

    task: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    preferred_provider: str | None = None
    policy: ModelRoutePolicy | None = None


@dataclass
class ModelSelection:
    """Result of model selection."""

    model: ModelDescriptor
    provider_name: str
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class LoadInfo:
    """Load information for a model."""

    model_id: str = ""
    active_requests: int = 0
    avg_latency_ms: float = 0.0
    last_checked: float = 0.0


@dataclass
class SchedulerConfig:
    """Configuration for the model scheduler."""

    health_check_interval_ms: int = 30_000
    load_window_size: int = 10
    default_policy: str = "balanced"
    cost_weight: float = 0.3
    speed_weight: float = 0.3
    capability_weight: float = 0.4


DEFAULT_SCHEDULER_CONFIG = SchedulerConfig()
