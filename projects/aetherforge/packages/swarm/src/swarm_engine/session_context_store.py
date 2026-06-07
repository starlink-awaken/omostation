from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Session Context Store ≡ Module
# 内涵 ≝ {Session, Context, Store}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SessionContextStore)}
# 功能 ⊢ {Session_Context, Context_Store, Store_Init}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SessionContext:
    """Represents a single session's context data."""

    session_id: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict = field(default_factory=dict)
    parent_session: str | None = None
    tags: list[str] = field(default_factory=list)


class SessionContextStore:
    """In-memory store for cross-session context with lineage tracking,
    snapshotting, and context compression.
    """

    def __init__(self) -> None:
        self.status = "active"
        self._sessions: dict[str, SessionContext] = {}
        self._snapshots: dict[str, list[dict]] = {}
        self._links: dict[str, str] = {}  # child -> parent

    def save_context(self, ctx: SessionContext) -> None:
        """Persist a session context."""
        self._sessions[ctx.session_id] = ctx
        if ctx.parent_session:
            self._links[ctx.session_id] = ctx.parent_session

    def load_context(self, session_id: str) -> SessionContext | None:
        """Load a session context by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self, tag: str | None = None) -> list[str]:
        """List session IDs, optionally filtered by tag."""
        if tag is None:
            return list(self._sessions.keys())
        return [sid for sid, ctx in self._sessions.items() if tag in ctx.tags]

    def snapshot(self, session_id: str) -> dict:
        """Create an immutable snapshot of the session state."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            raise KeyError(f"Session '{session_id}' not found")
        snap = {
            "session_id": ctx.session_id,
            "created_at": ctx.created_at,
            "data": copy.deepcopy(ctx.data),
            "parent_session": ctx.parent_session,
            "tags": list(ctx.tags),
            "snapshot_at": datetime.now(UTC).isoformat(),
        }
        self._snapshots.setdefault(session_id, []).append(snap)
        return snap

    def restore_snapshot(self, session_id: str, snapshot: dict) -> None:
        """Restore a session from a snapshot."""
        ctx = SessionContext(
            session_id=snapshot["session_id"],
            created_at=snapshot["created_at"],
            data=copy.deepcopy(snapshot["data"]),
            parent_session=snapshot.get("parent_session"),
            tags=list(snapshot.get("tags", [])),
        )
        self._sessions[session_id] = ctx

    def link_sessions(self, parent: str, child: str) -> None:
        """Create parent-child relationship between sessions."""
        if parent not in self._sessions:
            raise KeyError(f"Parent session '{parent}' not found")
        if child not in self._sessions:
            raise KeyError(f"Child session '{child}' not found")
        self._links[child] = parent
        self._sessions[child].parent_session = parent

    def get_lineage(self, session_id: str) -> list[str]:
        """Get the ancestry chain from the given session to the root."""
        lineage = [session_id]
        current = session_id
        visited: set[str] = {current}
        while current in self._links:
            parent = self._links[current]
            if parent in visited:
                break
            lineage.append(parent)
            visited.add(parent)
            current = parent
        return lineage

    def compress_context(self, session_id: str, max_keys: int = 50) -> SessionContext:
        """Compress session context to keep only the most recent max_keys entries.

        Uses insertion order (Python 3.7+ dict ordering) as proxy for recency.
        """
        ctx = self._sessions.get(session_id)
        if ctx is None:
            raise KeyError(f"Session '{session_id}' not found")
        if len(ctx.data) <= max_keys:
            return ctx
        keys = list(ctx.data.keys())
        keep = keys[-max_keys:]
        ctx.data = {k: ctx.data[k] for k in keep}
        return ctx
