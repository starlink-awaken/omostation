"""Worker abstraction layer for D_Execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, EnumType, auto
from typing import Any


class _DefaultEnumMeta(EnumType):
    def __call__(cls, value=None, *args, **kwargs):
        if value is None:
            return next(iter(cls))
        return super().__call__(value, *args, **kwargs)


class WorkerStatus(Enum, metaclass=_DefaultEnumMeta):
    """Operational status of a worker."""

    IDLE = auto()
    BUSY = auto()
    PAUSED = auto()
    TERMINATED = auto()
    ERROR = auto()


class WorkerType(Enum, metaclass=_DefaultEnumMeta):
    """Classification of worker implementations."""

    DAEMON = auto()
    CLI = auto()
    SUBPROCESS = auto()
    MCP_BRIDGE = auto()
    PYTHON = auto()
    REMOTE = auto()


@dataclass
class WorkerCapability:
    """Descriptor for a single worker capability."""

    name: str = "generic"
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, requirement: str) -> bool:
        """Check if this capability matches a requirement string."""
        return requirement.startswith(self.name)


@dataclass
class WorkerMetrics:
    """Performance and health metrics for a worker."""

    task_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency: float = 0.0
    current_load: float = 0.0
    max_load: float = 1.0

    @property
    def success_rate(self) -> float:
        """Fraction of completed tasks that succeeded."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 1.0

    @property
    def load_factor(self) -> float:
        """Current load as a fraction of maximum capacity."""
        return self.current_load / self.max_load if self.max_load > 0 else 0.0


class WorkerAbstract:
    """Abstract base for all worker implementations.

    Subclasses must implement :meth:`execute`.
    """

    def __init__(
        self,
        worker_id: str = "stub-worker",
        worker_type: WorkerType = WorkerType.DAEMON,
        capabilities: list[WorkerCapability] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.capabilities = capabilities or []
        self.status = WorkerStatus.IDLE
        self.metrics = WorkerMetrics()

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute a task and return the result."""
        return {"status": "noop", "task": task}

    def can_handle(self, task: dict[str, Any]) -> bool:
        """Check whether this worker can handle a task based on capabilities.

        A worker can handle a task when every required capability listed in
        the task payload is matched by at least one of the worker's own
        capabilities (by prefix matching).
        """
        required = task.get("capabilities", [])
        available = {c.name for c in self.capabilities}
        return all(any(req.startswith(cap) for cap in available) for req in required)
