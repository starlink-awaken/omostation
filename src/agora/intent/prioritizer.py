"""Prioritization engine for the intent model.

Scores each candidate item (task / goal / mandate) on a 0–100 scale
using configurable weights. Higher = more important to do now.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Priority(IntEnum):
    """Discrete priority bands derived from raw score."""

    CRITICAL = 5  # >= 80
    HIGH = 4  # >= 60
    MEDIUM = 3  # >= 40
    LOW = 2  # >= 20
    BACKLOG = 1  # < 20

    @classmethod
    def from_score(cls, score: float) -> Priority:
        if score >= 80:
            return cls.CRITICAL
        if score >= 60:
            return cls.HIGH
        if score >= 40:
            return cls.MEDIUM
        if score >= 20:
            return cls.LOW
        return cls.BACKLOG


@dataclass
class ScoreWeights:
    """Configurable weights for the scoring function.

    All weights are non-negative; they are normalized to sum to 1
    before scoring. Default weights favour deadline proximity and
    goal alignment.
    """

    deadline: float = 0.30
    goal_alignment: float = 0.25
    dependency: float = 0.20
    recency: float = 0.15
    effort: float = 0.10

    def normalized(self) -> dict[str, float]:
        total = (
            self.deadline
            + self.goal_alignment
            + self.dependency
            + self.recency
            + self.effort
        )
        if total <= 0:
            return dict(
                deadline=0.2,
                goal_alignment=0.2,
                dependency=0.2,
                recency=0.2,
                effort=0.2,
            )
        k = 1.0 / total
        return dict(
            deadline=self.deadline * k,
            goal_alignment=self.goal_alignment * k,
            dependency=self.dependency * k,
            recency=self.recency * k,
            effort=self.effort * k,
        )


@dataclass
class ScoredItem:
    """A single item with its importance score and breakdown."""

    id: str
    title: str
    source: str  # "task" | "goal" | "mandate"
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> Priority:
        return Priority.from_score(self.score)


class Prioritizer:
    """Score and rank candidate items by importance-right-now."""

    def __init__(self, weights: ScoreWeights | None = None) -> None:
        self.weights = (weights or ScoreWeights()).normalized()

    def score_task(self, task: dict[str, Any]) -> ScoredItem:
        """Score a single task dict (TaskManager-shaped)."""
        now = int(time.time() * 1000)
        breakdown: dict[str, float] = {}

        # Deadline: closer deadline → higher score. No deadline → 30.
        deadline = task.get("deadline_ms") or task.get("deadline")
        if deadline:
            remaining = max(0, deadline - now)
            # 0 remaining → 100, > 7 days → 0, linear in between
            days_left = remaining / 86_400_000
            breakdown["deadline"] = max(0, 100 * (1 - days_left / 7))
        else:
            breakdown["deadline"] = 30.0

        # Goal alignment: explicit goal_ref → 80, none → 20.
        breakdown["goal_alignment"] = 80.0 if task.get("goal_ref") else 20.0

        # Dependency: blocked_by others → lower, blocking others → higher.
        blocking = len(task.get("blocks", []))
        blocked_by = len(task.get("blocked_by", []))
        breakdown["dependency"] = min(100, 50 + blocking * 15 - blocked_by * 20)

        # Recency: more recently updated → higher.
        updated = task.get("updated_ms") or task.get("updated") or now
        age_hours = max(0, (now - updated) / 3_600_000)
        breakdown["recency"] = max(0, 100 * (1 - age_hours / 72))  # decay over 3 days

        # Effort: smaller effort → higher (quick wins preferred).
        effort = task.get("estimated_effort") or 3
        breakdown["effort"] = max(0, 100 - effort * 15)

        score = sum(self.weights[k] * breakdown[k] for k in breakdown)
        return ScoredItem(
            id=task.get("id", "?"),
            title=task.get("title", task.get("name", "(untitled)")),
            source="task",
            score=round(score, 2),
            breakdown={k: round(v, 1) for k, v in breakdown.items()},
            rationale=_rationale(breakdown, self.weights),
            metadata=task,
        )

    def rank(self, items: list[ScoredItem]) -> list[ScoredItem]:
        """Return items sorted by score descending (most important first)."""
        return sorted(items, key=lambda i: i.score, reverse=True)


def _rationale(bd: dict[str, float], weights: dict[str, float]) -> str:
    """Human-readable explanation of why an item scored as it did."""
    top = sorted(
        bd.items(), key=lambda kv: weights.get(kv[0], 0) * kv[1], reverse=True
    )[:2]
    parts = []
    for k, v in top:
        if k == "deadline":
            parts.append(f"deadline urgency {v:.0f}")
        elif k == "goal_alignment":
            parts.append("goal-aligned" if v > 50 else "no goal link")
        elif k == "dependency":
            parts.append(
                "unblocks others" if v > 50 else "blocked" if v < 40 else "neutral"
            )
        elif k == "recency":
            parts.append("recently active" if v > 60 else "stale")
        elif k == "effort":
            parts.append("quick win" if v > 60 else "heavy lift")
    return ", ".join(parts) if parts else "baseline priority"
