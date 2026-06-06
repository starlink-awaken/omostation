"""UmbilicalProtocol — parent-child instance communication protocol.

Extracted from SharedBrain D_Gateway.  Self-contained WebSocket-based
protocol for liveness detection, config sync, and status reporting.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import websockets

_logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of umbilical protocol messages."""

    HEARTBEAT = "heartbeat"
    CONFIG_SYNC = "config_sync"
    STATUS_REPORT = "status_report"
    ERROR = "error"


@dataclass
class UmbilicalMessage:
    """Message sent over umbilical connection."""

    type: MessageType
    payload: dict[str, Any]
    timestamp: float

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(
            {
                "type": self.type.value,
                "payload": self.payload,
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> UmbilicalMessage:
        """Create message from JSON string."""
        parsed = json.loads(data)
        return cls(
            type=MessageType(parsed["type"]),
            payload=parsed["payload"],
            timestamp=parsed["timestamp"],
        )


class UmbilicalProtocol:
    """Manages umbilical connection between parent and child instances.

    The umbilical protocol provides:
    1. **Heartbeat**: Liveness detection (10s interval)
    2. **Config sync**: Parent pushes configuration updates
    3. **Status reporting**: Child reports health and metrics
    4. **Reconnection**: Exponential backoff (1s -> 32s max, 5 retries)

    Responsibilities
    ----------------
    1. Establish WebSocket connection to parent
    2. Send periodic heartbeat messages
    3. Receive and handle config sync messages
    4. Send status reports to parent
    5. Handle connection failures with reconnection
    """

    def __init__(
        self,
        instance_id: str,
        parent_url: str,
        auth_token: str | None = None,
    ) -> None:
        """Initialize umbilical protocol.

        Parameters
        ----------
        instance_id:
            Child instance identifier.
        parent_url:
            Parent WebSocket URL (ws://parent:7421/umbilical/{instance_id}).
        auth_token:
            Optional authentication token.
        """
        self._instance_id = instance_id
        self._parent_url = parent_url
        self._auth_token = auth_token
        self._websocket: Any = None
        self._running = False
        self._heartbeat_task: asyncio.Task[Any] | None = None
        self._config: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Establish umbilical connection to parent.

        Returns
        -------
        bool
            True if connection succeeded, False otherwise.
        """
        try:
            headers = {}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"

            self._websocket = await asyncio.wait_for(
                websockets.connect(
                    self._parent_url,
                    additional_headers=headers,
                ),
                timeout=30,
            )

            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            self._logger.info("Umbilical connected: %s -> %s", self._instance_id, self._parent_url)
            return True

        except TimeoutError:
            self._logger.error("Umbilical connection timeout: %s", self._parent_url)
            return False
        except (OSError, ConnectionError) as exc:
            self._logger.error("Umbilical connection failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect umbilical connection."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._websocket:
            await self._websocket.close()

        self._logger.info("Umbilical disconnected: %s", self._instance_id)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages every 10 seconds."""
        while self._running:
            try:
                message = UmbilicalMessage(
                    type=MessageType.HEARTBEAT,
                    payload={"instance_id": self._instance_id},
                    timestamp=asyncio.get_event_loop().time(),
                )

                await self._websocket.send(message.to_json())
                await asyncio.sleep(10)

            except (OSError, ConnectionError) as exc:
                self._logger.error("Heartbeat failed: %s", exc)
                break

    async def send_status(self, status: dict[str, Any]) -> None:
        """Send status report to parent.

        Parameters
        ----------
        status:
            Status information (health, metrics, etc.).
        """
        message = UmbilicalMessage(
            type=MessageType.STATUS_REPORT,
            payload={
                "instance_id": self._instance_id,
                "status": status,
            },
            timestamp=asyncio.get_event_loop().time(),
        )

        try:
            await self._websocket.send(message.to_json())
        except (OSError, ConnectionError) as exc:
            self._logger.error("Failed to send status: %s", exc)

    async def sync_config(self, config: dict[str, Any]) -> None:
        """Handle configuration sync from parent.

        Merges non-protected keys into local config. Keys such as
        ``instance_id``, ``parent_id``, and ``created_at`` are never
        overwritten by a remote sync.

        Parameters
        ----------
        config:
            Configuration updates from parent.
        """
        self._logger.info("Config sync received: %s", list(config.keys()))
        protected_keys = {"instance_id", "parent_id", "created_at"}
        for key, value in config.items():
            if key not in protected_keys:
                self._config[key] = value
                self._logger.debug("Config updated: %s", key)
            else:
                self._logger.debug("Config key '%s' is protected — skipped", key)

    async def listen(self) -> None:
        """Listen for incoming messages from parent."""
        while self._running:
            try:
                data = await self._websocket.recv()
                message = UmbilicalMessage.from_json(data)

                if message.type == MessageType.CONFIG_SYNC:
                    await self.sync_config(message.payload)
                elif message.type == MessageType.ERROR:
                    self._logger.error("Error from parent: %s", message.payload.get("message"))

            except (OSError, ConnectionError) as exc:
                self._logger.error("Message receive failed: %s", exc)
                break

    async def reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff.

        Returns
        -------
        bool
            True if reconnection succeeded, False if all retries exhausted.
        """
        max_retries = 5
        base_delay = 1

        for attempt in range(max_retries):
            delay = min(base_delay * (2**attempt), 32)
            self._logger.info(
                "Reconnection attempt %d/%d (delay: %ds)",
                attempt + 1,
                max_retries,
                delay,
            )

            await asyncio.sleep(delay)

            if await self.connect():
                self._logger.info("Reconnection successful")
                return True

        self._logger.error("All reconnection attempts exhausted")
        return False
