"""Tool Interface Contract — shared types for all Agora tools.

Provides Pydantic models used by BaseTool subclasses and consumed by
the MCP server.  Extracted from SharedBrain D_Gateway.

URI scheme: agora://tool/{name}/{action}
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    """Enumeration of possible tool execution states."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class ToolConfig(BaseModel):
    """Configuration for a single Agora tool instance."""

    name: str = Field(
        ..., description="Unique tool identifier, e.g. 'mail', 'calendar'"
    )
    enabled: bool = Field(default=True, description="Whether the tool is active")
    timeout_seconds: float = Field(
        default=30.0, ge=0, description="Per-call timeout in seconds"
    )
    retry_policy: dict[str, int | float] = Field(
        default_factory=lambda: {"max_attempts": 1, "backoff_base": 1.0},
        description="Retry configuration with max_attempts and backoff_base",
    )
    mcp_namespace: str = Field(
        default="dt",
        description="MCP tool namespace this tool registers under",
    )


class ToolRequest(BaseModel):
    """Incoming request passed to BaseTool.execute()."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    action: str = Field(
        default="default", description="Semantic action within the tool"
    )
    params: dict = Field(default_factory=dict, description="Action-specific parameters")
    context: dict = Field(
        default_factory=dict, description="Execution context (auth, trace, etc.)"
    )
    trace_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex, description="Full链路 trace ID"
    )

    def get_uri(self, base_resource: str | None = None) -> str:
        """Return the canonical URI for this request."""
        resource = base_resource or self.tool_name
        return f"agora://tool/{resource}/{self.action}"


class ToolResult(BaseModel):
    """Standard result returned by BaseTool.execute()."""

    success: bool = Field(..., description="Whether the tool call succeeded")
    data: dict | list | str | None = Field(
        default=None, description="Payload on success"
    )
    error: str | None = Field(default=None, description="Error message on failure")
    metadata: dict = Field(
        default_factory=dict,
        description="Auxiliary metadata (duration_ms, record_count, etc.)",
    )
    trace_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex, description="Correlated trace ID"
    )
    status: ToolStatus = Field(
        default=ToolStatus.UNKNOWN, description="Tool execution status"
    )

    def with_duration(self, ms: float) -> ToolResult:
        """Return a copy with duration_ms added to metadata."""
        meta = dict(self.metadata)
        meta["duration_ms"] = round(ms, 3)
        return ToolResult(
            success=self.success,
            data=self.data,
            error=self.error,
            metadata=meta,
            trace_id=self.trace_id,
            status=self.status,
        )


__all__ = [
    "ToolStatus",
    "ToolConfig",
    "ToolRequest",
    "ToolResult",
]
