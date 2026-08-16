"""Governed source admission and durable pipeline run contracts for KEMS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DataDomain = Literal["official_work", "project_engineering", "personal", "quarantine"]
Sensitivity = Literal["public", "internal", "personal", "financial", "credential", "secret"]
RedactionStatus = Literal["not_required", "pending", "verified", "rejected"]
StepStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]


@dataclass(frozen=True)
class SourceManifest:
    """One immutable source admission record; raw content stays outside KEMS."""

    source_id: str
    source_type: str
    source_uri: str
    content_sha256: str
    domain: DataDomain
    sensitivity: Sensitivity
    redaction_status: RedactionStatus
    connector_version: str
    captured_at: str

    def __post_init__(self) -> None:
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256 must be a 64-character SHA-256 digest")
        if not self.source_id or not self.source_uri or not self.connector_version:
            raise ValueError("source_id, source_uri, and connector_version are required")

    @property
    def admitted_to_work_graph(self) -> bool:
        """Only approved, non-personal material can enter the work graph."""
        return (
            self.domain in {"official_work", "project_engineering"}
            and self.redaction_status in {"not_required", "verified"}
            and self.sensitivity not in {"financial", "credential", "secret", "personal"}
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"admitted_to_work_graph": self.admitted_to_work_graph}


@dataclass
class StepRun:
    step_id: str
    status: StepStatus = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    output_sha256: str | None = None
    error_code: str | None = None


@dataclass
class PipelineRun:
    run_id: str
    pipeline_id: str
    source_ids: tuple[str, ...]
    steps: list[StepRun] = field(default_factory=list)
    status: Literal["pending", "running", "succeeded", "failed"] = "pending"
    error_count: int = 0

    def start(self) -> None:
        if self.status not in {"pending", "running"}:
            raise ValueError(f"cannot start a {self.status} pipeline run")
        self.status = "running"

    def record_step(self, step: StepRun) -> None:
        if self.status == "succeeded":
            raise ValueError("completed pipeline runs are immutable")
        for index, existing in enumerate(self.steps):
            if existing.step_id == step.step_id:
                self.steps[index] = step
                break
        else:
            self.steps.append(step)
        if step.status == "failed":
            self.error_count += 1

    def finish(self, *, required_steps: tuple[str, ...]) -> None:
        missing = set(required_steps) - {step.step_id for step in self.steps}
        failed = {step.step_id for step in self.steps if step.step_id in required_steps and step.status != "succeeded"}
        if missing or failed:
            self.status = "failed"
            self.error_count += len(missing | failed)
            return
        self.status = "succeeded"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source_ids"] = list(self.source_ids)
        return result
