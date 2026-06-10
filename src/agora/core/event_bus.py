"""Event Bus — lightweight publish-subscribe engine.

Design decisions (per spec 103-agora-upgrade-spec.md §3.2):
- JSON persistence (agora-events.json), zero additional dependencies
- HTTP POST push to subscriber callback endpoints
- At-least-once delivery, retry 3 times
- Pattern matching: exact ("index:done"), prefix ("index:*"), catch-all ("*")
- Auto-truncate event log at 1000 events (keep last 500)
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]


@dataclass
class Subscription:
    id: str
    service: str
    pattern: str
    callback_url: str = ""
    created: str = ""
    last_seen: float = 0.0  # UTC timestamp for TTL cleanup


class EventBus:
    """Publish-subscribe event engine with JSON persistence."""

    def __init__(
        self,
        storage_path: str | None = None,
        registry: ServiceRegistry | None = None,
        subscription_ttl_hours: float = 24.0,
    ):
        self._storage_path = Path(
            storage_path
            or str(Path(__file__).parent.parent.parent / "agora-events.json")
        )
        self._registry = registry
        self._events: list[dict] = []
        self._subscriptions: dict[str, Subscription] = {}
        self._max_events = 1000
        self._subscription_ttl = subscription_ttl_hours * 3600
        self._hooks: list[
            Callable[[dict], None]
        ] = []  # registered hooks (for audit, metrics, etc.)
        self._save_counter = 0  # batch save counter: save every N publishes
        self._load()

    def _load(self):
        from agora.persistence import json_load  # type: ignore[import-not-found]

        data = json_load(
            self._storage_path, default={"events": [], "subscriptions": []}
        )
        if not isinstance(data, dict):
            data = {}

        events = data.get("events", [])
        self._events = events if isinstance(events, list) else []

        subscriptions = data.get("subscriptions", [])
        if not isinstance(subscriptions, list):
            subscriptions = []
        for s in subscriptions:
            if not isinstance(s, dict):
                continue
            sub = Subscription(**s)
            self._subscriptions[sub.id] = sub
        max_events = data.get("max_events", 1000)
        self._max_events = max_events if isinstance(max_events, int) else 1000

    def _save(self):
        from agora.persistence import json_save

        json_save(
            self._storage_path,
            {
                "events": self._events,
                "subscriptions": [
                    {
                        "id": s.id,
                        "service": s.service,
                        "pattern": s.pattern,
                        "callback_url": s.callback_url,
                        "created": s.created,
                    }
                    for s in self._subscriptions.values()
                ],
                "max_events": self._max_events,
            },
        )

    def _match(self, pattern: str, event_type: str) -> bool:
        """Check if event_type matches subscription pattern."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type

    def publish(
        self, event_type: str, payload: dict, source: str = "", trace_id: str = ""
    ) -> str:
        """Publish event. Returns event_id.

        Args:
            event_type: Event type (e.g., 'pipeline:started')
            payload: Event payload
            source: Event source service
            trace_id: Associated trace ID for correlation (新增)
        """
        event_id = f"evt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        event = {
            "id": event_id,
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source or "unknown",
            "type": event_type,
            "trace_id": trace_id,  # 新增：关联 trace
            "payload": payload,
        }

        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-500:]  # Keep last 500
        self._save_counter += 1
        self._save()

        # Notify registered hooks (audit, metrics, logging, etc.)
        for hook in self._hooks:
            with contextlib.suppress(Exception):
                hook(event)

        # Deliver to matching subscribers (async if loop available, sync otherwise)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._deliver(event))
        except RuntimeError:
            # No running loop (CLI context) — fire and forget ok
            pass
        return event_id

    async def _deliver(self, event: dict):
        """Deliver event to all matching subscribers with retry."""
        import httpx

        for sub in self._subscriptions.values():
            if not self._match(sub.pattern, event["type"]):
                continue

            callback = sub.callback_url
            if not callback and self._registry:
                svc = self._registry.get(sub.service)
                if svc and svc.health_endpoint:
                    callback = svc.health_endpoint.rstrip("/") + "/events"

            if not callback:
                continue

            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        r = await client.post(callback, json=event)
                        if r.status_code < 500:
                            break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                    else:
                        import structlog

                        _logger = structlog.get_logger(__name__)
                        _logger.warning(
                            "event_delivery_failed",
                            event_id=event["id"],
                            subscriber=sub.id,
                            callback=callback,
                        )

    def subscribe(self, service: str, pattern: str, callback_url: str = "") -> str:
        """Subscribe to events. Returns subscription_id."""
        self._cleanup_expired()
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        sub = Subscription(
            id=sub_id,
            service=service,
            pattern=pattern,
            callback_url=callback_url,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            last_seen=time.time(),
        )
        self._subscriptions[sub_id] = sub
        self._save()
        return sub_id

    def _cleanup_expired(self):
        """Remove subscriptions older than TTL (dead subscriber cleanup)."""
        now = time.time()
        expired = [
            sid
            for sid, sub in self._subscriptions.items()
            if now - sub.last_seen > self._subscription_ttl
        ]
        for sid in expired:
            del self._subscriptions[sid]
        if expired:
            self._save()

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. Returns True if removed."""
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            self._save()
            return True
        return False

    def get_event_log(self, limit: int = 50, since: str = "") -> list[dict]:
        """Query historical events."""
        events = self._events
        if since:
            events = [e for e in events if e.get("time", "") > since]
        return events[-limit:]

    # ── Hook API ────────────────────────────────────────────────
    # Hooks are callables that receive each published event.
    # Order of registration is preserved. Exceptions are caught so
    # one failed hook never blocks other hooks or event publishing.

    def register_hook(self, callback: Callable[[dict], None]):
        """Register a callback to be notified on every published event.

        Args:
            callback: Function(event: dict) -> None. Receives the full event dict
                      after it's persisted to the event log.
        """
        if callback not in self._hooks:
            self._hooks.append(callback)

    def remove_hook(self, callback: Callable[[dict], None]):
        """Remove a previously registered hook.

        Args:
            callback: The same callback reference that was registered.
                      Silent if the callback was never registered.
        """
        with contextlib.suppress(ValueError):
            self._hooks.remove(callback)

    def clear_hooks(self):
        """Remove all registered hooks. Used during shutdown/testing."""
        self._hooks.clear()

    def list_subscriptions(self) -> list[dict]:
        """List all subscriptions."""
        return [
            {
                "id": s.id,
                "service": s.service,
                "pattern": s.pattern,
                "callback_url": s.callback_url,
                "created": s.created,
            }
            for s in self._subscriptions.values()
        ]

    def has_push_subscribers(self) -> bool:
        """Return True if any subscription has a callback URL configured."""
        return any(s.callback_url for s in self._subscriptions.values())
