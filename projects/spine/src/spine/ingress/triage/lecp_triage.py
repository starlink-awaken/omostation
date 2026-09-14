"""LECP Triage — map parsed email/calendar data to LECP v3.0 entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from spine.ingress.parsers.email_parser import EmailParser
from spine.ingress.parsers.calendar_parser import CalendarParser


# LECP v3.0 domain constants
DOMAIN_WORK = "p0_work"
DOMAIN_HEALTH = "p1_health"
DOMAIN_FAMILY = "p2_family"
DOMAIN_MIND = "p3_mind"
DOMAIN_RESEARCH = "p4_research"

PRIVACY_PUBLIC = "public"
PRIVACY_INTERNAL = "internal"
PRIVACY_SECRET = "secret"

STATUS_RAW = "raw"
STATUS_TRIAGED = "triaged"


class LeCPTriage:
    """Triage parsed email/calendar data into LECP v3.0 entity format."""

    def __init__(self) -> None:
        self.email_parser = EmailParser()
        self.calendar_parser = CalendarParser()

    def triage_email(self, eml_path: str | bytes | None = None, *, raw: bytes | None = None, parsed: dict[str, Any] | None = None) -> dict[str, Any]:
        """Triage an email into a LECP entity.

        Provide either `eml_path` (file path), `raw` (bytes), or `parsed` (pre-parsed dict).
        """
        if parsed is not None:
            data = parsed
        elif raw is not None:
            data = self.email_parser.parse_bytes(raw)
        elif eml_path is not None:
            data = self.email_parser.parse_file(eml_path)
        else:
            raise ValueError("Provide eml_path, raw, or parsed")

        return self._build_lecp_entity(
            entity_id=data["entity_id"],
            source="email",
            payload={
                "subject": data.get("subject", ""),
                "sender": data.get("sender", ""),
                "sender_domain": data.get("sender_domain", ""),
                "recipients": data.get("recipients", ""),
                "date": data.get("date", ""),
                "body": data.get("body", ""),
                "body_length": data.get("body_length", 0),
            },
            triage_fn=self._triage_email_data(data),
        )

    def triage_calendar(self, ics_path: str | bytes | None = None, *, raw: bytes | None = None) -> list[dict[str, Any]]:
        """Triage calendar events into LECP entities.

        Provide either `ics_path` (file path) or `raw` (bytes).
        """
        if raw is not None:
            events = self.calendar_parser.parse_bytes(raw)
        elif ics_path is not None:
            events = self.calendar_parser.parse_file(ics_path)
        else:
            raise ValueError("Provide ics_path or raw")

        return [self._triage_calendar_event(event) for event in events]

    def _triage_email_data(self, data: dict[str, Any]) -> dict[str, str]:
        """Determine domain and privacy for an email."""
        if data.get("is_work_domain"):
            return {"domain": DOMAIN_WORK, "privacy": PRIVACY_INTERNAL}
        return {"domain": DOMAIN_MIND, "privacy": PRIVACY_SECRET}

    def _triage_calendar_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build a LECP entity from a parsed calendar event."""
        if event.get("is_health_related"):
            domain = DOMAIN_HEALTH
            privacy = PRIVACY_SECRET
        elif event.get("is_multi_attendee"):
            domain = DOMAIN_WORK
            privacy = PRIVACY_INTERNAL
        else:
            domain = DOMAIN_MIND
            privacy = PRIVACY_SECRET

        return self._build_lecp_entity(
            entity_id=event["entity_id"],
            source="calendar",
            payload={
                "summary": event.get("summary", ""),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
                "attendee_count": event.get("attendee_count", 0),
            },
            triage_fn={"domain": domain, "privacy": privacy},
        )

    def _build_lecp_entity(
        self,
        *,
        entity_id: str,
        source: str,
        payload: dict[str, Any],
        triage_fn: dict[str, str],
    ) -> dict[str, Any]:
        """Build a complete LECP v3.0 entity."""
        now = datetime.now(tz=timezone.utc).isoformat()
        return {
            "entity_id": entity_id,
            "domain": triage_fn["domain"],
            "timestamp": now,
            "privacy_level": triage_fn["privacy"],
            "status": STATUS_TRIAGED,
            "source": source,
            "payload": payload,
        }
