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
# Task Dependency Dag ≡ Module
# 内涵 ≝ {Task, Dependency, Dag}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, TaskDependencyDag)}
# 功能 ⊢ {Task_Dependency, Dependency_Dag, Dag_Init}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# ---

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class TaskNode:
    """Represents a single task in the dependency graph."""

    task_id: str
    name: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 0
    status: str = "pending"
    metadata: dict = field(default_factory=dict)


class TaskDAG:
    """Directed acyclic graph for task dependency tracking and scheduling.

    Manages task nodes with dependency edges, provides topological ordering,
    cycle detection, critical path analysis, and ready-task resolution.
    """

    def __init__(self) -> None:
        self.status = "active"
        self._nodes: dict[str, TaskNode] = {}
        self._edges: dict[str, set[str]] = defaultdict(set)  # task_id -> set of dependency task_ids

    def add_task(self, node: TaskNode) -> None:
        """Add a task node to the DAG."""
        self._nodes[node.task_id] = node
        for dep in node.dependencies:
            self._edges[node.task_id].add(dep)

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """Add a dependency edge: task_id depends on depends_on."""
        if task_id not in self._nodes:
            raise KeyError(f"Task '{task_id}' not found in DAG")
        if depends_on not in self._nodes:
            raise KeyError(f"Dependency '{depends_on}' not found in DAG")
        self._edges[task_id].add(depends_on)
        self._nodes[task_id].dependencies.append(depends_on)

    def get_execution_order(self) -> list[str]:
        """Return topological sort of all tasks. Raises ValueError if cycles exist."""
        cycles = self.detect_cycles()
        if cycles:
            raise ValueError(f"Cannot compute execution order: cycles detected: {cycles}")

        in_degree: dict[str, int] = dict.fromkeys(self._nodes, 0)
        for tid, deps in self._edges.items():
            if tid in in_degree:
                in_degree[tid] = len([d for d in deps if d in self._nodes])

        queue: list[str] = []
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)
        queue.sort(key=lambda t: -self._nodes[t].priority)

        result: list[str] = []
        while queue:
            queue.sort(key=lambda t: -self._nodes[t].priority)
            current = queue.pop(0)
            result.append(current)
            for tid in list(self._nodes.keys()):
                if current in self._edges.get(tid, set()):
                    in_degree[tid] -= 1
                    if in_degree[tid] == 0:
                        queue.append(tid)

        return result

    def get_ready_tasks(self) -> list[str]:
        """Return task IDs whose dependencies are all satisfied (status='done') and task is pending."""
        ready = []
        for tid, node in self._nodes.items():
            if node.status != "pending":
                continue
            deps = self._edges.get(tid, set())
            all_done = all(self._nodes[d].status == "done" for d in deps if d in self._nodes)
            if all_done:
                ready.append(tid)
        return sorted(ready, key=lambda t: -self._nodes[t].priority)

    def mark_complete(self, task_id: str) -> None:
        """Mark a task as done."""
        if task_id not in self._nodes:
            raise KeyError(f"Task '{task_id}' not found")
        self._nodes[task_id].status = "done"

    def mark_failed(self, task_id: str) -> None:
        """Mark a task as failed."""
        if task_id not in self._nodes:
            raise KeyError(f"Task '{task_id}' not found")
        self._nodes[task_id].status = "failed"

    def detect_cycles(self) -> list[list[str]]:
        """Detect and return all cycles in the graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2  # noqa: N806
        color: dict[str, int] = dict.fromkeys(self._nodes, WHITE)
        path: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for dep in self._edges.get(node, set()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])  # noqa: RUF005
                elif color[dep] == WHITE:
                    dfs(dep)
            path.pop()
            color[node] = BLACK

        for tid in self._nodes:
            if color[tid] == WHITE:
                dfs(tid)
        return cycles

    def get_critical_path(self) -> list[str]:
        """Return the longest dependency chain (critical path)."""
        if not self._nodes:
            return []

        order = self.get_execution_order()
        dist: dict[str, int] = dict.fromkeys(order, 0)
        parent: dict[str, str | None] = dict.fromkeys(order)

        for tid in order:
            for other_tid in self._nodes:
                if tid in self._edges.get(other_tid, set()):
                    if dist[tid] + 1 > dist[other_tid]:
                        dist[other_tid] = dist[tid] + 1
                        parent[other_tid] = tid

        end_node = max(dist, key=lambda t: dist[t])
        path: list[str] = []
        current: str | None = end_node
        while current is not None:
            path.append(current)
            current = parent[current]
        path.reverse()
        return path

    def get_blocked_tasks(self) -> list[str]:
        """Return tasks blocked by failed dependencies."""
        blocked = []
        for tid, node in self._nodes.items():
            if node.status in ("done", "failed"):
                continue
            deps = self._edges.get(tid, set())
            has_failed = any(self._nodes[d].status == "failed" for d in deps if d in self._nodes)
            if has_failed:
                blocked.append(tid)
        return blocked
