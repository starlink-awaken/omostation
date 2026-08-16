"""Task Dispatcher — priority queues, QoS, preemption + agent match stub."""

from __future__ import annotations

import logging
import time as _time
from dataclasses import dataclass
from enum import IntEnum

_log = logging.getLogger(__name__)

# ── QoS thresholds (seconds) ──
QOS_P0_MAX_SEC = 300  # 5 minutes
QOS_P1_MAX_SEC = 1800  # 30 minutes


class Priority(IntEnum):
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_NORMAL = 2
    P3_LOW = 3


@dataclass
class Task:
    id: str
    priority: Priority
    description: str
    status: str = "queued"
    submitted_at: float = 0.0
    started_at: float | None = None


class TaskDispatcher:
    """Priority-queue task dispatcher with preemption, QoS monitoring,
    and stub agent matching.

    Usage::

        d = TaskDispatcher()
        d.submit("my task", Priority.P1_HIGH)
        task = d.next()          # dequeue highest-priority task
        d.status(task.id)        # "running"
        d.check_qos()            # { "P0": { "count": 0, "max_wait_seconds": 0 }, ... }
        d.find_agent(cap, agents)  # filter agents by capability
        d.stats()                # queue breakdown
    """

    def __init__(self) -> None:
        self.queues: dict[Priority, list[Task]] = {p: [] for p in Priority}
        self.running: Task | None = None
        self._id_counter = 0

    # ── Core ops ──

    def submit(self, desc: str, priority: Priority = Priority.P2_NORMAL) -> Task:
        self._id_counter += 1
        t = Task(
            id=f"T{self._id_counter:04d}",
            priority=priority,
            description=desc,
            submitted_at=_time.time(),
        )
        self.queues[priority].append(t)
        return t

    def next(self) -> Task | None:
        """Dequeue the highest-priority task.

        * If nothing is running, the highest-priority queued task starts.
        * If a task is running and a *strictly higher* priority task is
          queued, the running task is **preempted** (re-queued, status
          set back to ``queued``) and the higher-priority task starts.
        * Otherwise returns ``None`` (current task keeps running).
        """
        for p in sorted(Priority):
            if not self.queues[p]:
                continue
            t = self.queues[p].pop(0)
            # Preempt lower-priority running task if new task is strictly higher
            if self.running and p.value >= self.running.priority.value:
                # New task has equal or lower priority — put it back and do nothing
                self.queues[p].insert(0, t)
                return None
            # Preempt: pause the running task
            if self.running:
                self.queues[self.running.priority].insert(0, self.running)
                _log.info("Preempted %s for %s", self.running.id, t.id)
                self.running.status = "queued"
            self.running = t
            t.started_at = _time.time()
            t.status = "running"
            return t
        return None

    def status(self, task_id: str) -> str | None:
        for q in self.queues.values():
            for t in q:
                if t.id == task_id:
                    return t.status
        if self.running and self.running.id == task_id:
            return self.running.status
        return None

    def stats(self) -> dict:
        return {
            "queued": sum(len(q) for q in self.queues.values()),
            "running": 1 if self.running else 0,
            "queues": {p.name: len(self.queues[p]) for p in Priority},
        }

    # ── QoS ──

    def check_qos(self) -> dict[str, dict]:
        """Return per-priority wait-time report.

        Returns a dict keyed by ``"P0"`` … ``"P3"`` with:
        ``count`` — number of queued tasks
        ``max_wait_seconds`` — longest wait among queued tasks
        """
        now = _time.time()
        report: dict[str, dict] = {}
        for p in Priority:
            key = p.name.split("_")[0]  # "P0", "P1", …
            q = self.queues[p]
            if not q:
                continue
            waits = [now - t.submitted_at for t in q]
            report[key] = {
                "count": len(q),
                "max_wait_seconds": max(waits),
            }
        return report

    # ── Agent matching stub ──

    @staticmethod
    def find_agent(capability: str, agents: list[dict]) -> list[dict]:
        """Find agents whose capabilities include *capability* (stub).

        Parameters
        ----------
        capability : str
            Required capability name (case-sensitive).
        agents : list[dict]
            List of agent dicts, each may contain a ``"capabilities"`` key
            (list of str).

        Returns
        -------
        list[dict]
            Subset of *agents* whose capabilities include the requested
            capability.
        """
        return [a for a in agents if capability in a.get("capabilities", [])]
