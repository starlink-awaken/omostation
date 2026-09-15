"""Context compressor — manages memory entries with compression and tier promotion.

Provides context compression with basic summarization support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryEntry:
    """A single memory entry with content, metadata, and tier information."""

    id: str
    content: str
    tier: str = "hot"  # hot, warm, cold, archive
    access_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    token_count: int = 0


class ContextCompressor:
    """Compresses and manages memory context across tiers."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries = max_entries
        self._entries: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry."""
        self._entries[entry.id] = entry
        self._maybe_compact()

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        return self._entries.get(entry_id)

    def summarize_batch(self, entries: list[Any]) -> Any:
        """Summarize a batch of entries into one MemoryEntry (合并策略 MVP).

        合并 entries 的 content (拼接 + token 累加), 生成 summary MemoryEntry.
        非 LLM 摘要 — 简单合并策略 (TODO: LLM 摘要后续).
        """
        if not entries:
            return None
        contents: list[str] = []
        total_tokens = 0
        for e in entries:
            content = getattr(e, "content", str(e))
            contents.append(content)
            total_tokens += getattr(e, "token_count", 0) or 0
        ts = datetime.utcnow().isoformat()
        return MemoryEntry(
            id=f"summary-{ts}",
            content="\n---\n".join(contents),
            tier="warm",
            token_count=total_tokens,
            metadata={"summarized_count": len(entries), "strategy": "merge"},
        )

    def _maybe_compact(self) -> None:
        """Evict oldest cold entries if over capacity."""
        if len(self._entries) > self.max_entries:
            cold = [e for e in self._entries.values() if e.tier == "cold"]
            cold.sort(key=lambda e: e.last_accessed)
            for entry in cold[: len(self._entries) - self.max_entries]:
                self._entries.pop(entry.id, None)


__all__ = [
    "ContextCompressor",
    "MemoryEntry",
]
