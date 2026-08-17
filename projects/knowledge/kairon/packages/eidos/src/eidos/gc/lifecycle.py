"""Lifecycle Manager — track creation, access, modification for knowledge decay."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class LifecycleRecord:
    """Tracks creation, access, and modification timestamps for a single entry.

    Attributes:
        entry_id: Unique identifier.
        created_at: Unix timestamp of creation.
        last_accessed: Unix timestamp of last access.
        last_modified: Unix timestamp of last modification.
        access_count: Total number of accesses.
        importance: Importance score 0.0-1.0.
    """

    entry_id: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5


@dataclass
class DecayConfig:
    """Configuration for knowledge decay scoring.

    Attributes:
        base_ttl_days: Default TTL for entries without explicit TTL.
        min_importance_ttl: Minimum TTL for high-importance entries (days).
        access_decay_rate: Rate at which idle time reduces freshness.
        importance_weight: Weight of importance in combined decay (0-1).
        access_weight: Weight of access freshness in combined decay (0-1).
        idle_threshold_days: If idle longer than this, mark as dormant.
        collect_decay_threshold: Decay score above this → eligible for collection.
    """

    base_ttl_days: float = 90.0
    min_importance_ttl: float = 7.0
    access_decay_rate: float = 0.05
    importance_weight: float = 0.4
    access_weight: float = 0.6
    idle_threshold_days: float = 30.0
    collect_decay_threshold: float = 0.7


class LifecycleManager:
    """Track the lifecycle of knowledge entries and compute decay/collection decisions.

    Maintains backward compatibility with the existing stub API (``register``,
    ``access``, ``modify``, ``get_decay_score``, ``should_collect``, ``get_stale``,
    ``remove``, ``get_stats``) while adding richer TTL tracking, stage management,
    and bulk operations.

    Typical usage::

        lm = LifecycleManager()
        lm.register("doc-1", importance=0.8)
        lm.access("doc-1")
        score = lm.get_decay_score("doc-1")
        if lm.should_collect("doc-1"):
            engine.mark("doc-1", "lifecycle-expired")
    """

    def __init__(self, config: DecayConfig | None = None) -> None:
        self.config = config or DecayConfig()
        self._records: dict[str, LifecycleRecord] = {}
        # Per-entry TTL overrides (seconds)
        self._ttl_overrides: dict[str, float] = {}
        # Stage tracking
        self._stages: dict[str, str] = {}  # entry_id → stage label

    # ------------------------------------------------------------------
    # Backward-compatible registration API
    # ------------------------------------------------------------------

    def register(self, entry_id: str, importance: float = 0.5) -> LifecycleRecord:
        """Register a new entry, returning the created :class:`LifecycleRecord`.

        Args:
            entry_id: Unique identifier.
            importance: Initial importance score, clamped to [0, 1].
        """
        record = LifecycleRecord(
            entry_id=entry_id,
            importance=max(0.0, min(1.0, importance)),
        )
        self._records[entry_id] = record
        self._stages[entry_id] = "active"
        return record

    def access(self, entry_id: str) -> None:
        """Record an access event (updating timestamp and count)."""
        rec = self._records.get(entry_id)
        if rec:
            rec.last_accessed = time.time()
            rec.access_count += 1
            # Bump back to active if dormant
            if self._stages.get(entry_id) in ("decaying", "dormant"):
                self._stages[entry_id] = "active"

    def modify(self, entry_id: str) -> None:
        """Record a modification event."""
        rec = self._records.get(entry_id)
        if rec:
            now = time.time()
            rec.last_modified = now
            rec.last_accessed = now  # modification implies access

    # ------------------------------------------------------------------
    # Backward-compatible decay/collection API
    # ------------------------------------------------------------------

    def get_decay_score(self, entry_id: str) -> float:
        """Calculate a decay score in [0, 1], where 0 = fresh, 1 = should collect.

        Formula::

            age_factor = min(1, age_days / base_ttl_days)
            access_factor = min(1, access_gap_days / 30)
            importance_factor = 1 - importance
            score = access_weight * access_factor
                  + importance_weight * importance_factor
                  + 0.3 * age_factor

        The effective TTL for an entry considers its importance score: more
        important entries get a longer effective TTL (`base_ttl_days +
        importance * extra_ttl`), so they decay more slowly.
        """
        rec = self._records.get(entry_id)
        if not rec:
            return 1.0

        # Check explicit TTL override
        explicit_ttl = self._ttl_overrides.get(entry_id)
        if explicit_ttl is not None:
            age_seconds = time.time() - rec.created_at
            if age_seconds > explicit_ttl:
                return 1.0  # definitely expired

        now = time.time()
        age_days = (now - rec.created_at) / 86400.0
        access_gap_days = (now - rec.last_accessed) / 86400.0

        # Effective TTL grows with importance
        effective_ttl = self.config.base_ttl_days + rec.importance * 30.0
        age_factor = min(1.0, age_days / effective_ttl)

        # Access staleness (30-day reference window)
        access_factor = min(1.0, access_gap_days / 30.0)

        # Importance inversion (low importance → high decay contribution)
        importance_factor = 1.0 - rec.importance

        # Decay bonus: frequently accessed entries decay slower
        freq_bonus = 0.0
        if rec.access_count > 0:
            freq_bonus = math.exp(-self.config.access_decay_rate * rec.access_count)
            access_factor *= freq_bonus

        score = (
            self.config.access_weight * access_factor
            + self.config.importance_weight * importance_factor
            + 0.3 * age_factor
        )
        return min(1.0, score)

    def should_collect(self, entry_id: str, threshold: float = 0.7) -> bool:
        """Return True if the decay score is at or above *threshold*.

        Also returns True if an explicit TTL has elapsed.
        """
        score = self.get_decay_score(entry_id)
        if score >= threshold:
            return True
        # Check explicit TTL
        explicit_ttl = self._ttl_overrides.get(entry_id)
        rec = self._records.get(entry_id)
        if rec and explicit_ttl is not None:
            if time.time() - rec.created_at > explicit_ttl:
                return True
        return False

    def get_stale(self, threshold: float = 0.7) -> list[str]:
        """Return sorted IDs of entries whose decay score is >= *threshold*."""
        return sorted(eid for eid in self._records if self.should_collect(eid, threshold))

    def remove(self, entry_id: str) -> bool:
        """Remove a tracked entry. Returns True if it was present."""
        self._ttl_overrides.pop(entry_id, None)
        self._stages.pop(entry_id, None)
        return self._records.pop(entry_id, None) is not None

    def get_stats(self) -> dict:
        """Return lifecycle statistics (total, avg decay, stale count)."""
        if not self._records:
            return {"total": 0, "avg_decay": 0.0, "stale_count": 0, "by_stage": {}}
        scores = [self.get_decay_score(eid) for eid in self._records]
        stale = sum(1 for s in scores if s >= self.config.collect_decay_threshold)
        by_stage: dict[str, int] = {}
        for sid in set(self._stages.values()):
            by_stage[sid] = sum(1 for s in self._stages.values() if s == sid)
        return {
            "total": len(self._records),
            "avg_decay": round(sum(scores) / len(scores), 4),
            "stale_count": stale,
            "by_stage": by_stage,
        }

    # ------------------------------------------------------------------
    # Extended API
    # ------------------------------------------------------------------

    def set_ttl(self, entry_id: str, ttl_seconds: float) -> None:
        """Set an explicit TTL (in seconds) for *entry_id*."""
        self._ttl_overrides[entry_id] = ttl_seconds

    def get_ttl_remaining(self, entry_id: str) -> float | None:
        """Return remaining TTL in seconds, or None if no TTL is set."""
        explicit = self._ttl_overrides.get(entry_id)
        if explicit is not None:
            rec = self._records.get(entry_id)
            if rec:
                elapsed = time.time() - rec.created_at
                return max(0.0, explicit - elapsed)
        return None

    def get_record(self, entry_id: str) -> LifecycleRecord | None:
        """Return the raw :class:`LifecycleRecord`, or None."""
        return self._records.get(entry_id)

    def get_stage(self, entry_id: str) -> str:
        """Return the current lifecycle stage label for *entry_id*."""
        return self._stages.get(entry_id, "unknown")

    def update_stages(self) -> dict[str, int]:
        """Re-evaluate lifecycle stages for all entries based on current
        decay scores. Returns a dict of transition counts.

        Stage mapping:
            - decay < 0.3 → active
            - decay 0.3-0.6 → decaying
            - decay 0.6-0.85 → dormant
            - decay >= 0.85 → expired
        """
        transitions: dict[str, int] = {}
        for entry_id in self._records:
            old_stage = self._stages.get(entry_id, "active")
            score = self.get_decay_score(entry_id)
            if score < 0.3:
                new_stage = "active"
            elif score < 0.6:
                new_stage = "decaying"
            elif score < 0.85:
                new_stage = "dormant"
            else:
                new_stage = "expired"

            if new_stage != old_stage:
                self._stages[entry_id] = new_stage
                key = f"{old_stage}->{new_stage}"
                transitions[key] = transitions.get(key, 0) + 1
        return transitions

    def list_all(self) -> list[dict]:
        """Return all tracked entries as dicts suitable for JSON output."""
        result: list[dict] = []
        for entry_id, rec in self._records.items():
            result.append(
                {
                    "entry_id": entry_id,
                    "created_at": datetime.fromtimestamp(rec.created_at, tz=UTC).isoformat(),
                    "last_accessed": datetime.fromtimestamp(rec.last_accessed, tz=UTC).isoformat(),
                    "last_modified": datetime.fromtimestamp(rec.last_modified, tz=UTC).isoformat(),
                    "access_count": rec.access_count,
                    "importance": rec.importance,
                    "decay_score": round(self.get_decay_score(entry_id), 4),
                    "stage": self._stages.get(entry_id, "unknown"),
                    "ttl_remaining": self.get_ttl_remaining(entry_id),
                }
            )
        return result

    def find_collectable(self, threshold: float | None = None) -> list[str]:
        """Return entry IDs that should be collected.

        A convenience wrapper that re-evaluates stages before checking.
        """
        self.update_stages()
        thresh = threshold if threshold is not None else self.config.collect_decay_threshold
        return sorted(eid for eid in self._records if self.should_collect(eid, thresh))
