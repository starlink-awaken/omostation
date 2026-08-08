"""State transition log for the service registry."""

from __future__ import annotations

import secrets
import time


class TransitionLog:
    """Manages service state transition records with filtering and pruning."""

    _MAX_TRANSITIONS = 500

    def __init__(self):
        self._transitions: list[dict] = []

    def add(
        self, service: str, state_from: str, state_to: str, reason: str, source: str
    ):
        """Record a state transition."""
        transition = {
            "id": "tr_" + secrets.token_hex(4),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "service": service,
            "state_from": state_from or "",
            "state_to": state_to,
            "reason": reason,
            "source": source,
        }
        self._transitions.append(transition)
        if len(self._transitions) > self._MAX_TRANSITIONS:
            self._transitions = self._transitions[-self._MAX_TRANSITIONS :]

    def query(self, service: str = "", since: str = "", limit: int = 50) -> list[dict]:
        """Query state transition log.

        Args:
            service: Filter by service name (empty returns all)
            since: ISO timestamp filter
            limit: Max results (default 50)
        """
        result = self._transitions
        if service:
            result = [t for t in result if t["service"] == service]
        if since:
            result = [t for t in result if t["timestamp"] > since]
        return result[-limit:]

    def clear(self):
        """Clear all transition records (used for testing)."""
        self._transitions.clear()
