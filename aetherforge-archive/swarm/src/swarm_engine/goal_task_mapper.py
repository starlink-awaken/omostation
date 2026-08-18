from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Goal:
    goal_id: str
    description: str
    priority: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class TaskMapping:
    goal_id: str
    task_id: str
    contribution: float = 1.0


class GoalTaskMapper:
    def __init__(self) -> None:
        self._goals: dict[str, Goal] = {}
        self._mappings: list[TaskMapping] = []

    def define_goal(self, description: str, priority: int = 0, tags: list[str] | None = None) -> Goal:
        gid = uuid.uuid4().hex[:12]
        goal = Goal(goal_id=gid, description=description, priority=priority, tags=tags or [])
        self._goals[gid] = goal
        return goal

    def map_task(self, goal_id: str, task_id: str, contribution: float = 1.0) -> None:
        self._require_goal(goal_id)
        for m in self._mappings:
            if m.goal_id == goal_id and m.task_id == task_id:
                m.contribution = contribution
                return
        self._mappings.append(TaskMapping(goal_id=goal_id, task_id=task_id, contribution=contribution))

    def unmap_task(self, goal_id: str, task_id: str) -> None:
        self._mappings = [m for m in self._mappings if not (m.goal_id == goal_id and m.task_id == task_id)]

    def get_tasks_for_goal(self, goal_id: str) -> list[TaskMapping]:
        return [m for m in self._mappings if m.goal_id == goal_id]

    def get_goals_for_task(self, task_id: str) -> list[TaskMapping]:
        return [m for m in self._mappings if m.task_id == task_id]

    def get_unlinked_goals(self) -> list[Goal]:
        linked_ids = {m.goal_id for m in self._mappings}
        return [g for g in self._goals.values() if g.goal_id not in linked_ids]

    def get_unlinked_tasks(self, task_ids: list[str]) -> list[str]:
        linked_tasks = {m.task_id for m in self._mappings}
        return [tid for tid in task_ids if tid not in linked_tasks]

    def get_goal_coverage(self) -> dict:
        total = len(self._goals)
        if total == 0:
            return {"total_goals": 0, "covered_goals": 0, "coverage_pct": 0.0}
        linked_ids = {m.goal_id for m in self._mappings}
        covered = sum(1 for g in self._goals if g in linked_ids)
        return {
            "total_goals": total,
            "covered_goals": covered,
            "coverage_pct": covered / total * 100,
        }

    def _require_goal(self, goal_id: str) -> Goal:
        goal = self._goals.get(goal_id)
        if goal is None:
            raise KeyError(f"Goal {goal_id} not found")
        return goal
