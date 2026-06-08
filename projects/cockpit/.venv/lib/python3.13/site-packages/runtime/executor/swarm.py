"""Swarm Protocol — master-worker coordination for parallel agent execution."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SwarmNode:
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    role: str = "worker"
    status: str = "idle"
    capabilities: list[str] = field(default_factory=list)
    last_heartbeat: float = field(default_factory=time.time)

@dataclass
class SwarmTask:
    task_id: str
    action: str = ""
    params: dict = field(default_factory=dict)
    assigned_to: str = "",  # type: ignore[assignment]
    status: str = "pending"
    result: Any = None

class SwarmCoordinator:
    """Master node that coordinates worker nodes for parallel execution."""

    def __init__(self, heartbeat_interval: float = 5.0, node_timeout: float = 30.0):
        self.heartbeat_interval = heartbeat_interval
        self.node_timeout = node_timeout
        self._nodes: dict[str, SwarmNode] = {}
        self._tasks: dict[str, SwarmTask] = {}
        self._results: dict[str, Any] = {}
        self._running = False

    def register_worker(self, capabilities: list[str] | None = None) -> str:
        node = SwarmNode(role="worker", capabilities=capabilities or [])
        self._nodes[node.node_id] = node
        return node.node_id

    def register_master(self) -> str:
        node = SwarmNode(role="master")
        self._nodes[node.node_id] = node
        return node.node_id

    def heartbeat(self, node_id: str):
        node = self._nodes.get(node_id)
        if node:
            node.last_heartbeat = time.time()

    def get_available_workers(self) -> list[SwarmNode]:
        now = time.time()
        return [n for n in self._nodes.values()
                if n.role == "worker" and n.status == "idle"
                and (now - n.last_heartbeat) < self.node_timeout]

    def assign_task(self, task_id: str, action: str, params: dict | None = None) -> str | None:
        workers = self.get_available_workers()
        if not workers:
            return None
        worker = workers[0]
        task = SwarmTask(task_id=task_id, action=action, params=params or {}, assigned_to=worker.node_id, status="running")
        self._tasks[task_id] = task
        worker.status = "busy"
        return worker.node_id

    def complete_task(self, task_id: str, result: Any):
        task = self._tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result = result
            self._results[task_id] = result
            worker = self._nodes.get(task.assigned_to)
            if worker:
                worker.status = "idle"

    def fail_task(self, task_id: str, error: str):
        task = self._tasks.get(task_id)
        if task:
            task.status = "failed"
            task.result = error
            worker = self._nodes.get(task.assigned_to)
            if worker:
                worker.status = "idle"

    def rebalance(self) -> int:
        """Redistribute pending tasks across available workers."""
        pending = [t for t in self._tasks.values() if t.status == "pending"]
        count = 0
        for task in pending:
            wid = self.assign_task(task.task_id, task.action, task.params)
            if wid:
                count += 1
        return count

    def get_status(self) -> dict:
        nodes = {n.node_id: {"role": n.role, "status": n.status, "capabilities": n.capabilities}
                 for n in self._nodes.values()}
        tasks = {t.task_id: {"status": t.status, "assigned_to": t.assigned_to}
                 for t in self._tasks.values()}
        return {"nodes": nodes, "tasks": tasks, "total_tasks": len(self._tasks), "total_nodes": len(self._nodes)}
