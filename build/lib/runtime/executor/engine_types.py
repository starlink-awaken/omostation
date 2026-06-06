"""Engine-specific type definitions for agent-runtime."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SovereigntyLevel(StrEnum):
    FULL = "FULL"
    CONDITIONAL = "CONDITIONAL"
    OBSERVE = "OBSERVE"


@dataclass
class AgentCapability:
    id: str; description: str = ""  # noqa: E702


@dataclass
class AgentIdentity:
    id: str; name: str; role: str  # noqa: E702
    sovereignty_level: SovereigntyLevel = SovereigntyLevel.CONDITIONAL
    capabilities: list[AgentCapability] = field(default_factory=list)
    personality: str | None = None
    communication_style: str | None = None
    boundaries: list[str] = field(default_factory=list)


@dataclass
class IdentityValidationResult:
    valid: bool; errors: list[str] = field(default_factory=list); warnings: list[str] = field(default_factory=list)  # noqa: E702


@dataclass
class WorkingMemoryEntry:
    value: Any; expires_at: float | None = None  # noqa: E702
    created_at: float = field(default_factory=time.time)


@dataclass
class ProjectMemoryEntry:
    id: str; project_id: str; category: str; key: str; value: str  # noqa: E702
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0; updated_at: float = 0.0  # noqa: E702


@dataclass
class OrgMemoryEntry:
    id: str; category: str; key: str; value: str  # noqa: E702
    source_project: str = ""; confidence: float = 0.5  # noqa: E702
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0; updated_at: float = 0.0  # noqa: E702


class ErrorSeverity(StrEnum):
    RECOVERABLE = "recoverable"; NON_RECOVERABLE = "non-recoverable"; FATAL = "fatal"  # noqa: E702


class ErrorCategory(StrEnum):
    NETWORK = "network"; FILESYSTEM = "filesystem"; DATABASE = "database"  # noqa: E702
    CONFIGURATION = "configuration"; VALIDATION = "validation"; AGENT_EXECUTION = "agent-execution"  # noqa: E702
    RESOURCE_EXHAUSTED = "resource-exhausted"; PERMISSION = "permission"; TIMEOUT = "timeout"  # noqa: E702
    PLUGIN = "plugin"; UNKNOWN = "unknown"  # noqa: E702


@dataclass
class RecoveryStrategy:
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    max_retries: int = 3; base_delay_ms: float = 1000.0; max_delay_ms: float = 10000.0  # noqa: E702
    use_exponential_backoff: bool = True; jitter_factor: float = 0.1; log_as_warning: bool = True  # noqa: E702


# fmt: off
class EngineError(Exception):
    def __init__(self, message, category=ErrorCategory.UNKNOWN, severity=ErrorSeverity.NON_RECOVERABLE, retryable=False, context=None, original=None):
        super().__init__(message); self.category = category; self.severity = severity  # noqa: E702
        self.retryable = retryable; self.context = context or {}; self.original = original  # noqa: E702
        self.timestamp = time.time()
    @classmethod
    def network(cls, msg, **kw): return cls(msg, ErrorCategory.NETWORK, ErrorSeverity.RECOVERABLE, True, kw)
    @classmethod
    def configuration(cls, msg, **kw): return cls(msg, ErrorCategory.CONFIGURATION, ErrorSeverity.NON_RECOVERABLE, False, kw)
    @classmethod
    def database(cls, msg, retryable=False, **kw):
        sev = ErrorSeverity.RECOVERABLE if retryable else ErrorSeverity.NON_RECOVERABLE
        return cls(msg, ErrorCategory.DATABASE, sev, retryable, kw)
    @classmethod
    def fatal(cls, msg, **kw): return cls(msg, ErrorCategory.UNKNOWN, ErrorSeverity.FATAL, False, kw)
    @classmethod
    def from_exception(cls, exc, **kw):
        m = str(exc)
        if any(x in m for x in ("ECONNREFUSED", "ETIMEDOUT", "ENOTFOUND")): return cls.network(m, original=exc)  # noqa: E701
        if any(x in m for x in ("ENOENT", "EACCES")): return cls(m, ErrorCategory.FILESYSTEM, ErrorSeverity.NON_RECOVERABLE, False, kw, exc)  # noqa: E701
        return cls(m, ErrorCategory.UNKNOWN, ErrorSeverity.NON_RECOVERABLE, False, kw, exc)
# fmt: on


class PluginType(StrEnum):
    PROTOCOL = "protocol"; DECOMPOSER = "decomposer"; CONTRACT = "contract"  # noqa: E702
    OBSERVABILITY = "observability"; STORAGE = "storage"; NOTIFICATION = "notification"  # noqa: E702
    AUTH = "auth"; AGENT = "agent"; SKILL = "skill"; INTEGRATION = "integration"; CUSTOM = "custom"  # noqa: E702

class PluginStatus(StrEnum):
    REGISTERED = "registered"; LOADED = "loaded"; ACTIVE = "active"  # noqa: E702
    INACTIVE = "inactive"; ERROR = "error"; UNLOADED = "unloaded"  # noqa: E702

PluginPermission = str

@dataclass
class PluginMetadata:
    plugin_id: str; name: str  # noqa: E702
    type: PluginType = PluginType.CUSTOM; version: str = "1.0.0"; description: str = ""  # noqa: E702
    author: str | None = None
    dependencies: list[str] = field(default_factory=list)
    permissions: list[PluginPermission] = field(default_factory=list)
    sandbox_enabled: bool = True

@dataclass
class PluginManifest:
    metadata: PluginMetadata; main: str = ""  # noqa: E702

@dataclass
class PluginLoadResult:
    plugin_id: str; success: bool; error: str | None = None  # noqa: E702

@dataclass
class PluginStateInfo:
    plugin_id: str; status: PluginStatus  # noqa: E702
    last_state_change: float = 0.0; error: str | None = None; started_at: float | None = None  # noqa: E702

@dataclass
class PluginSandboxConfig:
    enabled: bool = True
    allow_read_paths: list[str] = field(default_factory=list)
    allow_write_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=lambda: ["/etc", "/sys", "/proc", "/root"])
    allow_network: bool = False; allow_domains: list[str] = field(default_factory=list)  # noqa: E702
    allow_spawn: bool = False; allow_commands: list[str] = field(default_factory=list)  # noqa: E702
    max_memory_mb: int = 512; max_cpu_percent: int = 50; max_execution_time_ms: int = 30000  # noqa: E702
# fmt: on


# fmt: off
@dataclass
class CompletionOptions:
    model: str | None = None; max_tokens: int | None = None  # noqa: E702
    temperature: float | None = None; top_p: float | None = None  # noqa: E702
    system_prompt: str | None = None; stop_sequences: list[str] | None = None  # noqa: E702
    timeout_ms: int | None = None; api_key: str | None = None; skip_cache: bool = False  # noqa: E702
    metadata: dict[str, str] | None = None

@dataclass
class CompletionResult:
    content: str; model: str; provider: str  # noqa: E702
    input_tokens: int = 0; output_tokens: int = 0; total_tokens: int = 0  # noqa: E702
    finish_reason: str = "stop"; cached: bool = False; duration_ms: float = 0.0  # noqa: E702
    timestamp: float = field(default_factory=time.time)

@dataclass
class CompletionRequest:
    id: str; prompt: str; options: CompletionOptions | None = None  # noqa: E702

@dataclass
class CompletionChunk:
    delta: str = ""; done: bool = False; input_tokens: int = 0; output_tokens: int = 0  # noqa: E702

@dataclass
class ProviderConfig:
    name: str; provider_type: str; default_model: str  # noqa: E702
    supported_models: list[str] = field(default_factory=list)
    max_tokens: int = 128000; supports_streaming: bool = True  # noqa: E702
    supports_tools: bool = True; supports_batch: bool = False  # noqa: E702
    timeout_ms: int = 60000; max_retries: int = 3  # noqa: E702

@dataclass
class CacheConfig:
    enabled: bool = True; max_size: int = 1000; ttl_ms: int = 3_600_000  # noqa: E702

@dataclass
class RateLimitConfig:
    enabled: bool = True; requests_per_minute: int = 60  # noqa: E702

@dataclass
class AgentDefinition:
    name: str; description: str = ""  # noqa: E702
    capabilities: list[str] = field(default_factory=list)
    identity: AgentIdentity | None = None
# fmt: on
