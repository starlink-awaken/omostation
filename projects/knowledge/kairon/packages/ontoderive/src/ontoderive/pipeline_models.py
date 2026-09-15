"""Pipeline data models — re-exported for compatibility.

These are the canonical pipeline model classes (ProgressInfo, StepResult,
StepStatus, BatchItem, BatchResult) used by the ontoderive pipeline steps.
Originally sourced from engine/pipeline_models; restored here for
backward compatibility after the engine/ directory was removed in P30.

Used by:
  - pipeline_steps.base (PipelineStep class)
  - governance_steps (RootNamespaceStep, SectionIndexStep, AgentContextStep)
  - validation_steps (BatchValidateStep, EvolveStep, ValidateStep)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class StepStatus(str, enum.Enum):  # noqa: UP042
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class ProgressInfo:
    """Progress information for a pipeline step."""

    step_name: str
    current: int = 0
    total: int = 0
    completed: int = 0
    failed: int = 0
    message: str = ""

    def __post_init__(self) -> None:
        if self.current < 0:
            raise ValueError(f"current must be >= 0, got {self.current}")
        if self.completed < 0:
            raise ValueError(f"completed must be >= 0, got {self.completed}")
        if self.failed < 0:
            raise ValueError(f"failed must be >= 0, got {self.failed}")
        if self.total < 0:
            raise ValueError(f"total must be >= 0, got {self.total}")
        if self.total and self.current > self.total:
            raise ValueError(f"current ({self.current}) cannot exceed total ({self.total})")


@dataclass(slots=True)
class StepResult:
    """Result of a pipeline step execution."""

    step_name: str
    status: StepStatus = StepStatus.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    items_processed: int = 0
    items_failed: int = 0

    def __post_init__(self) -> None:
        if self.items_processed < 0:
            raise ValueError(f"items_processed must be >= 0, got {self.items_processed}")
        if self.items_failed < 0:
            raise ValueError(f"items_failed must be >= 0, got {self.items_failed}")
        if self.items_failed > self.items_processed:
            raise ValueError(
                f"items_failed ({self.items_failed}) cannot exceed items_processed ({self.items_processed})"
            )
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValueError(f"end_time ({self.end_time}) cannot precede start_time ({self.start_time})")


@dataclass(slots=True)
class BatchItem:
    """Item in a batch operation."""

    id: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("BatchItem id must be a non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError(f"BatchItem.data must be a dict, got {type(self.data).__name__}")
        if not isinstance(self.metadata, dict):
            raise ValueError(f"BatchItem.metadata must be a dict, got {type(self.metadata).__name__}")


@dataclass(slots=True)
class BatchResult:
    """Result of a batch operation."""

    items: list[BatchItem] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    total: int = 0
    completed: int = 0
    skipped: int = 0
    results: list[BatchItem] = field(default_factory=list)
    duration: float = 0.0

    def __post_init__(self) -> None:
        if self.succeeded < 0 or self.failed < 0 or self.completed < 0 or self.skipped < 0:
            raise ValueError("counters must be non-negative")
        if self.duration < 0:
            raise ValueError(f"duration must be >= 0, got {self.duration}")
        if self.completed + self.skipped > max(self.total, len(self.items)):
            raise ValueError(
                f"completed ({self.completed}) + skipped ({self.skipped}) "
                f"cannot exceed item count "
                f"(total={self.total}, items={len(self.items)})"
            )


__all__ = [
    "BatchItem",
    "BatchResult",
    "ProgressInfo",
    "StepResult",
    "StepStatus",
]
