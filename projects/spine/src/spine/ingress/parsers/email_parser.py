"""Email parser — extract structured data from .eml files."""

from __future__ import annotations

import email
import hashlib
import re
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


class EmailParser:
    """Parse .eml files into structured dicts suitable for LECP triage."""

    WORK_DOMAINS: set[str] = {"github.com", "gitlab.com", "atlassian.net", "notion.so"}

    def parse_file(self, path: str | Path) -> dict[str, Any]:
        """Parse an .eml file and return structured data."""
        raw = Path(path).read_bytes()
        return self.parse_bytes(raw)

    def parse_bytes(self, raw: bytes) -> dict[str, Any]:
        """Parse raw .eml bytes and return structured data."""
        msg = email.message_from_bytes(raw)
        return self._extract(msg)

    def _extract(self, msg: Message) -> dict[str, Any]:
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        recipients = msg.get("To", "")
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        # Parse date
        dt: datetime | None = None
        if date_str:
            try:
                dt = parsedate_to_datetime(date_str)
            except (ValueError, TypeError):
                dt = None

        # Extract plain text body
        body = self._extract_body(msg)

        # Sender domain
        sender_domain = self._extract_domain(sender)

        # Generate entity_id
        entity_id = self._generate_entity_id(message_id or sender or subject, dt)

        return {
            "entity_id": entity_id,
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "sender_domain": sender_domain,
            "recipients": recipients,
            "date": dt.isoformat() if dt else date_str,
            "body": body,
            "body_length": len(body),
            "is_work_domain": sender_domain in self.WORK_DOMAINS,
        }

    def _extract_body(self, msg: Message) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace")
            return ""
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
            return ""

    @staticmethod
    def _extract_domain(sender: str) -> str:
        """Extract email domain from sender address."""
        match = re.search(r"@([\w.-]+)", sender)
        return match.group(1).lower() if match else ""

    @staticmethod
    def _generate_entity_id(message_id: str, dt: datetime | None) -> str:
        """Generate LECP-compliant entity_id: evt-{YYYYMMDD}-{hash}."""
        date_part = dt.strftime("%Y%m%d") if dt else datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        hash_input = message_id or str(datetime.now(tz=timezone.utc).timestamp())
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        return f"evt-{date_part}-{short_hash}"
