from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
Extracted from: SharedBrain D_Memory/organs/forgetting_curve_engine.py → eidos/forgetting_curve_engine.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Forgetting Curve Engine ≡ Engine
# 内涵 ≝ {Forgetting, Curve, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ForgettingCurveEngine)}
# 功能 ⊢ {Forgetting_Curve, Curve_Engine, Engine_Init}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---

import logging
import math
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

__all__ = ["MemoryItem", "ForgettingCurveEngine"]


@dataclass
class MemoryItem:
    item_id: str
    content: str
    strength: float = 1.0
    last_reviewed: float = field(default_factory=time.time)
    review_count: int = 0
    importance: float = 0.5


class ForgettingCurveEngine:
    """Ebbinghaus forgetting-curve engine for spaced-repetition memory management."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def store(self, item_id: str, content: str, importance: float = 0.5) -> None:
        now = time.time()
        self._items[item_id] = MemoryItem(
            item_id=item_id,
            content=content,
            strength=1.0,
            last_reviewed=now,
            review_count=1,
            importance=importance,
        )

    def get_item(self, item_id: str) -> MemoryItem | None:
        return self._items.get(item_id)

    def review(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        item.review_count += 1
        item.strength = min(item.strength + 0.5 * item.importance, 10.0)
        item.last_reviewed = time.time()

    def get_retention(self, item_id: str, current_time: float | None = None) -> float:
        item = self._items.get(item_id)
        if item is None:
            return 0.0
        now = current_time if current_time is not None else time.time()
        elapsed = max(now - item.last_reviewed, 0.0)
        stability = max(item.strength * item.review_count, 0.01)
        return math.exp(-elapsed / stability)

    def get_due_for_review(self, threshold: float = 0.5, current_time: float | None = None) -> list[str]:
        return [iid for iid in self._items if self.get_retention(iid, current_time) < threshold]

    def decay_all(self, current_time: float | None = None) -> None:
        now = current_time if current_time is not None else time.time()
        for item in self._items.values():
            elapsed = max(now - item.last_reviewed, 0.0)
            stability = max(item.strength * item.review_count, 0.01)
            item.strength = max(item.strength * math.exp(-elapsed / stability), 0.01)

    def prune_forgotten(self, threshold: float = 0.1, current_time: float | None = None) -> list[str]:
        pruned: list[str] = []
        for iid in list(self._items):
            if self.get_retention(iid, current_time) < threshold:
                pruned.append(iid)
                del self._items[iid]
        return pruned

    def get_stats(self, current_time: float | None = None) -> dict:
        if not self._items:
            return {
                "total_items": 0,
                "avg_retention": 0.0,
                "items_due_for_review": 0,
            }
        retentions = [self.get_retention(iid, current_time) for iid in self._items]
        due = sum(1 for r in retentions if r < 0.5)
        return {
            "total_items": len(self._items),
            "avg_retention": sum(retentions) / len(retentions),
            "items_due_for_review": due,
        }
