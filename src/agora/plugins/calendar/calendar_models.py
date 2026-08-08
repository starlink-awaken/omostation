"""Calendar data models.

Extracted from SharedBrain D_Gateway.  Self-contained dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CalendarEvent:
    """Represents a calendar event."""

    event_id: str
    calendar_id: str
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    organizer: str = ""
    recurrence: str = ""
    uid: str = ""
    raw_ics: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "description": self.description,
            "location": self.location,
            "attendees": self.attendees,
            "organizer": self.organizer,
            "recurrence": self.recurrence,
            "uid": self.uid,
        }


@dataclass
class Calendar:
    """Represents a calendar resource."""

    calendar_id: str
    name: str
    description: str = ""
    color: str = ""
    read_only: bool = False
    ctag: str = ""
    supported_components: list[str] = field(default_factory=list)
