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
# Context Compressor ≡ Module
# 内涵 ≝ {Context, Compressor}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ContextCompressor)}
# 功能 ⊢ {Context_Compressor, Init_Context, Validate_Compressor}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
"""Context compression pipeline for managing agent context within token budgets.

Implements a hot/warm/cold temperature model:
- **hot** entries are kept as-is (recent, frequently accessed)
- **warm** entries are summarised into a single merged entry
- **cold** entries are evicted from the context window

Token counting uses a simple word-split proxy (no external deps).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
_HOT_AGE_SECS: float = 300.0  # ≤ 5 min → hot
_WARM_AGE_SECS: float = 1800.0  # ≤ 30 min → warm
_HOT_ACCESS_FLOOR: int = 3  # ≥ 3 accesses can promote to hot
_SUMMARY_TAG = "compressed-summary"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class MemoryEntry:
    """Lightweight record carried through the compression pipeline."""

    content: str
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    token_count: int = 0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.token_count <= 0:
            self.token_count = _estimate_tokens(self.content)


def _estimate_tokens(text: str) -> int:
    """Cheap proxy: one token ≈ one whitespace-delimited word."""
    return len(text.split()) if text else 0


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------
class ContextCompressor:
    """Pure-Python context compressor with hot / warm / cold strategy.

    Usage::

        cc = ContextCompressor()
        trimmed = cc.compress(entries, token_budget=4096)
    """

    def __init__(
        self,
        hot_age: float = _HOT_AGE_SECS,
        warm_age: float = _WARM_AGE_SECS,
        hot_access_floor: int = _HOT_ACCESS_FLOOR,
    ) -> None:
        self._hot_age = hot_age
        self._warm_age = warm_age
        self._hot_access_floor = hot_access_floor

    # -- public API ---------------------------------------------------------

    def compress(
        self,
        entries: list[MemoryEntry],
        token_budget: int,
        *,
        now: float | None = None,
    ) -> list[MemoryEntry]:
        """Return a list of entries that fit within *token_budget*.

        Strategy (applied in order):
        1. Classify every entry by temperature.
        2. Evict cold entries outright.
        3. If still over budget, summarise warm entries into one.
        4. If *still* over budget, greedily keep entries newest-first
           until the budget is exhausted.
        """
        if not entries:
            return []

        now = now if now is not None else time.time()

        hot: list[MemoryEntry] = []
        warm: list[MemoryEntry] = []
        for entry in entries:
            temp = self.classify_temperature(entry, now)
            if temp == "hot":
                hot.append(entry)
            elif temp == "warm":
                warm.append(entry)
            # cold → dropped

        result: list[MemoryEntry] = list(hot)
        used = sum(e.token_count for e in result)

        # Fold warm entries into a single summary if any exist
        if warm:
            summary = self.summarize_batch(warm)
            if used + summary.token_count <= token_budget:
                result.append(summary)
                used += summary.token_count

        # Budget check — greedy trim newest-first when over
        if used > token_budget:
            result.sort(key=lambda e: e.timestamp, reverse=True)
            trimmed: list[MemoryEntry] = []
            budget_left = token_budget
            for entry in result:
                if entry.token_count <= budget_left:
                    trimmed.append(entry)
                    budget_left -= entry.token_count
            result = trimmed

        logger.debug(
            "compress: %d→%d entries, %d tokens used (budget %d)",
            len(entries),
            len(result),
            sum(e.token_count for e in result),
            token_budget,
        )
        return result

    def summarize_batch(self, entries: list[MemoryEntry]) -> MemoryEntry:
        """Merge *entries* into a single summary ``MemoryEntry``.

        The summary preserves the newest timestamp and the union of all tags.
        Content is concatenated with ``" | "`` separators and prefixed so
        downstream consumers can recognise a synthetic entry.
        """
        if not entries:
            return MemoryEntry(content="", tags=[_SUMMARY_TAG])

        if len(entries) == 1:
            return entries[0]

        merged_content = "[summary] " + " | ".join(e.content for e in entries)
        all_tags: list[str] = list(dict.fromkeys(tag for e in entries for tag in e.tags))
        if _SUMMARY_TAG not in all_tags:
            all_tags.append(_SUMMARY_TAG)

        newest_ts = max(e.timestamp for e in entries)
        total_access = sum(e.access_count for e in entries)

        return MemoryEntry(
            content=merged_content,
            timestamp=newest_ts,
            access_count=total_access,
            tags=all_tags,
        )

    def classify_temperature(
        self,
        entry: MemoryEntry,
        now: float,
    ) -> Literal["hot", "warm", "cold"]:
        """Classify an entry as hot / warm / cold.

        Rules:
        * age ≤ hot_age  **or**  access_count ≥ hot_access_floor  → **hot**
        * age ≤ warm_age  → **warm**
        * otherwise  → **cold**
        """
        age = now - entry.timestamp
        if age <= self._hot_age or entry.access_count >= self._hot_access_floor:
            return "hot"
        if age <= self._warm_age:
            return "warm"
        return "cold"

    def evict_cold(
        self,
        entries: list[MemoryEntry],
        threshold: float,
        *,
        now: float | None = None,
    ) -> tuple[list[MemoryEntry], list[MemoryEntry]]:
        """Partition *entries* into (kept, evicted).

        An entry is evicted when its age exceeds *threshold* seconds **and**
        it does not meet the hot-access floor.
        """
        now = now if now is not None else time.time()
        kept: list[MemoryEntry] = []
        evicted: list[MemoryEntry] = []
        for entry in entries:
            age = now - entry.timestamp
            if age > threshold and entry.access_count < self._hot_access_floor:
                evicted.append(entry)
            else:
                kept.append(entry)
        return kept, evicted
