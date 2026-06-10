"""CalendarTool — BOS tool for calendar operations via CalDAV.

Extracted from SharedBrain D_Gateway.  Uses agora.base_tool and
agora.tool_contract instead of nucleus/organs imports.

Supported platforms: Apple iCloud, Google Calendar, Microsoft Outlook.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from agora.calendar_adapters import BaseCalendarAdapter, create_adapter  # type: ignore[import-not-found]
from agora.plugins.calendar.calendar_models import CalendarEvent  # type: ignore[import-not-found]
from agora.mcp.base_tool import BaseTool  # type: ignore[import-not-found]
from agora.mcp.tool_contract import ToolConfig, ToolRequest, ToolResult, ToolStatus  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class CalendarTool(BaseTool):
    """
    BOS tool for calendar operations via CalDAV.

    Supported platforms: Apple iCloud, Google Calendar, Microsoft Outlook.
    """

    tool_name = "calendar"

    def __init__(
        self,
        config: ToolConfig | None = None,
        adapter: BaseCalendarAdapter | None = None,
        platform: str = "icloud",
        fact_graph: Any | None = None,
        **adapter_kwargs: Any,
    ) -> None:
        cfg = config or ToolConfig(
            name="calendar",
            enabled=True,
            mcp_namespace="calendar_events",
        )
        super().__init__(cfg)
        self._adapter = adapter
        self._platform = platform
        self._adapter_kwargs = adapter_kwargs
        self._fact_graph = fact_graph
        self._initialized = False

    def initialize(self) -> None:
        if self._adapter is None:
            self._adapter = create_adapter(self._platform, **self._adapter_kwargs)
        self._initialized = True
        super().initialize()

    def _do_execute(self, request: ToolRequest) -> ToolResult:
        action = request.action
        params = request.params

        if action == "list_calendars":
            return self._list_calendars(params)
        if action == "get_events":
            return self._get_events(params)
        if action == "create_event":
            return self._create_event(params)
        if action == "update_event":
            return self._update_event(params)
        if action == "delete_event":
            return self._delete_event(params)
        if action == "check_conflicts":
            return self._check_conflicts(params)
        if action == "sync_to_factgraph":
            return self._sync_to_factgraph(params)

        return ToolResult(
            success=False,
            error=(
                f"Unknown action: '{action}'. "
                f"Valid actions: list_calendars, get_events, create_event, "
                f"update_event, delete_event, check_conflicts, sync_to_factgraph"
            ),
            status=ToolStatus.FAILURE,
        )

    def _list_calendars(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        try:
            calendars = self._adapter.list_calendars()  # type: ignore[union-attr]
            return ToolResult(
                success=True,
                data=[cal.__dict__ for cal in calendars],
                metadata={"count": len(calendars)},
                status=ToolStatus.SUCCESS,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _get_events(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        from dateutil.parser import parse as parse_dt

        start_str = params.get("start_date", params.get("start"))
        end_str = params.get("end_date", params.get("end"))
        if not start_str or not end_str:
            return ToolResult(
                success=False,
                error="start_date and end_date are required",
                status=ToolStatus.FAILURE,
            )
        try:
            start = parse_dt(start_str)
            end = parse_dt(end_str)
        except (ValueError, TypeError) as exc:
            return ToolResult(
                success=False,
                error=f"Invalid date format: {exc}",
                status=ToolStatus.FAILURE,
            )
        calendar_id = params.get("calendar_id")
        try:
            events = self._adapter.get_events(start, end, calendar_id)  # type: ignore[union-attr]
            return ToolResult(
                success=True,
                data=[e.to_dict() for e in events],
                metadata={"count": len(events), "start": start_str, "end": end_str},
                status=ToolStatus.SUCCESS,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _create_event(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        from dateutil.parser import parse as parse_dt

        title = params.get("title", "Untitled Event")
        start_str = params.get("start")
        end_str = params.get("end")
        if not start_str or not end_str:
            return ToolResult(
                success=False,
                error="start and end are required",
                status=ToolStatus.FAILURE,
            )
        try:
            start = parse_dt(start_str)
            end = parse_dt(end_str)
        except (ValueError, TypeError) as exc:
            return ToolResult(
                success=False,
                error=f"Invalid date format: {exc}",
                status=ToolStatus.FAILURE,
            )
        try:
            event = self._adapter.create_event(  # type: ignore[union-attr]
                title=title,
                start=start,
                end=end,
                description=params.get("description", ""),
                attendees=params.get("attendees"),
                location=params.get("location", ""),
                calendar_id=params.get("calendar_id"),
            )
            self._ingest_to_factgraph(event)
            return ToolResult(
                success=True,
                data=event.to_dict(),
                metadata={"event_id": event.event_id},
                status=ToolStatus.SUCCESS,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _update_event(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        event_id = params.get("event_id")
        if not event_id:
            return ToolResult(
                success=False,
                error="event_id is required",
                status=ToolStatus.FAILURE,
            )
        try:
            event = self._adapter.update_event(event_id, params)  # type: ignore[union-attr]
            return ToolResult(
                success=True,
                data=event.to_dict(),
                metadata={"event_id": event.event_id},
                status=ToolStatus.SUCCESS,
            )
        except NotImplementedError:
            return ToolResult(
                success=False,
                error="update_event not supported for this platform",
                status=ToolStatus.FAILURE,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _delete_event(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        event_id = params.get("event_id")
        if not event_id:
            return ToolResult(
                success=False,
                error="event_id is required",
                status=ToolStatus.FAILURE,
            )
        try:
            deleted = self._adapter.delete_event(event_id)  # type: ignore[union-attr]
            if deleted:
                return ToolResult(
                    success=True,
                    data={"deleted": True, "event_id": event_id},
                    status=ToolStatus.SUCCESS,
                )
            return ToolResult(
                success=False,
                error="Delete operation returned false",
                status=ToolStatus.FAILURE,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _check_conflicts(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        from dateutil.parser import parse as parse_dt

        start_str = params.get("start")
        end_str = params.get("end")
        if not start_str or not end_str:
            return ToolResult(
                success=False,
                error="start and end are required",
                status=ToolStatus.FAILURE,
            )
        try:
            start = parse_dt(start_str)
            end = parse_dt(end_str)
            if start.tzinfo is None:
                start = start.replace(tzinfo=datetime.UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=datetime.UTC)
        except (ValueError, TypeError) as exc:
            return ToolResult(
                success=False,
                error=f"Invalid date format: {exc}",
                status=ToolStatus.FAILURE,
            )
        try:
            events = self._adapter.get_events(start, end)  # type: ignore[union-attr]
            conflicts = [e.to_dict() for e in events if e.start < end and e.end > start]
            return ToolResult(
                success=True,
                data={
                    "has_conflicts": len(conflicts) > 0,
                    "conflicts": conflicts,
                    "count": len(conflicts),
                },
                metadata={"checked_start": start_str, "checked_end": end_str},
                status=ToolStatus.SUCCESS,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _sync_to_factgraph(self, params: dict) -> ToolResult:
        if not self._initialized:
            self.initialize()
        from dateutil.parser import parse as parse_dt

        start_str = params.get("start_date")
        end_str = params.get("end_date")
        if not start_str or not end_str:
            return ToolResult(
                success=False,
                error="start_date and end_date are required",
                status=ToolStatus.FAILURE,
            )
        try:
            start = parse_dt(start_str)
            end = parse_dt(end_str)
        except (ValueError, TypeError) as exc:
            return ToolResult(
                success=False,
                error=f"Invalid date format: {exc}",
                status=ToolStatus.FAILURE,
            )
        try:
            events = self._adapter.get_events(start, end)  # type: ignore[union-attr]
            for event in events:
                self._ingest_to_factgraph(event)
            return ToolResult(
                success=True,
                data={
                    "synced": len(events),
                    "event_ids": [e.event_id for e in events],
                },
                metadata={"count": len(events)},
                status=ToolStatus.SUCCESS,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), status=ToolStatus.FAILURE)

    def _ingest_to_factgraph(self, event: CalendarEvent) -> None:
        """Ingest a calendar event into FactGraph as knowledge triples."""
        if self._fact_graph is None:
            _log.debug("[CalendarTool] FactGraph not available, skipping ingestion")
            return
        try:
            node = f"event:{event.event_id}"
            self._fact_graph.add_fact(
                sub=node,
                pred="rdf:type",
                obj="cal:Event",
                metadata={"source": "calendar_tool"},
            )
            self._fact_graph.add_fact(
                sub=node,
                pred="cal:title",
                obj=event.title,
                metadata={"source": "calendar_tool"},
            )
            self._fact_graph.add_fact(
                sub=node,
                pred="cal:start",
                obj=event.start.isoformat(),
                metadata={"source": "calendar_tool"},
            )
            self._fact_graph.add_fact(
                sub=node,
                pred="cal:end",
                obj=event.end.isoformat(),
                metadata={"source": "calendar_tool"},
            )
            if event.organizer:
                self._fact_graph.add_fact(
                    sub=node,
                    pred="cal:organizer",
                    obj=event.organizer,
                    metadata={"source": "calendar_tool"},
                )
            for att in event.attendees:
                self._fact_graph.add_fact(
                    sub=node,
                    pred="cal:attendee",
                    obj=att,
                    metadata={"source": "calendar_tool"},
                )
            _log.debug(
                "[CalendarTool] Ingested event %s (%s) into FactGraph",
                event.event_id,
                event.title,
            )
        except Exception as exc:
            _log.warning("[CalendarTool] FactGraph ingestion failed: %s", exc)
