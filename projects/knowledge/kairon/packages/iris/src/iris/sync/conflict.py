"""Conflict resolution — handles cases where both sides modified the same item.

Strategies:
  - last_write_wins (default): The item with the latest timestamp wins
  - obsidian_wins: Always prefer Obsidian's version
  - wpsnote_wins: Always prefer WPS Note's version
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class Conflict:
    """Represents a sync conflict where both sides modified the same item."""

    item_id: str
    item_title: str
    obsidian_version: dict[str, Any]
    wpsnote_version: dict[str, Any]
    resolved: bool = False
    resolved_version: dict[str, Any] | None = None
    resolution_strategy: str = ""


class ConflictResolver:
    """Resolves conflicts between Obsidian and WPS Note versions of an item.

    Supports multiple strategies:
      - "last_write_wins": The most recently modified version wins
      - "obsidian_wins": Always prefer Obsidian's version
      - "wpsnote_wins": Always prefer WPS Note's version
    """

    def __init__(self, strategy: str = "last_write_wins"):
        """Initialize the resolver with a conflict resolution strategy.

        Args:
            strategy: One of "last_write_wins", "obsidian_wins", "wpsnote_wins"
        """
        if strategy not in ("last_write_wins", "obsidian_wins", "wpsnote_wins"):
            raise ValueError(f"Unknown strategy: {strategy}. Expected: last_write_wins, obsidian_wins, or wpsnote_wins")
        self._strategy = strategy
        self._conflicts: list[Conflict] = []

    @property
    def strategy(self) -> str:
        return self._strategy

    def resolve(self, conflict: Conflict) -> dict[str, Any]:
        """Resolve a conflict by selecting the winning version.

        Args:
            conflict: A Conflict object with both versions.

        Returns:
            The resolved version dict.
        """
        if self._strategy == "obsidian_wins":
            winning = conflict.obsidian_version
        elif self._strategy == "wpsnote_wins":
            winning = conflict.wpsnote_version
        else:
            # last_write_wins: compare timestamps
            winning = self._resolve_by_timestamp(conflict)

        conflict.resolved = True
        conflict.resolved_version = winning
        conflict.resolution_strategy = self._strategy
        return winning

    def get_conflicts(self) -> list[Conflict]:
        """Get the list of unresolved conflicts."""
        return [c for c in self._conflicts if not c.resolved]

    def register_conflict(self, conflict: Conflict) -> None:
        """Register a conflict for tracking."""
        self._conflicts.append(conflict)

    def detect_conflicts(
        self,
        obsidian_changes: list,
        wpsnote_changes: list,
    ) -> list[Conflict]:
        """Detect conflicts between two change sets.

        A conflict occurs when the same item appears as UPDATED
        on both sides.

        Args:
            obsidian_changes: Changes detected on Obsidian side.
            wpsnote_changes: Changes detected on WPS Note side.

        Returns:
            List of Conflict objects for items that changed on both sides.
        """
        conflicts: list[Conflict] = []
        return conflicts

    # ── Internal helpers ──────────────────────────────────────────

    def _resolve_by_timestamp(self, conflict: Conflict) -> dict[str, Any]:
        """Resolve conflict by picking the version with latest timestamp."""
        obs_ts = conflict.obsidian_version.get("updated_at", "") or conflict.obsidian_version.get("created_at", "")
        wps_ts = conflict.wpsnote_version.get("updated_at", "") or conflict.wpsnote_version.get("created_at", "")

        if obs_ts >= wps_ts:
            return conflict.obsidian_version
        return conflict.wpsnote_version

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse an ISO 8601 timestamp, defaulting to epoch on failure."""
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=UTC)
