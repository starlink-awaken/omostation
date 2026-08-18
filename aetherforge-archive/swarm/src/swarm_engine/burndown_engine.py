from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class WorkItem:
    item_id: str
    points: float
    completed: bool = False
    completed_at: float | None = None


@dataclass
class SprintData:
    sprint_id: str
    total_points: float
    items: list[WorkItem] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


class BurndownEngine:
    def __init__(self) -> None:
        self._sprints: dict[str, SprintData] = {}

    def create_sprint(self, sprint_id: str, total_points: float, start_time: float, end_time: float) -> SprintData:
        sprint = SprintData(
            sprint_id=sprint_id,
            total_points=total_points,
            start_time=start_time,
            end_time=end_time,
        )
        self._sprints[sprint_id] = sprint
        return sprint

    def add_item(self, sprint_id: str, item: WorkItem) -> None:
        sprint = self._require(sprint_id)
        sprint.items.append(item)

    def complete_item(self, sprint_id: str, item_id: str) -> None:
        sprint = self._require(sprint_id)
        for item in sprint.items:
            if item.item_id == item_id:
                item.completed = True
                item.completed_at = time.time()
                return
        raise KeyError(f"WorkItem {item_id} not found in sprint {sprint_id}")

    def get_remaining_points(self, sprint_id: str) -> float:
        sprint = self._require(sprint_id)
        completed = sum(i.points for i in sprint.items if i.completed)
        return sprint.total_points - completed

    def get_velocity(self, sprint_id: str) -> float:
        sprint = self._require(sprint_id)
        completed_items = [i for i in sprint.items if i.completed and i.completed_at]
        if not completed_items:
            return 0.0
        completed_pts = sum(i.points for i in completed_items)
        min(ca for i in completed_items if (ca := i.completed_at) is not None)
        latest = max(ca for i in completed_items if (ca := i.completed_at) is not None)
        elapsed = latest - sprint.start_time
        if elapsed <= 0:
            return completed_pts
        return completed_pts / elapsed

    def get_ideal_burndown(self, sprint_id: str, points: int = 10) -> list[tuple[float, float]]:
        sprint = self._require(sprint_id)
        duration = sprint.end_time - sprint.start_time
        if duration <= 0:
            return [(sprint.start_time, sprint.total_points)]
        step = duration / points
        result: list[tuple[float, float]] = []
        for i in range(points + 1):
            t = sprint.start_time + step * i
            remaining = sprint.total_points * (1 - i / points)
            result.append((t, remaining))
        return result

    def get_actual_burndown(self, sprint_id: str) -> list[tuple[float, float]]:
        sprint = self._require(sprint_id)
        events: list[tuple[float, float]] = [(sprint.start_time, sprint.total_points)]
        completed_sorted = sorted(
            [i for i in sprint.items if i.completed and i.completed_at is not None],
            key=lambda i: i.completed_at or 0.0,
        )
        running = sprint.total_points
        for item in completed_sorted:
            running -= item.points
            ca = item.completed_at
            if ca is not None:
                events.append((ca, running))
        return events

    def is_on_track(self, sprint_id: str) -> bool:
        sprint = self._require(sprint_id)
        now = time.time()
        duration = sprint.end_time - sprint.start_time
        if duration <= 0:
            return True
        elapsed_frac = min((now - sprint.start_time) / duration, 1.0)
        ideal_remaining = sprint.total_points * (1 - elapsed_frac)
        actual_remaining = self.get_remaining_points(sprint_id)
        return actual_remaining <= ideal_remaining * 1.1

    def predict_completion(self, sprint_id: str) -> float | None:
        self._require(sprint_id)
        velocity = self.get_velocity(sprint_id)
        if velocity <= 0:
            return None
        remaining = self.get_remaining_points(sprint_id)
        now = time.time()
        return now + remaining / velocity

    def _require(self, sprint_id: str) -> SprintData:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint {sprint_id} not found")
        return sprint
