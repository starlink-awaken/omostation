"""Correlation record shared by KEMS import, analysis, and closeout."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

RunMode = Literal["fixture-backed", "low-risk-live", "production"]
RunStatus = Literal["completed", "failed_with_recovery", "blocked"]


@dataclass(frozen=True)
class KemsRunRecord:
    schema_version: str
    scenario_id: str
    request_id: str
    request_mode: RunMode
    source_sha256: str | None
    result_status: RunStatus
    output_schema: str
    evidence_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    review_status: Literal["pending", "approved", "rejected"]
    limits: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.request_id:
            raise ValueError("scenario_id and request_id are required")
        if self.result_status == "completed" and not self.evidence_refs:
            raise ValueError("completed KEMS runs require evidence_refs")
        if self.request_mode == "production" and self.review_status != "approved":
            raise ValueError("production KEMS runs require approved review_status")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        result["verification_refs"] = list(self.verification_refs)
        result["limits"] = list(self.limits)
        return result


def create_run_record(
    *,
    scenario_id: str,
    request_id: str,
    request_mode: RunMode,
    source_sha256: str | None,
    output_schema: str,
    evidence_refs: tuple[str, ...],
    verification_refs: tuple[str, ...],
    review_status: Literal["pending", "approved", "rejected"] = "pending",
    result_status: RunStatus = "completed",
    limits: tuple[str, ...] = (),
) -> KemsRunRecord:
    return KemsRunRecord(
        schema_version="kems.run-record.v1",
        scenario_id=scenario_id,
        request_id=request_id,
        request_mode=request_mode,
        source_sha256=source_sha256,
        result_status=result_status,
        output_schema=output_schema,
        evidence_refs=evidence_refs,
        verification_refs=verification_refs,
        review_status=review_status,
        limits=limits,
    )
