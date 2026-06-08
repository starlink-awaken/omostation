"""Pub/sub message bus for inter-component communication.

Migrated from agentmesh engine MessageBus.
Provides asynchronous agent-to-agent messaging with publish/subscribe,
request/response patterns, and traceable message history.

Pure in-memory implementation -- no external dependencies.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ============================================================
# Constants
# ============================================================

MAX_HISTORY = 10_000
DEFAULT_REQUEST_TIMEOUT = 30.0  # seconds


# ============================================================
# Types
# ============================================================

MessageType = str  # e.g. "request", "response", "broadcast", "event", "command"
MessagePriority = int  # 0=low, 1=normal, 2=high


@dataclass
class AgentMessage:
    id: str
    from_agent: str  # "from" is reserved in Python
    to: str
    type: MessageType
    priority: MessagePriority
    payload: Any
    context_shards: list[str]
    timestamp: float
    trace_id: str
    reply_to: str | None = None

    @property
    def sender(self) -> str:
        return self.from_agent


MessageHandler = Callable[[AgentMessage], None]


@dataclass
class _PendingRequest:
    resolve: Callable[[AgentMessage], None]
    reject: Callable[[Exception], None]
    timer: asyncio.TimerHandle | None = None


@dataclass
class BusStats:
    total: int
    by_type: dict[str, int]
    by_agent: dict[str, int]


# ============================================================
# MessageBus
# ============================================================

class MessageBus:
    """In-memory pub/sub message bus for agent communication.

    Supports:
    - Agent-addressed subscriptions
    - Message-type subscriptions
    - Request/response correlation
    - Broadcast delivery
    - FIFO message history with trace_id indexing
    """

    def __init__(self) -> None:
        self._agent_subscribers: dict[str, set[MessageHandler]] = {}
        self._type_subscribers: dict[str, set[MessageHandler]] = {}
        self._history: list[AgentMessage] = []
        self._pending_requests: dict[str, _PendingRequest] = {}

    # ----------------------------------------------------------
    # Message Factory
    # ----------------------------------------------------------

    def create_message(
        self,
        from_agent: str,
        to: str,
        type_: MessageType,
        payload: Any,
        trace_id: str | None = None,
        priority: MessagePriority = 1,
    ) -> AgentMessage:
        return AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to=to,
            type=type_,
            priority=priority,
            payload=payload,
            context_shards=[],
            timestamp=self._now(),
            trace_id=trace_id or str(uuid.uuid4()),
        )

    # ----------------------------------------------------------
    # Publish
    # ----------------------------------------------------------

    def send(self, message: AgentMessage) -> None:
        """Send a message to a specific agent. Dispatches to agent subscribers
        and type subscribers, and resolves pending request/response if applicable."""
        self._record(message)

        # Resolve pending request if this is a reply
        if message.reply_to and message.reply_to in self._pending_requests:
            pending = self._pending_requests.pop(message.reply_to)
            if pending.timer:
                pending.timer.cancel()
            pending.resolve(message)

        # Dispatch to agent-name subscribers
        handlers = self._agent_subscribers.get(message.to)
        if handlers:
            for h in list(handlers):
                self._safe_invoke(h, message)

        # Dispatch to type subscribers
        type_handlers = self._type_subscribers.get(message.type)
        if type_handlers:
            for h in list(type_handlers):
                self._safe_invoke(h, message)

    def broadcast(self, message: AgentMessage) -> None:
        """Broadcast a message to ALL agent-name subscribers and matching type subscribers."""
        msg = AgentMessage(**{**vars(message), "to": "*", "from_agent": message.from_agent})
        self._record(msg)

        for handlers in self._agent_subscribers.values():
            for h in list(handlers):
                self._safe_invoke(h, msg)

        type_handlers = self._type_subscribers.get(msg.type)
        if type_handlers:
            for h in list(type_handlers):
                self._safe_invoke(h, msg)

    # ----------------------------------------------------------
    # Subscribe
    # ----------------------------------------------------------

    def subscribe(self, agent_name: str, handler: MessageHandler) -> Callable[[], None]:
        """Subscribe to messages addressed to a specific agent. Returns unsubscribe function."""
        self._agent_subscribers.setdefault(agent_name, set()).add(handler)
        return lambda: self._unsubscribe(agent_name, handler)

    def subscribe_to_type(self, type_: MessageType, handler: MessageHandler) -> Callable[[], None]:
        """Subscribe to messages of a specific type (across all agents). Returns unsubscribe function."""
        self._type_subscribers.setdefault(type_, set()).add(handler)
        return lambda: self._unsubscribe_type(type_, handler)

    def _unsubscribe(self, agent_name: str, handler: MessageHandler) -> None:
        handlers = self._agent_subscribers.get(agent_name)
        if handlers:
            handlers.discard(handler)
            if not handlers:
                del self._agent_subscribers[agent_name]

    def _unsubscribe_type(self, type_: str, handler: MessageHandler) -> None:
        handlers = self._type_subscribers.get(type_)
        if handlers:
            handlers.discard(handler)
            if not handlers:
                del self._type_subscribers[type_]

    # ----------------------------------------------------------
    # Request / Response
    # ----------------------------------------------------------

    async def request(
        self,
        from_agent: str,
        to: str,
        payload: Any,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> AgentMessage:
        """Send a request and wait for a correlated response.

        The callee should reply by sending a message with ``reply_to`` set
        to the original request's ``id``.

        Returns the response AgentMessage.
        """
        message = self.create_message(from_agent, to, "request", payload)
        loop = loop or asyncio.get_event_loop()
        future: asyncio.Future[AgentMessage] = loop.create_future()

        def resolve(msg: AgentMessage) -> None:
            if not future.done():
                future.set_result(msg)

        def reject(err: Exception) -> None:
            if not future.done():
                future.set_exception(err)

        timer = loop.call_later(timeout, lambda: reject(
            TimeoutError(f"MessageBus request timed out after {timeout}s (id={message.id})"),
        ))

        self._pending_requests[message.id] = _PendingRequest(resolve=resolve, reject=reject, timer=timer)

        # Send the request (also records history + dispatches)
        self.send(message)

        try:
            return await future
        except Exception:
            self._pending_requests.pop(message.id, None)
            raise

    # ----------------------------------------------------------
    # History
    # ----------------------------------------------------------

    def get_history(self, agent_name: str | None = None, limit: int | None = None) -> list[AgentMessage]:
        """Retrieve message history, newest first. Optionally filter by agent or limit."""
        result = self._history
        if agent_name:
            result = [m for m in result if m.from_agent == agent_name or m.to == agent_name]
        result = list(reversed(result))
        if limit is not None and limit > 0:
            result = result[:limit]
        return result

    def get_messages_by_trace_id(self, trace_id: str) -> list[AgentMessage]:
        """Return all messages sharing the same trace_id, chronologically."""
        return [m for m in self._history if m.trace_id == trace_id]

    # ----------------------------------------------------------
    # Stats
    # ----------------------------------------------------------

    def get_stats(self) -> BusStats:
        by_type: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        for msg in self._history:
            by_type[msg.type] = by_type.get(msg.type, 0) + 1
            by_agent[msg.from_agent] = by_agent.get(msg.from_agent, 0) + 1
            if msg.to != "*":
                by_agent[msg.to] = by_agent.get(msg.to, 0) + 1
        return BusStats(total=len(self._history), by_type=by_type, by_agent=by_agent)

    # ----------------------------------------------------------
    # Housekeeping
    # ----------------------------------------------------------

    def clear(self) -> None:
        """Clear all history, subscriptions, and pending requests."""
        self._history.clear()

        # Reject pending requests
        for pending in self._pending_requests.values():
            if pending.timer:
                pending.timer.cancel()
            pending.reject(RuntimeError("MessageBus cleared while request was pending"))
        self._pending_requests.clear()

        self._agent_subscribers.clear()
        self._type_subscribers.clear()

    # ----------------------------------------------------------
    # Private Helpers
    # ----------------------------------------------------------

    @staticmethod
    def _now() -> float:
        import time
        return time.time()

    def _record(self, message: AgentMessage) -> None:
        self._history.append(message)
        if len(self._history) > MAX_HISTORY:
            self._history[: len(self._history) - MAX_HISTORY] = []

    @staticmethod
    def _safe_invoke(handler: MessageHandler, message: AgentMessage) -> None:
        try:
            handler(message)
        except Exception:
            pass  # Swallow subscriber errors to protect the bus
