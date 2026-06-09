"""MCP handler functions for calendar tool operations.

Extracted from SharedBrain D_Gateway.  Uses agora imports.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from agora.plugins.calendar.calendar_tool import CalendarTool  # type: ignore[import-not-found]
from agora.mcp.tool_contract import ToolRequest  # type: ignore[import-not-found]


def _parse_calendar_dates(params: dict) -> tuple[datetime, datetime]:
    from dateutil.parser import parse as parse_dt

    start_str = params.get("start_date", params.get("start"))
    end_str = params.get("end_date", params.get("end"))
    if not start_str or not end_str:
        raise ValueError("start_date and end_date are required")
    return parse_dt(start_str), parse_dt(end_str)


def _detect_platform() -> str:
    for candidate in ("icloud", "google", "outlook"):
        if os.environ.get(f"BOS_CALENDAR_{candidate.upper()}_ENABLED"):
            return candidate
    return "icloud"


def tool_calendar_list_calendars(params: dict, ctx: Any) -> dict:
    try:
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(tool_name="calendar", action="list_calendars", params={})
        )
        return {
            "calendars": result.data,
            "count": result.metadata.get("count", 0),
            "success": result.success,
        }
    except Exception as exc:
        return {"calendars": [], "count": 0, "success": False, "error": str(exc)}


def tool_calendar_get_events(params: dict, ctx: Any) -> dict:
    try:
        start, end = _parse_calendar_dates(params)
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(
                tool_name="calendar",
                action="get_events",
                params={
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "calendar_id": params.get("calendar_id"),
                },
            )
        )
        return {
            "events": result.data,
            "count": result.metadata.get("count", 0),
            "success": result.success,
        }
    except ValueError as exc:
        return {"events": [], "count": 0, "success": False, "error": str(exc)}
    except Exception as exc:
        return {"events": [], "count": 0, "success": False, "error": str(exc)}


def tool_calendar_create_event(params: dict, ctx: Any) -> dict:
    try:
        from dateutil.parser import parse as parse_dt

        start = parse_dt(params["start"])
        end = parse_dt(params["end"])
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(
                tool_name="calendar",
                action="create_event",
                params={
                    "title": params.get("title", "Untitled Event"),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "description": params.get("description", ""),
                    "attendees": params.get("attendees", []),
                    "location": params.get("location", ""),
                    "calendar_id": params.get("calendar_id"),
                },
            )
        )
        return {"event": result.data, "success": result.success, "error": result.error}
    except (KeyError, ValueError) as exc:
        return {"event": None, "success": False, "error": str(exc)}
    except Exception as exc:
        return {"event": None, "success": False, "error": str(exc)}


def tool_calendar_update_event(params: dict, ctx: Any) -> dict:
    try:
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(tool_name="calendar", action="update_event", params=params)
        )
        return {"event": result.data, "success": result.success, "error": result.error}
    except Exception as exc:
        return {"event": None, "success": False, "error": str(exc)}


def tool_calendar_delete_event(params: dict, ctx: Any) -> dict:
    try:
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(
                tool_name="calendar",
                action="delete_event",
                params={"event_id": params.get("event_id")},
            )
        )
        return {
            "deleted": result.success,
            "success": result.success,
            "error": result.error,
        }
    except Exception as exc:
        return {"deleted": False, "success": False, "error": str(exc)}


def tool_calendar_check_conflicts(params: dict, ctx: Any) -> dict:
    try:
        start, end = _parse_calendar_dates(params)
        tool = CalendarTool(platform=_detect_platform())
        tool.initialize()
        result = tool.execute(
            ToolRequest(
                tool_name="calendar",
                action="check_conflicts",
                params={"start": start.isoformat(), "end": end.isoformat()},
            )
        )
        data = result.data
        return {
            "has_conflicts": bool(
                data.get("has_conflicts") if isinstance(data, dict) else False
            ),
            "conflicts": data.get("conflicts", []) if isinstance(data, dict) else [],
            "count": data.get("count", 0) if isinstance(data, dict) else 0,
            "success": result.success,
        }
    except ValueError as exc:
        return {
            "has_conflicts": False,
            "conflicts": [],
            "count": 0,
            "success": False,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "has_conflicts": False,
            "conflicts": [],
            "count": 0,
            "success": False,
            "error": str(exc),
        }
