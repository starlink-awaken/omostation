from __future__ import annotations

from typing import Any


class ToolCallHandler:
    """Handles the "tool" domain calls.

    Responsibilities (SRP): tool dispatch delegation only.
    Extracted from ExecutionCoordinator._handle_tool_call().
    """

    def __init__(self, tool_dispatcher: Any) -> None:
        self._dispatcher = tool_dispatcher

    async def handle(self, tool_id: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Delegate tool calls to the configured dispatcher."""
        if not action:
            return {"status": "error", "message": "Tool action is required"}
        return self._dispatcher.call(tool_id, action, params)
