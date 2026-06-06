"""BaseTool — abstract base class for all Agora tools.

All tool adapters inherit from BaseTool and implement ``_do_execute()``.
This ensures a consistent execute/validate/get_status interface.

Extracted from SharedBrain D_Gateway.  BOSUri dependency removed;
plain string URIs used instead.
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import Any

from agora.mcp.tool_contract import ToolConfig, ToolRequest, ToolResult, ToolStatus  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class BaseTool:
    """Abstract base for all Agora tools.

    Subclasses must implement ``_do_execute()`` with their own logic.
    The ``execute()`` method handles timing, status tracking,
    and error wrapping automatically.
    """

    def __init__(self, config: ToolConfig | None = None) -> None:
        self._config = config or ToolConfig(name=self._tool_name())
        self._status = ToolStatus.IDLE
        self._last_duration_ms: float = 0.0

    # -------------------------------------------------------------------------
    # Identity helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _tool_name(cls) -> str:
        """Subclass sets this via ``tool_name = "..."`` class attribute."""
        return cls.__name__.lower()

    def get_uri(self, action: str = "default") -> str:
        """Return the canonical URI for this tool with the given action.

        Format: agora://tool/{tool_name}/{action}
        """
        return f"agora://tool/{self._config.name}/{action}"

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize the tool (e.g. open connections, load credentials)."""
        _log.info("[%s] Initializing tool", self._config.name)
        self._status = ToolStatus.IDLE

    def shutdown(self) -> None:
        """Shutdown the tool and release resources."""
        _log.info("[%s] Shutting down tool", self._config.name)
        self._status = ToolStatus.IDLE

    def validate_access(self, operation: str, context: dict[str, Any]) -> bool:
        """Check whether the given operation is permitted.

        Override in subclasses for tool-specific access control.
        Default: allow if tool is enabled.
        """
        return self._config.enabled

    def get_metadata(self) -> dict[str, Any]:
        """Return tool metadata (name, version, status)."""
        return {
            "name": self._config.name,
            "enabled": self._config.enabled,
            "status": self._status.value,
            "tool_name": self._tool_name(),
            "uri": self.get_uri(),
        }

    def get_registry_info(self) -> dict[str, Any]:
        """Return registration info for the tool registry."""
        return {
            "tool_name": self._config.name,
            "namespace": self._config.mcp_namespace,
            "enabled": self._config.enabled,
            "uri_base": f"agora://tool/{self._config.name}",
        }

    # -------------------------------------------------------------------------
    # Tool interface
    # -------------------------------------------------------------------------

    def validate(self, request: ToolRequest) -> tuple[bool, str | None]:
        """
        Pre-execution validation.

        Returns:
            (is_valid, error_message_or_none)

        Default implementation delegates to validate_access().
        Override for tool-specific validation logic.
        """
        if not self._config.enabled:
            return False, f"Tool '{self._config.name}' is disabled"
        if not self.validate_access(request.action, request.context):
            return False, f"Access denied for action '{request.action}'"
        return True, None

    def execute(self, request: ToolRequest) -> ToolResult:
        """
        Execute the requested tool action.

        Handles timing, status transitions, and error wrapping.
        Subclasses implement ``_do_execute()`` for actual logic.
        """
        self._status = ToolStatus.RUNNING
        start = time.perf_counter()

        valid, error_msg = self.validate(request)
        if not valid:
            self._status = ToolStatus.FAILURE
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"tool": self._config.name, "action": request.action},
                status=self._status,
            )

        try:
            result = self._do_execute(request)
            self._status = ToolStatus.SUCCESS if result.success else ToolStatus.FAILURE
            self._last_duration_ms = (time.perf_counter() - start) * 1000
            return result.with_duration(self._last_duration_ms)
        except Exception as exc:
            self._status = ToolStatus.FAILURE
            self._last_duration_ms = (time.perf_counter() - start) * 1000
            _log.exception("[%s] Unhandled error in execute", self._config.name)
            return ToolResult(
                success=False,
                error=str(exc),
                metadata={"tool": self._config.name, "action": request.action},
                trace_id=request.trace_id,
                status=self._status,
            )

    def get_status(self) -> ToolStatus:
        """Return the current tool status."""
        return self._status

    # -------------------------------------------------------------------------
    # Abstract
    # -------------------------------------------------------------------------

    @abstractmethod
    def _do_execute(self, request: ToolRequest) -> ToolResult:
        """
        Subclass implements the actual tool logic here.

        Must return a ToolResult.  Do NOT handle timing or status
        yourself — BaseTool.execute() wraps this.
        """
        ...


__all__ = ["BaseTool"]
