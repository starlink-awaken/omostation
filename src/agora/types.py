"""Shared types for agentmesh gateway migration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

MessageType = Literal["request", "response", "event", "stream", "stream_end"]

EventType = Literal[
    "agent.registered",
    "agent.unregistered",
    "task.submitted",
    "task.assigned",
    "task.started",
    "task.progress",
    "task.completed",
    "task.failed",
    "context.updated",
]

AgentStatus = Literal["online", "offline", "busy"]
AgentType = Literal["claude-code", "openclaw", "process", "http"]
TaskStatus = Literal["pending", "assigned", "running", "completed", "failed"]
LogLevel = Literal["debug", "info", "warn", "error"]

AgentInvoker = Callable[["AgentMessage"], Awaitable[Any]]


@dataclass
class Error:
    code: str
    message: str


@dataclass
class ContextRef:
    shared_space_id: str
    history: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


@dataclass
class Payload:
    task: str | None = None
    context: ContextRef | None = None
    files: list[str] | None = None
    options: dict[str, Any] | None = None


@dataclass
class AgentMessage:
    id: str
    type: MessageType
    source: str
    target: str
    correlation_id: str
    timestamp: int
    payload: Payload | None = None
    event_type: EventType | None = None
    event_data: dict[str, Any] | None = None
    result: Any = None
    error: Error | None = None


@dataclass
class Agent:
    id: str
    name: str
    type: AgentType
    capabilities: list[str]
    status: AgentStatus = "online"
    endpoint: str | None = None
    last_seen: int = 0


@dataclass
class Task:
    id: str
    status: TaskStatus = "pending"
    request: AgentMessage | None = None
    assigned_agents: list[str] = field(default_factory=list)
    result: Any = None
    error: Error | None = None
    created_at: int = 0
    updated_at: int = 0


@dataclass
class RoutingRule:
    name: str
    keywords: list[str]
    agent: str | None = None
    agents: list[str] | None = None
    strategy: str = "direct"
    priority: int = 0


@dataclass
class AgentConfig:
    id: str
    name: str
    type: AgentType
    capabilities: list[str]
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    endpoint: str | None = None


@dataclass
class RoutingConfig:
    default_agent: str | None = None
    rules: list[RoutingRule] = field(default_factory=list)


@dataclass
class GatewayConfig:
    port: int = 3100
    ws_port: int = 3101
    host: str = "0.0.0.0"  # noqa: S104
    data_dir: str = "./data"
    log_dir: str = "./logs"
    log_level: LogLevel = "info"
    routing: RoutingConfig | None = None
    agents: list[AgentConfig] = field(default_factory=list)
    models: dict[str, Any] | None = None
