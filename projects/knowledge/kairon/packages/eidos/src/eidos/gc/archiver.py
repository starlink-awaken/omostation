"""Archive Manager — tiered storage with TTL policies, archive/retrieve/list lifecycle."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StorageTier(StrEnum):
    """Storage temperature tiers."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class ArchiveEntry:
    """A single archived entry with metadata.

    Attributes:
        entry_id: Unique identifier.
        tier: Current storage tier.
        data: The archived payload.
        created_at: Unix timestamp of archival.
        last_accessed: Unix timestamp of last retrieval.
        ttl_days: Days until expiry; 0 or negative means never.
        size_bytes: Estimated size of serialised data.
        metadata: Arbitrary key-value metadata.
    """

    entry_id: str
    tier: StorageTier = StorageTier.WARM
    data: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl_days: int = 90
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_days(self) -> float:
        """Return age in days."""
        return (time.time() - self.created_at) / 86400.0

    @property
    def is_expired(self) -> bool:
        """True if the entry has exceeded its TTL."""
        if self.ttl_days <= 0:
            return False
        return self.age_days > self.ttl_days


@dataclass
class ArchivePolicy:
    """Rules for what gets archived when.

    Attributes:
        max_hot_entries: Maximum entries in hot tier before demotion.
        max_warm_entries: Maximum entries in warm tier before demotion.
        hot_ttl_days: Default TTL for hot tier entries.
        warm_ttl_days: Default TTL for warm tier entries.
        cold_ttl_days: Default TTL for cold tier entries.
        hot_idle_days: Idle time after which a hot entry demotes to warm.
        warm_idle_days: Idle time after which a warm entry demotes to cold.
        min_importance_keep: Importance below this → eligible for demotion/purge.
    """

    max_hot_entries: int = 1000
    max_warm_entries: int = 10000
    hot_ttl_days: int = 7
    warm_ttl_days: int = 90
    cold_ttl_days: int = 365
    hot_idle_days: int = 1
    warm_idle_days: int = 30
    min_importance_keep: float = 0.1


class TieredStorage:
    """Encapsulates the hot/warm/cold storage tier management.

    Provides tier-aware put/get/delete with automatic demotion when tier
    capacity is exceeded.  Used internally by :class:`ArchiveManager`
    but also usable standalone for simple tiered key/value storage.

    Typical usage::

        ts = TieredStorage()
        ts.put("key1", {"val": 42}, tier=StorageTier.HOT)
        entry = ts.get("key1")
        ts.demote_if_needed()
    """

    def __init__(self, policy: ArchivePolicy | None = None) -> None:
        self._policy = policy or ArchivePolicy()
        self._tiers: dict[StorageTier, dict[str, ArchiveEntry]] = {
            StorageTier.HOT: {},
            StorageTier.WARM: {},
            StorageTier.COLD: {},
        }

    def put(
        self,
        entry_id: str,
        data: dict,
        tier: StorageTier = StorageTier.WARM,
        ttl_days: int = 90,
    ) -> ArchiveEntry:
        """Store *data* in *tier* under *entry_id*."""
        entry = ArchiveEntry(entry_id=entry_id, tier=tier, data=data, ttl_days=ttl_days)
        self._tiers[tier][entry_id] = entry
        self.demote_if_needed()
        return entry

    def get(self, entry_id: str) -> ArchiveEntry | None:
        """Retrieve an entry from any tier."""
        for tier in (StorageTier.HOT, StorageTier.WARM, StorageTier.COLD):
            if entry_id in self._tiers[tier]:
                entry = self._tiers[tier][entry_id]
                entry.last_accessed = time.time()
                return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """Remove an entry from all tiers."""
        for tier in (StorageTier.HOT, StorageTier.WARM, StorageTier.COLD):
            if entry_id in self._tiers[tier]:
                del self._tiers[tier][entry_id]
                return True
        return False

    def demote_if_needed(self) -> int:
        """Demote overflow entries from hot->warm and warm->cold.

        Returns the number of entries demoted.
        """
        demoted = 0
        # Hot -> Warm
        hot_count = len(self._tiers[StorageTier.HOT])
        if hot_count > self._policy.max_hot_entries:
            overflow = sorted(self._tiers[StorageTier.HOT].values(), key=lambda e: e.last_accessed)
            to_demote = hot_count - self._policy.max_hot_entries
            for entry in overflow[:to_demote]:
                del self._tiers[StorageTier.HOT][entry.entry_id]
                entry.tier = StorageTier.WARM
                self._tiers[StorageTier.WARM][entry.entry_id] = entry
                demoted += 1
        # Warm -> Cold
        warm_count = len(self._tiers[StorageTier.WARM])
        if warm_count > self._policy.max_warm_entries:
            overflow = sorted(self._tiers[StorageTier.WARM].values(), key=lambda e: e.last_accessed)
            to_demote = warm_count - self._policy.max_warm_entries
            for entry in overflow[:to_demote]:
                del self._tiers[StorageTier.WARM][entry.entry_id]
                entry.tier = StorageTier.COLD
                self._tiers[StorageTier.COLD][entry.entry_id] = entry
                demoted += 1
        return demoted

    def get_tier_stats(self) -> dict[str, int]:
        """Return per-tier entry counts."""
        return {
            "hot": len(self._tiers[StorageTier.HOT]),
            "warm": len(self._tiers[StorageTier.WARM]),
            "cold": len(self._tiers[StorageTier.COLD]),
        }


class ArchiveManager:
    """Manage tiered storage for archived entries with TTL and policy-driven lifecycle.

    Maintains backward compatibility with the existing stub API (``archive``,
    ``retrieve``, ``list_by_tier``, ``purge_expired``, ``get_stats``) while
    adding full tier demotion/promotion, importance-aware retention, and
    consolidated listing.

    Typical usage::

        mgr = ArchiveManager()
        mgr.archive("doc-1", {"title": "Hello"}, tier=StorageTier.HOT, ttl_days=30)
        data = mgr.retrieve("doc-1")
        mgr.purge_expired()
        print(mgr.get_stats())
    """

    def __init__(self, policy: ArchivePolicy | None = None) -> None:
        self.policy = policy or ArchivePolicy()
        self._store: dict[str, ArchiveEntry] = {}
        self._tier_counts: dict[str, int] = {"hot": 0, "warm": 0, "cold": 0}
        self._importance: dict[str, float] = {}  # entry_id → importance score

    # ------------------------------------------------------------------
    # Backward-compatible API
    # ------------------------------------------------------------------

    def archive(
        self,
        entry_id: str,
        data: dict,
        tier: StorageTier = StorageTier.WARM,
        ttl_days: int = 90,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Archive *data* under *entry_id* in the given *tier*.

        Args:
            entry_id: Unique identifier.
            data: Payload dict.
            tier: Target storage tier.
            ttl_days: Days before expiry.
            metadata: Optional extra key-value data.

        Returns the *entry_id*.
        """
        entry = ArchiveEntry(
            entry_id=entry_id,
            tier=tier,
            data=data,
            ttl_days=ttl_days,
            size_bytes=len(str(data).encode("utf-8")),
            metadata=metadata or {},
        )
        self._store[entry_id] = entry
        self._tier_counts[tier.value] = self._tier_counts.get(tier.value, 0) + 1
        self._promote_if_needed()
        return entry_id

    def retrieve(self, entry_id: str) -> dict | None:
        """Retrieve the data payload for *entry_id*, or None if absent/expired.

        Updates the last-access timestamp on successful retrieval.
        """
        entry = self._store.get(entry_id)
        if entry is None:
            return None
        if entry.is_expired:
            self._remove_entry(entry_id)
            return None
        entry.last_accessed = time.time()
        return entry.data

    def list_by_tier(self, tier: StorageTier) -> list[str]:
        """Return sorted list of entry IDs in the given *tier*."""
        return sorted(eid for eid, e in self._store.items() if e.tier == tier)

    def purge_expired(self) -> list[str]:
        """Remove all expired entries. Returns the list of removed IDs."""
        now = time.time()
        expired: list[str] = []
        for eid, entry in list(self._store.items()):
            age_days = (now - entry.created_at) / 86400.0
            if entry.ttl_days > 0 and age_days > entry.ttl_days:
                expired.append(eid)
                self._tier_counts[entry.tier.value] = max(0, self._tier_counts.get(entry.tier.value, 0) - 1)
                del self._store[eid]
                self._importance.pop(eid, None)
        return expired

    def get_stats(self) -> dict:
        """Return archive statistics."""
        return {
            "total": len(self._store),
            "by_tier": dict(self._tier_counts),
            "expired_count": sum(1 for e in self._store.values() if e.is_expired),
        }

    # ------------------------------------------------------------------
    # Extended API
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: str) -> ArchiveEntry | None:
        """Return the full :class:`ArchiveEntry`, or None."""
        return self._store.get(entry_id)

    def list_archived(self, tier: StorageTier | None = None) -> list[dict[str, Any]]:
        """Return all archived entries as dicts, optionally filtered by *tier*."""
        entries = list(self._store.values())
        if tier:
            entries = [e for e in entries if e.tier == tier]
        return [
            {
                "id": e.entry_id,
                "tier": e.tier.value,
                "created_at": e.created_at,
                "last_accessed": e.last_accessed,
                "ttl_days": e.ttl_days,
                "size_bytes": e.size_bytes,
                "metadata": e.metadata,
                "expired": e.is_expired,
                "age_days": round(e.age_days, 2),
            }
            for e in entries
        ]

    def delete(self, entry_id: str) -> bool:
        """Delete an entry. Returns True if it existed."""
        entry = self._store.pop(entry_id, None)
        if entry:
            self._tier_counts[entry.tier.value] = max(0, self._tier_counts.get(entry.tier.value, 0) - 1)
            self._importance.pop(entry_id, None)
            return True
        return False

    def set_importance(self, entry_id: str, score: float) -> None:
        """Set the importance score for an entry (0.0-1.0)."""
        self._importance[entry_id] = max(0.0, min(1.0, score))

    def get_importance(self, entry_id: str) -> float:
        """Get the importance score for an entry, defaulting to 0.5."""
        return self._importance.get(entry_id, 0.5)

    def promote_tier(self, entry_id: str) -> bool:
        """Promote an entry to the next hotter tier (COLD->WARM->HOT)."""
        entry = self._store.get(entry_id)
        if entry is None:
            return False
        tier_order = [StorageTier.COLD, StorageTier.WARM, StorageTier.HOT]
        try:
            idx = tier_order.index(entry.tier)
            if idx < len(tier_order) - 1:
                old_tier = entry.tier
                entry.tier = tier_order[idx + 1]
                self._tier_counts[old_tier.value] = max(0, self._tier_counts.get(old_tier.value, 0) - 1)
                self._tier_counts[entry.tier.value] = self._tier_counts.get(entry.tier.value, 0) + 1
                return True
        except ValueError:
            pass
        return False

    def demote_tier(self, entry_id: str) -> bool:
        """Demote an entry to the next colder tier (HOT->WARM->COLD)."""
        entry = self._store.get(entry_id)
        if entry is None:
            return False
        tier_order = [StorageTier.HOT, StorageTier.WARM, StorageTier.COLD]
        try:
            idx = tier_order.index(entry.tier)
            if idx < len(tier_order) - 1:
                old_tier = entry.tier
                entry.tier = tier_order[idx + 1]
                self._tier_counts[old_tier.value] = max(0, self._tier_counts.get(old_tier.value, 0) - 1)
                self._tier_counts[entry.tier.value] = self._tier_counts.get(entry.tier.value, 0) + 1
                return True
        except ValueError:
            pass
        return False

    def run_lifecycle_pass(self) -> dict[str, int]:
        """Run a full lifecycle pass: purge expired, demote idle, enforce caps.

        Returns counts by operation type.
        """
        stats: dict[str, int] = {"purged": 0, "demoted": 0, "promoted": 0}

        # Purge expired first
        stats["purged"] = len(self.purge_expired())

        now = time.time()

        # Demote idle hot entries
        hot_entries = [(e.entry_id, e.last_accessed) for e in self._store.values() if e.tier == StorageTier.HOT]
        hot_entries.sort(key=lambda x: x[1])  # oldest access first
        hot_idle_secs = self.policy.hot_idle_days * 86400.0
        overflow_hot = max(0, self._tier_counts.get("hot", 0) - self.policy.max_hot_entries)
        demoted_hot = 0
        for eid, last_acc in hot_entries:
            if demoted_hot >= overflow_hot and (now - last_acc) < hot_idle_secs:
                break
            if self.demote_tier(eid):
                demoted_hot += 1
        stats["demoted"] += demoted_hot

        # Demote idle warm entries
        warm_entries = [(e.entry_id, e.last_accessed) for e in self._store.values() if e.tier == StorageTier.WARM]
        warm_entries.sort(key=lambda x: x[1])
        warm_idle_secs = self.policy.warm_idle_days * 86400.0
        overflow_warm = max(0, self._tier_counts.get("warm", 0) - self.policy.max_warm_entries)
        demoted_warm = 0
        for eid, last_acc in warm_entries:
            if demoted_warm >= overflow_warm and (now - last_acc) < warm_idle_secs:
                break
            # Check importance threshold
            imp = self._importance.get(eid, 0.5)
            if imp < self.policy.min_importance_keep and (now - last_acc) > warm_idle_secs:
                if self.demote_tier(eid):
                    demoted_warm += 1
        stats["demoted"] += demoted_warm

        return stats

    def _promote_if_needed(self) -> None:
        """Demote overflow hot entries to warm tier."""
        hot = self._tier_counts.get("hot", 0)
        if hot > self.policy.max_hot_entries:
            overflow = sorted(
                [e for e in self._store.values() if e.tier == StorageTier.HOT],
                key=lambda x: x.last_accessed,
            )
            to_demote = hot - self.policy.max_hot_entries
            for entry in overflow[:to_demote]:
                entry.tier = StorageTier.WARM
                self._tier_counts["hot"] = max(0, self._tier_counts.get("hot", 0) - 1)
                self._tier_counts["warm"] = self._tier_counts.get("warm", 0) + 1

    def _remove_entry(self, entry_id: str) -> None:
        """Internal: remove an entry and update counts."""
        entry = self._store.pop(entry_id, None)
        if entry:
            self._tier_counts[entry.tier.value] = max(0, self._tier_counts.get(entry.tier.value, 0) - 1)
            self._importance.pop(entry_id, None)
