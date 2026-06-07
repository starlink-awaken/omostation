"""Task dependency DAG — topological sort, cycle detection, critical path."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class TaskNode:
    task_id: str
    name: str = ""
    estimated_duration: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class TaskDAG:
    def __init__(self) -> None:
        self._nodes: dict[str, TaskNode] = {}
        self._reverse: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node: TaskNode) -> None:
        self._nodes[node.task_id] = node
        for dep in node.depends_on:
            self._reverse[dep].add(node.task_id)

    def get_node(self, task_id: str) -> TaskNode | None:
        return self._nodes.get(task_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def dependents(self, task_id: str) -> set[str]:
        return self._reverse.get(task_id, set())

    def topological_sort(self) -> list[str] | None:
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                in_degree[node.task_id] += 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []

        while queue:
            nid = queue.popleft()
            result.append(nid)
            for dep_id in self._reverse.get(nid, set()):
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    queue.append(dep_id)

        return result if len(result) == len(self._nodes) else None

    def has_cycle(self) -> bool:
        return self.topological_sort() is None

    def critical_path(self) -> tuple[float, list[str]]:
        order = self.topological_sort()
        if order is None:
            return (0.0, [])

        earliest: dict[str, float] = {nid: 0.0 for nid in self._nodes}
        for nid in order:
            node = self._nodes[nid]
            finish_time = earliest[nid] + node.estimated_duration
            for dep_id in self._reverse.get(nid, set()):
                earliest[dep_id] = max(earliest[dep_id], finish_time)

        max_node = max(earliest, key=lambda k: earliest[k])
        return (earliest[max_node] + self._nodes[max_node].estimated_duration, order)
