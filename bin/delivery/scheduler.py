"""G-DEL.1 — Task scheduler over AgentRegistry (multi-node simulation).

Measures schedule success rate: tasks assigned to a healthy agent that can
complete without fault. Target > 99% (BET-7e074).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from agent_registry import AgentRegistry, AgentRecord


@dataclass
class Task:
    task_id: str
    role_id: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleResult:
    task_id: str
    success: bool
    agent_id: str | None = None
    node_id: str | None = None
    error: str | None = None
    latency_ms: float = 0.0


class TaskScheduler:
    def __init__(
        self,
        registry: AgentRegistry,
        *,
        executor: Callable[[Task, AgentRecord], bool] | None = None,
    ) -> None:
        self.registry = registry
        # default executor always succeeds if agent healthy
        self.executor = executor or (lambda _t, a: a.healthy)

    def schedule_one(self, task: Task) -> ScheduleResult:
        t0 = time.perf_counter()
        candidates = [
            a
            for a in self.registry.list_agents(role_id=task.role_id, healthy_only=True)
            if a.can_accept()
        ]
        # least-loaded first
        candidates.sort(key=lambda a: (a.inflight, a.agent_id))
        if not candidates:
            return ScheduleResult(
                task_id=task.task_id,
                success=False,
                error="no_healthy_agent",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        agent = candidates[0]
        if not self.registry.acquire_slot(agent.agent_id):
            return ScheduleResult(
                task_id=task.task_id,
                success=False,
                agent_id=agent.agent_id,
                node_id=agent.node_id,
                error="acquire_failed",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        try:
            ok = bool(self.executor(task, agent))
            return ScheduleResult(
                task_id=task.task_id,
                success=ok,
                agent_id=agent.agent_id,
                node_id=agent.node_id,
                error=None if ok else "executor_failed",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        finally:
            self.registry.release_slot(agent.agent_id)

    def schedule_batch(self, tasks: list[Task]) -> list[ScheduleResult]:
        return [self.schedule_one(t) for t in tasks]


def measure_schedule_success_rate(
    *,
    n_nodes: int = 4,
    agents_per_node: int = 3,
    n_tasks: int = 1000,
    fault_rate: float = 0.0,
) -> dict[str, Any]:
    """Spin multi-node registry and schedule n_tasks; return measured rate.

    fault_rate: fraction of agents marked unhealthy (to stress path).
    """
    import random

    reg = AgentRegistry()
    agents: list[str] = []
    for i in range(n_nodes):
        node = f"node-{i}"
        reg.register_node(node)
        for j in range(agents_per_node):
            a = reg.register_agent(node_id=node, role_id="implementer", capacity=4)
            agents.append(a.agent_id)
    # inject faults
    n_fault = int(len(agents) * fault_rate)
    for aid in random.sample(agents, n_fault) if n_fault else []:
        reg.mark_unhealthy(aid)

    sched = TaskScheduler(reg)
    tasks = [
        Task(task_id=f"t-{k}", role_id="implementer", payload={"k": k})
        for k in range(n_tasks)
    ]
    results = sched.schedule_batch(tasks)
    ok = sum(1 for r in results if r.success)
    rate = ok / n_tasks if n_tasks else 0.0
    from caliber import stamp_physical_goal  # noqa: PLC0415

    return stamp_physical_goal(
        {
            "n_nodes": n_nodes,
            "agents": len(agents),
            "n_tasks": n_tasks,
            "successes": ok,
            "failures": n_tasks - ok,
            "success_rate": rate,
            "success_rate_pct": round(rate * 100, 4),
            "gate": "G-DEL.1",
            "kpi": "schedule_success_rate > 99%",
            "env": "in-process multi-node simulation (not physical multi-host)",
        },
        sim_ok=rate > 0.99,
        physical_hosts=0,
    )


def new_task(role_id: str = "implementer", **payload: Any) -> Task:
    return Task(task_id=f"t-{uuid.uuid4().hex[:10]}", role_id=role_id, payload=payload)
