"""Bus backends — pluggable transport implementations.

Phase B (R66) status: 5 backends available, all without agora dependency.
  - eventbus   : in-process pub/sub (default)
  - croniter   : scheduled jobs (cron expressions)
  - asyncio    : in-process pub/sub via asyncio.Queue
  - messagebus : agent-to-agent request/response
  - sse        : in-process fan-out (HTTP layer wires its own SSE)

Premium backends that wrap agora.core.* (e.g. the persistent EventBusBackend
that uses agora-events.json) STAY in agora.bus.backends. Consumers can
opt-in by importing from agora.bus.backends instead.
"""
from bus_foundation.backends.asyncio import AsyncioBackend
from bus_foundation.backends.base import BusBackend
from bus_foundation.backends.croniter import CroniterBackend
from bus_foundation.backends.eventbus import EventBusBackend
from bus_foundation.backends.messagebus import MessageBusBackend
from bus_foundation.backends.sse import SSEBackend

__all__ = [
    "AsyncioBackend",
    "BusBackend",
    "CroniterBackend",
    "EventBusBackend",
    "MessageBusBackend",
    "SSEBackend",
]
