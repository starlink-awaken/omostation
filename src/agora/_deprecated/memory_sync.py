"""
---
Type: organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Copilot'
Authority: organs/D-Gateway/AGENTS.md
Layer: L3
Summary: 'Cross-node HoloMemory incremental synchronization with last-write-wins conflict resolution.'
---
"""

from __future__ import annotations

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Memory Sync ≡ Module
# 内涵 ≝ {Memory, Sync}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, MemorySync)}
# 功能 ⊢ {Sync_Memory, Merge_Remote, Resolve_Conflicts}
# =============================================================================
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)

__all__ = ["MemoryEntry", "MemorySyncManager"]


@dataclass
class MemoryEntry:
    """A single HoloMemory key-value entry with provenance metadata."""

    key: str
    value: Any
    node_id: str  # originating node
    timestamp: float  # unix timestamp (for LWW conflict resolution)
    version: int = 1


class MemorySyncManager:
    """Manages incremental sync of HoloMemory across federation nodes.

    Storage: each entry is persisted as a JSON file under *storage_path*
    named ``<key>.json`` so the implementation stays dependency-free and
    portable across all BOS node configurations.

    Conflict resolution uses **last-write-wins**: a remote entry replaces
    a local entry when ``remote.timestamp > local.timestamp``.
    """

    def __init__(
        self, local_node_id: str, storage_path: str = "data/holo_memory/"
    ) -> None:
        self.status = "active"
        self.local_node_id = local_node_id
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        # In-memory store: key → MemoryEntry (authoritative during runtime)
        self._store: dict[str, MemoryEntry] = {}
        self._last_sync: float = 0.0
        self._nodes_synced: set[str] = set()
        self._load_from_disk()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _entry_path(self, key: str) -> str:
        safe_key = key.replace("/", "__").replace(":", "_")
        return os.path.join(self.storage_path, f"{safe_key}.json")

    def _persist(self, entry: MemoryEntry) -> None:
        try:
            with open(self._entry_path(entry.key), "w") as fh:
                json.dump(
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "node_id": entry.node_id,
                        "timestamp": entry.timestamp,
                        "version": entry.version,
                    },
                    fh,
                )
        except OSError as exc:  # pragma: no cover
            _log.warning("MemorySyncManager: failed to persist %s: %s", entry.key, exc)

    def _load_from_disk(self) -> None:
        """Load persisted entries from storage_path into in-memory store."""
        try:
            for fname in os.listdir(self.storage_path):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(self.storage_path, fname)
                try:
                    with open(fpath) as fh:
                        data = json.load(fh)
                    entry = MemoryEntry(
                        key=data["key"],
                        value=data["value"],
                        node_id=data["node_id"],
                        timestamp=data["timestamp"],
                        version=data.get("version", 1),
                    )
                    self._store[entry.key] = entry
                except (OSError, KeyError, json.JSONDecodeError) as exc:
                    _log.warning(
                        "MemorySyncManager: skipping corrupt entry %s: %s", fname, exc
                    )
        except OSError:  # pragma: no cover
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def put(self, key: str, value: Any) -> MemoryEntry:
        """Write a local entry into HoloMemory."""
        entry = MemoryEntry(
            key=key,
            value=value,
            node_id=self.local_node_id,
            timestamp=time.time(),
            version=self._store[key].version + 1 if key in self._store else 1,
        )
        self._store[key] = entry
        self._persist(entry)
        return entry

    def get(self, key: str) -> MemoryEntry | None:
        return self._store.get(key)

    def get_local_entries(self, since_timestamp: float = 0.0) -> list[MemoryEntry]:
        """Return entries created/modified on or after *since_timestamp*.

        Parameters
        ----------
        since_timestamp:
            Unix timestamp lower bound (inclusive). ``0.0`` returns all entries.
        """
        return [e for e in self._store.values() if e.timestamp >= since_timestamp]

    def merge_remote_entries(self, remote_entries: list[dict]) -> int:
        """Merge remote entries into local store using last-write-wins.

        Parameters
        ----------
        remote_entries:
            List of serialised ``MemoryEntry`` dicts (as returned by
            :meth:`to_sync_payload`).

        Returns
        -------
        int
            Count of entries actually merged (newer than existing local copy).
        """
        merged = 0
        for raw in remote_entries:
            try:
                remote = MemoryEntry(
                    key=raw["key"],
                    value=raw["value"],
                    node_id=raw["node_id"],
                    timestamp=float(raw["timestamp"]),
                    version=int(raw.get("version", 1)),
                )
            except (KeyError, TypeError, ValueError) as exc:
                _log.warning(
                    "MemorySyncManager: invalid remote entry %s — skipping: %s",
                    raw,
                    exc,
                )
                continue

            local = self._store.get(remote.key)
            if local is None or remote.timestamp > local.timestamp:
                self._store[remote.key] = remote
                self._persist(remote)
                merged += 1
                if remote.node_id != self.local_node_id:
                    self._nodes_synced.add(remote.node_id)

        self._last_sync = time.time()
        return merged

    def get_sync_state(self) -> dict:
        """Return a summary of current sync state.

        Returns
        -------
        dict
            ``{last_sync, total_entries, nodes_synced}``
        """
        return {
            "last_sync": self._last_sync,
            "total_entries": len(self._store),
            "nodes_synced": list(self._nodes_synced),
        }

    def push(self, key: str, value: Any, importance: float = 0.5) -> None:
        """Push a memory entry to the sync store."""
        entry = self.put(key, value)
        self._persist(entry)

    def pull(self) -> list[MemoryEntry]:
        """Pull all local entries from sync store."""
        return list(self._store.values())

    def to_sync_payload(self, since: float = 0.0) -> list[dict]:
        """Serialise entries for transmission to a remote node.

        Parameters
        ----------
        since:
            Only include entries with ``timestamp >= since``.
        """
        return [
            {
                "key": e.key,
                "value": e.value,
                "node_id": e.node_id,
                "timestamp": e.timestamp,
                "version": e.version,
            }
            for e in self._store.values()
            if e.timestamp >= since
        ]
