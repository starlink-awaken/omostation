"""
Two-Tier Semantic & Prefix Cache Registry for omlxc.

Provides:
- Tier 1: Zero-latency exact Prefix-Hash / Session Cache
- Tier 2: Normalized semantic prompt fingerprint cache
Eliminating redundant inference for frequent template & governance queries.
"""

from __future__ import annotations

import enum
import hashlib
import time
from dataclasses import dataclass
from typing import Final


class CacheTier(enum.StrEnum):
    """Cache lookup tier."""

    L1_EXACT = "l1_exact"
    L2_SEMANTIC = "l2_semantic"


@dataclass(slots=True)
class SemanticCacheEntry:
    """Stored response artifact with TTL and hit telemetry."""

    cache_key: str
    tier: CacheTier
    model_id: str
    prompt_fingerprint: str
    response_content: str
    created_at: float
    ttl_seconds: float
    hit_count: int = 0

    def is_expired(self, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        return (current_time - self.created_at) > self.ttl_seconds


DEFAULT_CACHE_TTL_SECONDS: Final[float] = 1800.0  # 30 minutes


def normalize_semantic_fingerprint(prompt: str) -> str:
    """Normalize whitespace and punctuation to compute invariant semantic hash."""
    clean = " ".join(prompt.strip().lower().split())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


class SemanticCacheRegistry:
    """In-memory two-tier cache with LRU eviction and hit telemetry."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, SemanticCacheEntry] = {}
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0

    def lookup(
        self,
        prefix_hash: str | None = None,
        raw_prompt: str | None = None,
        now: float | None = None,
    ) -> tuple[str | None, CacheTier | None]:
        """
        Query L1 (exact prefix) or L2 (normalized semantic fingerprint).
        
        Returns (response_content, tier_hit).
        """
        current_time = time.monotonic() if now is None else now

        # 1. Tier 1 exact prefix hash
        if prefix_hash and prefix_hash in self._entries:
            entry = self._entries[prefix_hash]
            if not entry.is_expired(current_time):
                entry.hit_count += 1
                self._l1_hits += 1
                return (entry.response_content, CacheTier.L1_EXACT)
            del self._entries[prefix_hash]

        # 2. Tier 2 semantic fingerprint
        if raw_prompt:
            fp = normalize_semantic_fingerprint(raw_prompt)
            if fp in self._entries:
                entry = self._entries[fp]
                if not entry.is_expired(current_time):
                    entry.hit_count += 1
                    self._l2_hits += 1
                    return (entry.response_content, CacheTier.L2_SEMANTIC)
                del self._entries[fp]

        self._misses += 1
        return (None, None)

    def store(
        self,
        key: str,
        response_content: str,
        model_id: str,
        tier: CacheTier = CacheTier.L1_EXACT,
        ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        now: float | None = None,
    ) -> None:
        """Store generated response with TTL and capacity bounding."""
        current_time = time.monotonic() if now is None else now

        # Evict oldest entry if capacity reached
        if len(self._entries) >= self._max_entries:
            oldest_key = min(self._entries, key=lambda k: self._entries[k].created_at)
            del self._entries[oldest_key]

        self._entries[key] = SemanticCacheEntry(
            cache_key=key,
            tier=tier,
            model_id=model_id,
            prompt_fingerprint=key,
            response_content=response_content,
            created_at=current_time,
            ttl_seconds=ttl_seconds,
            hit_count=0,
        )

    def get_stats(self) -> dict[str, float | int]:
        """Fetch real-time cache efficiency metrics."""
        total_queries = self._l1_hits + self._l2_hits + self._misses
        hit_rate = (
            (self._l1_hits + self._l2_hits) / total_queries if total_queries > 0 else 0.0
        )
        return {
            "total_entries": len(self._entries),
            "l1_exact_hits": self._l1_hits,
            "l2_semantic_hits": self._l2_hits,
            "misses": self._misses,
            "total_queries": total_queries,
            "hit_rate": round(hit_rate, 4),
        }
