from __future__ import annotations
import logging
from agora.tools.base import ToolContext, JSONDict

_log = logging.getLogger(__name__)


def tool_mail_handler(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for all mail_inbox actions — wraps MailTool."""
    try:
        from organs.D_Gateway.tools.mail_tool import MailTool  # type: ignore[import-not-found]
    except ImportError:
        return {
            "error": "MailTool not available (missing mail_tool.py)",
            "success": False,
        }

    try:
        tool = MailTool()
        action = params.pop("action", "list_mailboxes")
        request = __import__(
            "organs.D_Gateway.interfaces.tool_interface_contract",
            fromlist=["ToolRequest"],
        ).ToolRequest(
            tool_name="mail_inbox",
            action=action,
            params=params,
        )
        result = tool.execute(request)
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "status": result.status.value,
        }
    except Exception as exc:  # noqa: BLE001  # defensive fallback
        _log.error("[MCPToolRegistry] mail handler error: %s", exc)
        return {"error": str(exc), "success": False}


def tool_tasks_list(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for tasks_list — wraps TasksTool via tool_tasks_handler."""
    from organs.D_Gateway.interfaces.tools.tasks_tool import tool_tasks_handler  # type: ignore[import-not-found]

    return tool_tasks_handler(params, ctx)
