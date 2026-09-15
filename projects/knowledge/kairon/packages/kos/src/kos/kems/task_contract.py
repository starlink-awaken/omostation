"""Evidence-bound task draft contract shared by KEMS and OMO adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

TaskStatus = Literal["draft", "approved", "dispatched", "verified", "closed", "rejected"]


@dataclass(frozen=True)
class TaskDraft:
    task_id: str
    source_run_id: str
    title: str
    owner: str
    due_at: str
    acceptance_criteria: str
    evidence_refs: tuple[str, ...]
    graph_refs: tuple[str, ...] = ()
    priority: Literal["P0", "P1", "P2", "P3"] = "P2"
    risk_level: Literal["low", "medium", "high"] = "medium"
    status: TaskStatus = "draft"

    def __post_init__(self) -> None:
        required = {
            "task_id": self.task_id,
            "source_run_id": self.source_run_id,
            "title": self.title,
            "owner": self.owner,
            "due_at": self.due_at,
            "acceptance_criteria": self.acceptance_criteria,
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("task drafts require source, title, owner, due_at, and acceptance criteria")
        if not self.evidence_refs:
            raise ValueError("task drafts require at least one evidence reference")

    @property
    def idempotency_key(self) -> str:
        return f"{self.source_run_id}:{self.task_id}"

    def approve(self, reviewer: str) -> TaskDraft:
        if not reviewer.strip():
            raise ValueError("task approval requires a reviewer")
        if self.status != "draft":
            raise ValueError(f"only draft tasks can be approved, got {self.status}")
        return self.__class__(
            **{**asdict(self), "status": "approved", "evidence_refs": self.evidence_refs, "graph_refs": self.graph_refs}
        )

    def to_omo_payload(self) -> dict[str, Any]:
        """Return a transport payload; OMO remains the task state authority."""
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        result["graph_refs"] = list(self.graph_refs)
        result["idempotency_key"] = self.idempotency_key
        result["approval_required"] = self.risk_level != "low"
        return result
