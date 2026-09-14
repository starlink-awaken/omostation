"""Memory Excretion Pipeline — identify and excrete stale entries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class MemoryExcretionPipeline:
    """Pipeline that identifies stale memory entries and excretes them.

    An entry is considered stale when its ``last_accessed`` timestamp is
    older than a configurable threshold (in days).

    Typical usage::

        pipeline = MemoryExcretionPipeline(entries=[...])
        stale = pipeline.identify_stale(days_threshold=30)
        removed = pipeline.excrete(stale)
    """

    def __init__(self, entries: list[dict] | None = None) -> None:
        """Initialize the pipeline with an optional list of entries.

        Each entry dict is expected to contain at least an ``id`` key.
        If ``last_accessed`` is present it should be an ISO-format datetime
        string; otherwise the entry is treated as never accessed (very stale).
        """
        self._entries: dict[str, dict] = {}
        if entries:
            for e in entries:
                self._entries[e["id"]] = e

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def identify_stale(self, days_threshold: int = 30) -> list[str]:
        """Return IDs of entries whose ``last_accessed`` exceeds *days_threshold*.

        Args:
            days_threshold: Number of days after which an entry is stale.

        Returns:
            Sorted list of stale entry IDs.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days_threshold)
        stale_ids: list[str] = []

        for entry_id, entry in self._entries.items():
            last_accessed_raw = entry.get("last_accessed")
            if last_accessed_raw is None:
                # Never accessed — treat as very stale
                stale_ids.append(entry_id)
                continue
            try:
                last_accessed = datetime.fromisoformat(last_accessed_raw)
            except (ValueError, TypeError):
                stale_ids.append(entry_id)
                continue
            if last_accessed < cutoff:
                stale_ids.append(entry_id)

        return sorted(stale_ids)

    def excrete(self, entry_ids: list[str]) -> list[str]:
        """Remove the given entry IDs from the pipeline and return them.

        Args:
            entry_ids: IDs to remove.

        Returns:
            The list of IDs that were actually removed.
        """
        removed: list[str] = []
        for eid in entry_ids:
            if eid in self._entries:
                del self._entries[eid]
                removed.append(eid)
        return removed
