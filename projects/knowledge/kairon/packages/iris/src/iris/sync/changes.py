"""Change detection — compares current state with ID mapping to find changes.

Detects four types of changes:
  - CREATED: Item exists on one side but has no mapping entry
  - UPDATED: Item exists on both sides but timestamps differ
  - DELETED: Item has a mapping but is missing on one side
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import cast

from iris.base import BaseConnector
from iris.models import Note
from iris.sync.id_map import IdMapping


class ChangeType(Enum):
    """Type of change detected during a sync cycle."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass
class Change:
    """Represents a single detected change between sync cycles."""

    type: ChangeType
    platform: str  # "obsidian" or "wpsnote"
    item_id: str  # Platform-specific ID
    item_title: str  # Human-readable title
    timestamp: str  # ISO 8601 timestamp of detection


class ChangeTracker:
    """Detects changes between Obsidian and WPS Note since last sync.

    Compares the current state of both connectors against the ID mapping
    to find new, updated, and deleted items on each side.
    """

    def __init__(
        self,
        obsidian_connector: BaseConnector,
        wpsnote_connector: BaseConnector,
        id_mapping: IdMapping,
    ):
        self._obsidian = obsidian_connector
        self._wpsnote = wpsnote_connector
        self._id_map = id_mapping

    def detect_changes(
        self,
        last_sync_at: str | None = None,
    ) -> tuple[list[Change], list[Change]]:
        """Detect changes on both sides since last sync.

        Args:
            last_sync_at: ISO 8601 timestamp of last sync. If None,
                          treats all items as newly created.

        Returns:
            Tuple of (obsidian_changes, wpsnote_changes), each being
            a list of Change objects sorted by change type.
        """
        # Fetch all items from both sides
        obsidian_items = self._fetch_all(self._obsidian)
        wpsnote_items = self._fetch_all(self._wpsnote)

        # Build lookup dicts by ID
        {item.id: item for item in obsidian_items}
        wpsnote_by_id: dict[str, Note] = {item.id: item for item in wpsnote_items}

        # Get all known mappings
        mapped_obsidian_paths = self._id_map.get_all_obsidian_paths()
        mapped_wpsnote_ids = self._id_map.get_all_wpsnote_ids()

        # For Obsidian items, we need to match by path (since base64 ID
        # encodes the relative path). Build a lookup from path→item.
        obsidian_by_path: dict[str, Note] = {}
        for item in obsidian_items:
            # The source_path contains the full vault path
            # But the mapping uses relative paths
            from pathlib import Path

            Path(item.source_path)
            # Use the relative path as the key, derived from the base64 ID
            # Since the ID is base64(relative_path), decode it back
            obsidian_by_path[item.source_path] = item

        # Detect changes
        obsidian_changes: list[Change] = []
        wpsnote_changes: list[Change] = []

        now = datetime.now(UTC).isoformat()

        # ── Obsidian-side changes ──
        for item in obsidian_items:
            obs_path = self._get_obsidian_rel_path(item)
            if obs_path is None:
                continue

            if not self._id_map.has(obs_path):
                # New Obsidian item, not yet mapped
                obsidian_changes.append(
                    Change(
                        type=ChangeType.CREATED,
                        platform="obsidian",
                        item_id=item.id,
                        item_title=item.title,
                        timestamp=now,
                    )
                )
            else:
                # Known item — check if updated
                wps_id = self._id_map.get_wpsnote_id(obs_path)
                if wps_id and wps_id in wpsnote_by_id:
                    wps_item = wpsnote_by_id[wps_id]
                    if self._is_newer(item, wps_item):
                        obsidian_changes.append(
                            Change(
                                type=ChangeType.UPDATED,
                                platform="obsidian",
                                item_id=item.id,
                                item_title=item.title,
                                timestamp=now,
                            )
                        )

        # Check for deletions on Obsidian side
        for obs_path in mapped_obsidian_paths:
            # Check if the path still exists in Obsidian
            found = False
            for item in obsidian_items:
                if self._get_obsidian_rel_path(item) == obs_path:
                    found = True
                    break
            if not found:
                wps_id = self._id_map.get_wpsnote_id(obs_path)
                title = obs_path
                obsidian_changes.append(
                    Change(
                        type=ChangeType.DELETED,
                        platform="obsidian",
                        item_id=obs_path,  # Use path as ID for deletion tracking
                        item_title=title,
                        timestamp=now,
                    )
                )

        # ── WPS Note-side changes ──
        for item in wpsnote_items:
            wps_id = item.id

            if wps_id not in mapped_wpsnote_ids:
                # New WPS Note item, not yet mapped
                wpsnote_changes.append(
                    Change(
                        type=ChangeType.CREATED,
                        platform="wpsnote",
                        item_id=wps_id,
                        item_title=item.title,
                        timestamp=now,
                    )
                )
            else:
                # Known item — check if updated
                obs_path = self._id_map.get_obsidian_path(wps_id)
                if obs_path:
                    # Find matching Obsidian item by path
                    obs_item = None
                    for oi in obsidian_items:
                        if self._get_obsidian_rel_path(oi) == obs_path:
                            obs_item = oi
                            break
                    if obs_item and self._is_newer(item, obs_item):
                        wpsnote_changes.append(
                            Change(
                                type=ChangeType.UPDATED,
                                platform="wpsnote",
                                item_id=wps_id,
                                item_title=item.title,
                                timestamp=now,
                            )
                        )

        # Check for deletions on WPS Note side
        for wps_id in mapped_wpsnote_ids:
            if wps_id not in wpsnote_by_id:
                # Get title from mapping or use ID
                title = wps_id
                wpsnote_changes.append(
                    Change(
                        type=ChangeType.DELETED,
                        platform="wpsnote",
                        item_id=wps_id,
                        item_title=title,
                        timestamp=now,
                    )
                )

        return (obsidian_changes, wpsnote_changes)

    # ── Internal helpers ──────────────────────────────────────────

    def _get_obsidian_rel_path(self, item: Note) -> str | None:
        """Extract the relative vault path from an Obsidian Note.

        Tries source_path first, falls back to decoding the base64 ID.
        """
        if item.source_path:
            try:
                from pathlib import Path

                Path(item.source_path)
                # We don't know the vault root directly from the item,
                # but we can derive it from the base64-encoded ID
                import base64

                try:
                    padded = item.id + "=" * (-len(item.id) % 4)
                    rel_path = base64.urlsafe_b64decode(padded.encode()).decode()
                    return rel_path
                except Exception:
                    pass
            except Exception:
                pass
        return item.source_path or item.id

    def _is_newer(self, item_a: Note, item_b: Note) -> bool:
        """Compare two items and return True if item_a is newer.

        Compares updated_at timestamps. If either is empty,
        compares created_at or returns False.
        """
        ts_a = item_a.updated_at or item_a.created_at
        ts_b = item_b.updated_at or item_b.created_at
        if not ts_a or not ts_b:
            return False
        return ts_a > ts_b

    def _fetch_all(self, connector: BaseConnector) -> list[Note]:
        """Fetch all items from a connector, handling pagination."""
        all_items: list[Note] = []
        cursor: str | None = None
        limit = 100
        while True:
            batch = cast(list[Note], connector.list_items(limit=limit, cursor=cursor))
            if not batch:
                break
            all_items.extend(batch)
            if len(batch) < limit:
                break
            # For pagination: the last item's ID can be used as cursor
            cursor = str(len(all_items))
        return all_items
