from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

_DEFAULT_HATCH_TIMEOUT_S: float = 60.0
_PROCESS_POLL_INTERVAL_S: float = 0.5


def _emit_hatcher_event(event_type: str, source: str, payload: dict | None = None) -> None:
    """Publish a hatcher event to the EventBus."""
    from .event_bus import EventBus, make_event

    try:
        bus = EventBus.get_instance()
        event = make_event(event_type, source, payload)
        bus.publish(event)
    except Exception as e:
        _log.debug("[HatcherEvents] Failed to emit hatcher event: %s", e)
