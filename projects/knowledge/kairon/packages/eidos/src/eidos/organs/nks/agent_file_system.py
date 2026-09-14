"""Agent file system — file system abstraction for NKS pipeline operations.

Provides agent file system with basic snapshot and operation logging support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FileNode:
    """A node in the agent file system tree."""

    path: str
    content: str = ""
    file_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[FileNode] = field(default_factory=list)


@dataclass
class OperationLog:
    """A log entry for a file system operation."""

    operation: str  # create, read, update, delete
    path: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    """A point-in-time snapshot of the file system state."""

    id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    files: dict[str, FileNode] = field(default_factory=dict)


class AgentFileSystem:
    """Agent file system abstraction for NKS pipeline operations."""

    def __init__(self, root_dir: str, db_path: str | None = None) -> None:
        self.root_dir = root_dir
        self.db_path = db_path
        self._files: dict[str, FileNode] = {}
        self._operation_log: list[OperationLog] = []

    def read_file(self, path: str) -> FileNode | None:
        """Read a file from the file system."""
        return self._files.get(path)

    def write_file(
        self, path: str, content: str, content_type: str = "", metadata: dict | None = None, op_id: str | None = None
    ) -> FileNode:
        """Write content to a file in the file system."""
        node = FileNode(path=path, content=content, file_type=content_type)
        self._files[path] = node
        self._operation_log.append(OperationLog(operation="write", path=path))
        return node

    def delete_file(self, path: str, op_id: str | None = None) -> bool:
        """Delete a file from the file system."""
        if path in self._files:
            del self._files[path]
            self._operation_log.append(OperationLog(operation="delete", path=path))
            return True
        return False

    def list_files(self, directory: str = "") -> list[str]:
        """List file paths in the file system."""
        return list(self._files.keys())

    def get_file_node(self, path: str) -> FileNode | None:
        """Get a file node by path (stub)."""
        return self._files.get(path)

    def create_snapshot(self, description: str = "", metadata: dict | None = None) -> Snapshot:
        """Create a snapshot (stub)."""
        return Snapshot(id="", files=dict(self._files))

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Get a snapshot by ID (stub)."""
        return None

    def list_snapshots(self, limit: int = 100) -> list[Snapshot]:
        """List snapshots (stub)."""
        return []

    def get_operations_log(
        self, since: float | None = None, snapshot_id: str | None = None, limit: int = 1000
    ) -> list[OperationLog]:
        """Get operations log (stub)."""
        return list(self._operation_log)

    def ping(self) -> bool:
        """Check health (stub)."""
        return True

    def take_snapshot(self, snapshot_id: str) -> Snapshot:
        """Take a snapshot of the current state."""
        return Snapshot(id=snapshot_id, files=dict(self._files))

    def get_operation_log(self) -> list[OperationLog]:
        """Get the full operation log."""
        return list(self._operation_log)


__all__ = [
    "AgentFileSystem",
    "FileNode",
    "OperationLog",
    "Snapshot",
]
