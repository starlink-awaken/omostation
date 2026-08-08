"""Bus backends — pluggable transport implementations.

R61 status: 5 backends available.
  - eventbus   : wraps agora.core.event_bus (default, in-process)
  - croniter   : scheduled jobs (cron expressions)
  - asyncio    : in-process pub/sub via asyncio.Queue
  - messagebus : agent-to-agent request/response
  - sse        : server-sent events fanout (R60)

Cross-repo adapter authors: use the `BusBackend` Protocol to type your
own backend; register it in `agora.bus._backends` if you want the facade
to dispatch to it by name.
"""

from agora.bus.backends.asyncio import AsyncioBackend
from agora.bus.backends.base import BusBackend
from agora.bus.backends.croniter import CroniterBackend
from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.backends.messagebus import MessageBusBackend
from agora.bus.backends.sse import SSEBackend

__all__ = [
    "AsyncioBackend",
    "BusBackend",
    "CroniterBackend",
    "EventBusBackend",
    "MessageBusBackend",
    "SSEBackend",
]
