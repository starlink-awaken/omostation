"""Context manager for agentmesh gateway migration.

Manages shared spaces (conversation contexts) with in-memory caching.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from agora.types import AgentMessage, ContextRef  # type: ignore[import-not-found]


class ContextData:
    """In-memory representation of a shared space context."""

    def __init__(self, shared_space_id: str, metadata: dict[str, Any] | None = None) -> None:
        self.shared_space_id = shared_space_id
        self.messages: list[AgentMessage] = []
        self.artifacts: dict[str, str] = {}
        self.metadata: dict[str, Any] = metadata or {}
        now = int(time.time() * 1000)
        self.created_at: int = now
        self.updated_at: int = now


class ContextManager:
    """Manages shared spaces for agent conversations and artifacts."""

    def __init__(self, base_dir: str = "./data/tasks") -> None:
        self._cache: dict[str, ContextData] = {}
        self._base_dir = base_dir

    def configure(self, base_dir: str) -> None:
        """Update the base directory for artifact storage."""
        self._base_dir = base_dir

    async def create_shared_space(self, metadata: dict[str, Any] | None = None) -> str:
        """Create a new shared space and return its ID."""
        space_id = str(uuid.uuid4())
        self._cache[space_id] = ContextData(space_id, metadata)
        return space_id

    async def get_shared_space(self, space_id: str) -> ContextData | None:
        """Retrieve a shared space by ID."""
        return self._cache.get(space_id)

    async def add_message(self, space_id: str, message: AgentMessage) -> None:
        """Add a message to a shared space."""
        ctx = await self.get_shared_space(space_id)
        if ctx is None:
            raise ValueError(f"Shared space not found: {space_id}")
        ctx.messages.append(message)
        ctx.updated_at = int(time.time() * 1000)

    async def get_messages(self, space_id: str, limit: int | None = None) -> list[AgentMessage]:
        """Get messages from a shared space, optionally limited to the most recent N."""
        ctx = await self.get_shared_space(space_id)
        if ctx is None:
            return []
        msgs = ctx.messages
        return msgs[-limit:] if limit else list(msgs)

    async def add_artifact(self, space_id: str, filename: str, content: str) -> str:
        """Persist an artifact file and return its path."""
        ctx = await self.get_shared_space(space_id)
        if ctx is None:
            raise ValueError(f"Shared space not found: {space_id}")
        artifacts_dir = Path(self._base_dir) / space_id / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        file_path = artifacts_dir / filename
        file_path.write_text(content, encoding="utf-8")
        ctx.artifacts[filename] = str(file_path)
        ctx.updated_at = int(time.time() * 1000)
        return str(file_path)

    async def get_artifact(self, space_id: str, filename: str) -> str | None:
        """Read an artifact file content by filename."""
        ctx = await self.get_shared_space(space_id)
        if ctx is None:
            return None
        file_path = ctx.artifacts.get(filename)
        if file_path is None:
            return None
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    async def create_context_ref(self, space_id: str) -> ContextRef:
        """Create a context reference pointing to a shared space."""
        return ContextRef(shared_space_id=space_id)

    def remove(self, space_id: str) -> bool:
        """Remove a shared space from memory."""
        return self._cache.pop(space_id, None) is not None


context_manager = ContextManager()
