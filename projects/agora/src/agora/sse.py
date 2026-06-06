"""Server-Sent Events (SSE) support for real-time event streaming.

Adapted from agentmesh gateway routes/sse.ts.
Provides SSE client management, event broadcasting, and connection info.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any


class SSEClient:
    """Represents a connected SSE client."""

    def __init__(self, client_id: str, queue: asyncio.Queue) -> None:
        self.id = client_id
        self.queue = queue


class SSEManager:
    """Manages SSE client connections and broadcasting."""

    def __init__(self) -> None:
        self._clients: dict[str, SSEClient] = {}

    def connect(self) -> SSEClient:
        """Create a new SSE client connection."""
        client_id = str(uuid.uuid4())
        client = SSEClient(client_id, asyncio.Queue())
        self._clients[client_id] = client
        return client

    def disconnect(self, client_id: str) -> None:
        """Remove a client connection."""
        self._clients.pop(client_id, None)

    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, event_type: str, data: Any) -> int:
        """Broadcast an event to all connected clients."""
        message = json.dumps({"type": event_type, "data": data, "timestamp": time.time() * 1000})
        sent = 0
        for client in list(self._clients.values()):
            try:
                await client.queue.put(f"data: {message}\n\n")
                sent += 1
            except Exception:
                pass
        return sent

    async def send_event(self, client_id: str, event_type: str, data: Any) -> bool:
        """Send an event to a specific client."""
        client = self._clients.get(client_id)
        if not client:
            return False
        message = json.dumps({"type": event_type, "data": data, "timestamp": time.time() * 1000})
        try:
            await client.queue.put(f"data: {message}\n\n")
            return True
        except Exception:
            return False

    def get_info(self) -> dict:
        """Get connection info for the /events info endpoint."""
        return {
            "message": "Use /events for Server-Sent Events streaming",
            "endpoints": {
                "events": "/events?task_id=<task_id>&space_id=<space_id>",
                "description": "Subscribe to real-time task updates and agent responses",
            },
            "example": "curl -N http://localhost:3100/v1/events?task_id=<task_id>",
            "connected_clients": len(self._clients),
        }


# Global SSE manager singleton
sse_manager = SSEManager()
