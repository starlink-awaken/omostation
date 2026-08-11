"""Independent bounded subscriber queues with safe, immutable events."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, cast

import anyio
from anyio import ClosedResourceError, EndOfStream, WouldBlock
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

_SECRET_KEY = re.compile(r"(?:authorization|api[_-]?key|token|password|secret)", re.I)
_SECRET_TEXT = re.compile(
    r"(?:authorization\s*:|bearer\s+\S+|api[_-]?key\s*[=:]|"
    r"token\s*[=:]|password\s*[=:]|secret\s*[=:])",
    re.I,
)
_MAX_PAYLOAD_BYTES = 64 * 1024
type _JsonScalar = str | int | float | bool | None
type _FrozenJson = _JsonScalar | tuple[_FrozenJson, ...] | Mapping[str, _FrozenJson]


class InvalidEventError(ValueError):
    """An event failed schema, size, time, or payload validation."""


class EventSubscriptionClosed(RuntimeError):
    """The subscription has explicit end-of-stream semantics."""


class EventPriority(StrEnum):
    LOW = "low"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    schema_version: int
    timestamp: datetime
    event_id: str
    priority: EventPriority
    kind: str
    payload: Mapping[str, _FrozenJson]
    request_id: str | None = None
    job_id: str | None = None
    resource_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        priority: EventPriority,
        kind: str,
        timestamp: datetime,
        payload: Mapping[str, object],
        schema_version: int = 1,
        request_id: str | None = None,
        job_id: str | None = None,
        resource_id: str | None = None,
    ) -> RuntimeEvent:
        if schema_version != 1:
            raise InvalidEventError("unsupported event schema version")
        if not event_id or not kind:
            raise InvalidEventError("event ID and kind are required")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidEventError("event timestamp must be timezone-aware")
        normalized = timestamp.astimezone(UTC)
        frozen = _freeze_mapping(payload)
        encoded = _payload_json(frozen)
        if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
            raise InvalidEventError("event payload exceeds the size limit")
        return cls(
            schema_version=schema_version,
            timestamp=normalized,
            event_id=event_id,
            priority=priority,
            kind=kind,
            payload=frozen,
            request_id=request_id,
            job_id=job_id,
            resource_id=resource_id,
        )

    def payload_json(self) -> str:
        return _payload_json(self.payload)


@dataclass(frozen=True, slots=True)
class EventPublishOutcome:
    delivered: int
    dropped: int


class DurableEventStore(Protocol):
    async def append_durable_event(
        self,
        *,
        event_id: str,
        schema_version: int,
        observed_at: datetime,
        priority: str,
        kind: str,
        payload_json: str,
        job_id: str | None,
        resource_id: str | None,
    ) -> int: ...


class EventSubscription:
    def __init__(
        self,
        receiver: MemoryObjectReceiveStream[RuntimeEvent],
        close_callback: Callable[[], Awaitable[None]],
    ) -> None:
        self._receiver = receiver
        self._close_callback = close_callback
        self._closed = False

    async def receive(self) -> RuntimeEvent:
        if self._closed:
            raise EventSubscriptionClosed("event subscription is closed")
        try:
            return await self._receiver.receive()
        except (ClosedResourceError, EndOfStream):
            raise EventSubscriptionClosed("event subscription is closed") from None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._receiver.aclose()
        await self._close_callback()


class EventBus:
    def __init__(self, *, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("event subscriber capacity must be greater than zero")
        self._capacity = capacity
        self._next_subscriber = 0
        self._senders: dict[int, MemoryObjectSendStream[RuntimeEvent]] = {}
        self._closed = False
        self._dropped_low_priority = 0

    @property
    def dropped_low_priority(self) -> int:
        return self._dropped_low_priority

    def subscribe(self) -> EventSubscription:
        if self._closed:
            raise EventSubscriptionClosed("event bus is closed")
        sender, receiver = anyio.create_memory_object_stream[RuntimeEvent](self._capacity)
        subscriber_id = self._next_subscriber
        self._next_subscriber += 1
        self._senders[subscriber_id] = sender

        async def remove() -> None:
            registered = self._senders.pop(subscriber_id, None)
            if registered is not None:
                await registered.aclose()

        return EventSubscription(receiver, remove)

    async def publish(self, event: RuntimeEvent) -> EventPublishOutcome:
        if self._closed:
            raise EventSubscriptionClosed("event bus is closed")
        delivered = 0
        dropped = 0
        disconnected: list[int] = []
        for subscriber_id, sender in tuple(self._senders.items()):
            try:
                sender.send_nowait(event)
                delivered += 1
            except WouldBlock:
                dropped += 1
                if event.priority is EventPriority.LOW:
                    self._dropped_low_priority += 1
                else:
                    disconnected.append(subscriber_id)
            except ClosedResourceError:
                disconnected.append(subscriber_id)
        for subscriber_id in disconnected:
            sender = self._senders.pop(subscriber_id, None)
            if sender is not None:
                await sender.aclose()
        return EventPublishOutcome(delivered=delivered, dropped=dropped)

    async def publish_durable(self, store: DurableEventStore, event: RuntimeEvent) -> int:
        if event.priority is not EventPriority.HIGH:
            raise InvalidEventError("only high-priority events use durable publication")
        sequence = await store.append_durable_event(
            event_id=event.event_id,
            schema_version=event.schema_version,
            observed_at=event.timestamp,
            priority=event.priority.value,
            kind=event.kind,
            payload_json=event.payload_json(),
            job_id=event.job_id,
            resource_id=event.resource_id,
        )
        await self.publish(event)
        return sequence

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        senders = tuple(self._senders.values())
        self._senders.clear()
        for sender in senders:
            await sender.aclose()


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, _FrozenJson]:
    frozen: dict[str, _FrozenJson] = {}
    for key, item in value.items():
        frozen[key] = "[REDACTED]" if _SECRET_KEY.search(key) else _freeze(item)
    return MappingProxyType(frozen)


def _freeze(value: object) -> _FrozenJson:
    if isinstance(value, str):
        return "[REDACTED]" if _SECRET_TEXT.search(value) else value
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidEventError("event payload numbers must be finite")
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(cast(Mapping[str, object], value))
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return tuple(_freeze(item) for item in sequence)
    raise InvalidEventError("event payload must be JSON serializable")


def _thaw(value: _FrozenJson) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _payload_json(value: Mapping[str, _FrozenJson]) -> str:
    return json.dumps(_thaw(value), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
