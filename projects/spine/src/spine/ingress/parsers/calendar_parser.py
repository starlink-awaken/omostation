"""Calendar parser — extract structured data from .ics files."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from icalendar import Calendar
except ImportError:
    Calendar = None  # type: ignore[assignment, misc]


class CalendarParser:
    """Parse .ics files into structured dicts suitable for LECP triage."""

    HEALTH_KEYWORDS: set[str] = {"医院", "体检", "医生", "clinic", "medical", "health", "dental", "therapy"}

    def parse_file(self, path: str | Path) -> list[dict[str, Any]]:
        """Parse an .ics file and return a list of event dicts."""
        raw = Path(path).read_bytes()
        return self.parse_bytes(raw)

    def parse_bytes(self, raw: bytes) -> list[dict[str, Any]]:
        """Parse raw .ics bytes and return a list of event dicts."""
        if Calendar is None:
            raise ImportError("icalendar package required: pip install icalendar")

        cal = Calendar.from_ical(raw)
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                events.append(self._extract_event(component))
        return events

    def _extract_event(self, component: Any) -> dict[str, Any]:
        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))
        location = str(component.get("LOCATION", ""))

        dt_start = component.get("DTSTART")
        dt_end = component.get("DTEND")

        start_str = self._format_datetime(dt_start.dt) if dt_start else ""
        end_str = self._format_datetime(dt_end.dt) if dt_end else ""

        # Extract attendees
        attendees = []
        for attr in ["ATTENDEE", "ATTENDEES"]:
            raw_attendees = component.get(attr)
            if raw_attendees:
                if isinstance(raw_attendees, list):
                    attendees.extend(str(a) for a in raw_attendees)
                else:
                    attendees.append(str(raw_attendees))

        is_multi_attendee = len(attendees) > 1
        is_health = self._is_health_related(summary, description)

        entity_id = self._generate_entity_id(uid, start_str)

        return {
            "entity_id": entity_id,
            "uid": uid,
            "summary": summary,
            "description": description,
            "location": location,
            "start": start_str,
            "end": end_str,
            "attendees": attendees,
            "attendee_count": len(attendees),
            "is_multi_attendee": is_multi_attendee,
            "is_health_related": is_health,
        }

    def _is_health_related(self, summary: str, description: str) -> bool:
        """Check if event is health-related based on keywords."""
        text = f"{summary} {description}".lower()
        return any(kw.lower() in text for kw in self.HEALTH_KEYWORDS)

    @staticmethod
    def _format_datetime(dt: Any) -> str:
        """Format datetime or date to ISO string."""
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        return str(dt)

    @staticmethod
    def _generate_entity_id(uid: str, start_str: str) -> str:
        """Generate LECP-compliant entity_id: evt-{YYYYMMDD}-{hash}."""
        date_part = "00000000"
        if start_str:
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                date_part = dt.strftime("%Y%m%d")
            except ValueError:
                date_part = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        hash_input = uid or start_str or str(datetime.now(tz=timezone.utc).timestamp())
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        return f"evt-{date_part}-{short_hash}"
