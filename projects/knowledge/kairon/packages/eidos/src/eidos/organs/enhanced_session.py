"""Enhanced session organ — session management with checkpoint support.

Provides enhanced session management with context tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EnhancedSession:
    """An enhanced session with metadata, checkpoints, and persistence support."""

    session_id: str
    user_id: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    checkpoints: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def save_checkpoint(self, name: str, data: Any) -> None:
        """Save a checkpoint."""
        self.checkpoints[name] = {"data": data, "timestamp": datetime.utcnow().isoformat()}

    def load_checkpoint(self, name: str) -> Any | None:
        """Load a checkpoint by name."""
        cp = self.checkpoints.get(name)
        return cp["data"] if cp else None


__all__ = [
    "EnhancedSession",
]
