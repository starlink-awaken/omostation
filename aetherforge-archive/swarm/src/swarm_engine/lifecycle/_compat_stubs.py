"""Runtime fallback type stubs for when nucleus is not available.

These provide ISwarmLifecycle, TaskResult, WorkerBundle, WorkerHandle, and
WorkerState as lightweight substitutes so lifecycle_manager can load without
the full nucleus package.

Extracted from lifecycle_manager.py (ARCH-003 SRP refactor).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ISwarmLifecycle(Protocol):
    def hatch(self, *a: Any, **kw: Any) -> Any: ...
    def reap(self, *a: Any, **kw: Any) -> Any: ...
    def list_active(self, *a: Any, **kw: Any) -> Any: ...


class TaskResult:
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    worker_id: str = ""
    task_id: str = ""
    success: bool = True
    output: str = ""
    eu_consumed: float = 0.0
    duration_s: float = 0.0
    quality_score: float = 0.0
    error: str = ""


class WorkerBundle:
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    total_tasks: int = 0
    successful_tasks: int = 0
    total_eu_consumed: float = 0.0


class WorkerHandle:
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    worker_id: str = ""
    pid: int = 0
    state: Any = None


class WorkerState(StrEnum):
    HATCHING = "HATCHING"
    ACTIVE = "ACTIVE"
    STARVING = "STARVING"
    REAPED = "REAPED"
