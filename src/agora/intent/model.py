"""IntentModel — answer "what's the most important thing right now".

BET-Y2Q1-T3-02 execution: composes active tasks (TaskManager) with
goals/mandates (omo state) into a ranked list the agent can act on.

Usage::

    model = IntentModel(task_manager)
    result = model.whats_most_important(top_n=3)
    for item in result.items:
        print(f"{item.priority.name}: {item.title} ({item.score})")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from agora.intent.prioritizer import Prioritizer, ScoredItem, ScoreWeights


class TaskSource(Protocol):
    """Minimal interface the model needs from a task store."""

    def get_all_tasks(self) -> list[dict[str, Any]]: ...
    def get_active_tasks(self) -> list[dict[str, Any]]: ...


@dataclass
class IntentResult:
    """Output of a "what's most important" query."""

    items: list[ScoredItem]
    generated_at: float = field(default_factory=lambda: __import__("time").time())
    context_summary: str = ""

    @property
    def top(self) -> ScoredItem | None:
        return self.items[0] if self.items else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "context_summary": self.context_summary,
            "items": [
                {
                    "id": it.id,
                    "title": it.title,
                    "source": it.source,
                    "score": it.score,
                    "priority": it.priority.name,
                    "rationale": it.rationale,
                }
                for it in self.items
            ],
        }


class IntentModel:
    """Compose tasks + goals into a ranked importance list."""

    def __init__(
        self,
        task_source: TaskSource | Any = None,
        weights: ScoreWeights | None = None,
    ) -> None:
        self.task_source = task_source
        self.prioritizer = Prioritizer(weights)

    # ── Public API ──────────────────────────────────────────────────

    def whats_most_important(self, top_n: int = 5) -> IntentResult:
        """Answer: what should I work on right now?"""
        items: list[ScoredItem] = []

        # 1) Active tasks from the task source
        if self.task_source is not None:
            active = _extract_tasks(self.task_source)
            items.extend(self.prioritizer.score_task(t) for t in active)

        # 2) Goals / mandates (placeholder — wired to omo state in BET-Y2Q2)
        # items.extend(self._score_goals())

        ranked = self.prioritizer.rank(items)
        return IntentResult(
            items=ranked[:top_n],
            context_summary=self._summarize(ranked),
        )

    def rank_all(self) -> IntentResult:
        """Return every known item, ranked."""
        return self.whats_most_important(top_n=10_000)

    # ── Internal ────────────────────────────────────────────────────

    def _summarize(self, ranked: list[ScoredItem]) -> str:
        if not ranked:
            return "No active tasks or goals."
        top = ranked[0]
        n = len(ranked)
        return (
            f"{n} item(s) tracked; top priority: "
            f"[{top.priority.name}] {top.title} (score {top.score})"
        )


def _extract_tasks(source: Any) -> list[dict[str, Any]]:
    """Best-effort extraction of task dicts from various source shapes."""
    if hasattr(source, "get_active_tasks"):
        raw = source.get_active_tasks()
    elif hasattr(source, "get_all_tasks"):
        raw = source.get_all_tasks()
    elif isinstance(source, list):
        raw = source
    elif hasattr(source, "_tasks"):
        raw = list(source._tasks.values())
    else:
        return []
    return [_task_to_dict(t) for t in raw]


def _task_to_dict(task: Any) -> dict[str, Any]:
    """Normalize a Task object or dict into a plain dict."""
    if isinstance(task, dict):
        return task
    # Object-shaped Task (dataclass / attrs / plain class)
    out: dict[str, Any] = {}
    for attr in (
        "id",
        "title",
        "name",
        "status",
        "deadline_ms",
        "deadline",
        "updated_ms",
        "updated",
        "goal_ref",
        "blocks",
        "blocked_by",
        "estimated_effort",
    ):
        if hasattr(task, attr):
            out[attr] = getattr(task, attr)
    return out
