from __future__ import annotations

import logging

from agora.tools.base import MCPToolRegistry, RegistryEntry
from agora.tools.core import (
    tool_broadcast_event,
    tool_get_task_info,
    tool_ping,
    tool_post_result,
)
from agora.tools.monitoring import (
    tool_get_metrics_snapshot,
    tool_get_swarm_health,
    tool_get_system_resources,
)
from agora.tools.synapse import tool_synapse_hello, tool_synapse_ping
from agora.tools.voice import (
    tool_voice_intent_digest,
    tool_voice_session_info,
    tool_voice_speak,
)

_log = logging.getLogger(__name__)


def build_default_registry() -> MCPToolRegistry:
    """Build the default MCP tool registry with all standard tools."""
    reg = MCPToolRegistry()
    # --- P5: digital_twin tool namespace ---
    # Tool implementations are provided by organs/D-Gateway/interfaces/base_tool.py
    # and registered here when their concrete adapters (mail, calendar, tasks) are ready.
    # Expected tool names: mail_inbox, calendar_events, tasks_list
    _dt_tool_registry: list[RegistryEntry] = []

    # --- Calendar Tool registration ---
    try:
        from organs.D_Gateway.tools.calendar_tool import (  # type: ignore[import-not-found]
            tool_calendar_check_conflicts,
            tool_calendar_create_event,
            tool_calendar_delete_event,
            tool_calendar_get_events,
            tool_calendar_list_calendars,
            tool_calendar_update_event,
        )

        _dt_tool_registry.extend(
            [
                (
                    "calendar/list_calendars",
                    tool_calendar_list_calendars,
                    "calendar_events",
                ),
                ("calendar/get_events", tool_calendar_get_events, "calendar_events"),
                (
                    "calendar/create_event",
                    tool_calendar_create_event,
                    "calendar_events",
                ),
                (
                    "calendar/update_event",
                    tool_calendar_update_event,
                    "calendar_events",
                ),
                (
                    "calendar/delete_event",
                    tool_calendar_delete_event,
                    "calendar_events",
                ),
                (
                    "calendar/check_conflicts",
                    tool_calendar_check_conflicts,
                    "calendar_events",
                ),
            ]
        )
    except ImportError:
        _log.warning(
            "[MCPToolRegistry] Calendar tool could not be loaded (missing dependencies)"
        )

    for name, handler, cat in _dt_tool_registry + [
        ("ping", tool_ping, "core"),
        ("post_result", tool_post_result, "core"),
        ("get_task_info", tool_get_task_info, "core"),
        ("broadcast_event", tool_broadcast_event, "core"),
        ("get_swarm_health", tool_get_swarm_health, "monitoring"),
        ("get_system_resources", tool_get_system_resources, "monitoring"),
        ("get_metrics_snapshot", tool_get_metrics_snapshot, "monitoring"),
        ("synapse/hello", tool_synapse_hello, "synapse"),
        ("synapse/ping", tool_synapse_ping, "synapse"),
        # --- Voice Tool registration ---
        ("voice/speak", tool_voice_speak, "voice"),
        ("voice/session_info", tool_voice_session_info, "voice"),
        ("voice/intent_digest", tool_voice_intent_digest, "voice"),
    ]:
        reg.register(name, handler, cat)
    return reg
