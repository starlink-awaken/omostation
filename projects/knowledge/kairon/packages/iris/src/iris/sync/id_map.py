"""Persistent bidirectional mapping: obsidian_path ↔ wpsnote_id.

Uses JSONFileStore for durable storage of the mapping table.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from iris.store import JSONFileStore


class IdMapping:
    """Persistent bidirectional mapping between Obsidian file paths and WPS Note IDs.

    Stores mappings in a JSON file. Two lookup directions:
      - Obsidian path → WPS Note ID
      - WPS Note ID → Obsidian path
    """

    def __init__(self, store_path: str | Path | None = None):
        """Initialize with an optional JSON store path.

        If no path is given, uses ~/.iris/sync/id_map.json by default.
        """
        if store_path is None:
            store_path = Path.home() / ".iris" / "sync" / "id_map.json"
        self._store = JSONFileStore(str(store_path))

    # ── Internal helpers ──────────────────────────────────────────

    def _obsidian_key(self, path: str) -> str:
        """Internal key for obsidian→wps direction."""
        return f"o2w:{path}"

    def _wpsnote_key(self, wps_id: str) -> str:
        """Internal key for wps→obsidian direction."""
        return f"w2o:{wps_id}"

    # ── Public API ────────────────────────────────────────────────

    def set_mapping(self, obsidian_path: str, wpsnote_id: str) -> None:
        """Record a bidirectional mapping.

        Args:
            obsidian_path: Relative vault path (e.g., "folder/note.md")
            wpsnote_id: WPS Note ID (e.g., "abc123")
        """
        self._store.set(self._obsidian_key(obsidian_path), wpsnote_id)
        self._store.set(self._wpsnote_key(wpsnote_id), obsidian_path)

    def get_wpsnote_id(self, obsidian_path: str) -> str | None:
        """Look up WPS Note ID from an Obsidian path.

        Returns None if no mapping exists.
        """
        return cast("str | None", self._store.get(self._obsidian_key(obsidian_path)))

    def get_obsidian_path(self, wpsnote_id: str) -> str | None:
        """Look up Obsidian path from a WPS Note ID.

        Returns None if no mapping exists.
        """
        return cast("str | None", self._store.get(self._wpsnote_key(wpsnote_id)))

    def remove(self, obsidian_path: str) -> None:
        """Delete a mapping by Obsidian path.

        Cleans up both directions of the mapping.
        """
        wps_id = self._store.get(self._obsidian_key(obsidian_path))
        if wps_id:
            self._store.delete(self._wpsnote_key(wps_id))
        self._store.delete(self._obsidian_key(obsidian_path))

    def list_all(self) -> list[dict]:
        """List all mappings as a list of dicts.

        Each dict: {"obsidian_path": "...", "wpsnote_id": "..."}
        """
        result: list[dict[str, str]] = []
        data = self._store._data  # Access internal dict for iteration
        for key, value in data.items():
            if key.startswith("o2w:"):
                result.append({"obsidian_path": key[4:], "wpsnote_id": value})
        # Sort for deterministic output
        result.sort(key=lambda x: x["obsidian_path"])
        return result

    def has(self, obsidian_path: str) -> bool:
        """Check if a mapping exists for the given Obsidian path."""
        return self._store.get(self._obsidian_key(obsidian_path)) is not None

    def get_all_obsidian_paths(self) -> set[str]:
        """Return all Obsidian paths that have mappings."""
        paths: set[str] = set()
        for key in self._store.list_keys():
            if key.startswith("o2w:"):
                paths.add(key[4:])
        return paths

    def get_all_wpsnote_ids(self) -> set[str]:
        """Return all WPS Note IDs that have mappings."""
        ids: set[str] = set()
        for key in self._store.list_keys():
            if key.startswith("w2o:"):
                ids.add(key[4:])
        return ids
