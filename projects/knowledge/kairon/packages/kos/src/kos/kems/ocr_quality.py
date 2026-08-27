"""Deterministic OCR quality reports and admission gates for KEMS."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

QualityStatus = Literal["pass", "review", "reject"]


def _bounded_score(value: float, field: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return value


@dataclass(frozen=True)
class OCRQualityPolicy:
    """Admission thresholds; values are policy targets, not measured accuracy."""

    max_cer: float = 0.08
    min_field_accuracy: float = 0.95
    min_table_cell_f1: float = 0.90
    min_text_confidence: float = 0.90
    min_layout_confidence: float = 0.85

    def __post_init__(self) -> None:
        if self.max_cer < 0.0:
            raise ValueError("max_cer must be non-negative")
        for field in (
            "min_field_accuracy",
            "min_table_cell_f1",
            "min_text_confidence",
            "min_layout_confidence",
        ):
            _bounded_score(getattr(self, field), field)


@dataclass(frozen=True)
class OCRPageQuality:
    page: int
    text_confidence: float
    layout_confidence: float
    table_confidence: float | None = None

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be one-based")
        _bounded_score(self.text_confidence, "text_confidence")
        _bounded_score(self.layout_confidence, "layout_confidence")
        if self.table_confidence is not None:
            _bounded_score(self.table_confidence, "table_confidence")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OCRQualityReport:
    schema_version: str
    run_id: str
    document_id: str
    engine: str
    model_version: str
    page_metrics: tuple[OCRPageQuality, ...]
    cer: float | None
    field_accuracy: float | None
    table_cell_f1: float | None
    status: QualityStatus
    review_flags: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.run_id or not self.document_id or not self.engine or not self.model_version:
            raise ValueError("run_id, document_id, engine, and model_version are required")
        if not self.page_metrics:
            raise ValueError("OCR quality reports require at least one page")
        if self.cer is not None and self.cer < 0.0:
            raise ValueError("cer must be non-negative")
        for field in ("field_accuracy", "table_cell_f1"):
            value = getattr(self, field)
            if value is not None:
                _bounded_score(value, field)

    @property
    def needs_human_review(self) -> bool:
        return self.status == "review"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["page_metrics"] = [page.to_dict() for page in self.page_metrics]
        result["review_flags"] = list(self.review_flags)
        result["evidence_refs"] = list(self.evidence_refs)
        return result


def assess_ocr_quality(
    *,
    run_id: str,
    document_id: str,
    engine: str,
    model_version: str,
    page_metrics: tuple[OCRPageQuality, ...],
    cer: float | None = None,
    field_accuracy: float | None = None,
    table_cell_f1: float | None = None,
    evidence_refs: tuple[str, ...] = (),
    policy: OCRQualityPolicy | None = None,
) -> OCRQualityReport:
    """Assess OCR output without changing or silently repairing the source text."""
    gate = policy or OCRQualityPolicy()
    flags: list[str] = []
    if cer is None:
        flags.append("missing_cer")
    elif cer > gate.max_cer:
        flags.append("cer_above_threshold")
    if field_accuracy is None:
        flags.append("missing_field_accuracy")
    elif field_accuracy < gate.min_field_accuracy:
        flags.append("field_accuracy_below_threshold")
    if table_cell_f1 is None:
        flags.append("missing_table_cell_f1")
    elif table_cell_f1 < gate.min_table_cell_f1:
        flags.append("table_cell_f1_below_threshold")
    if min(page.text_confidence for page in page_metrics) < gate.min_text_confidence:
        flags.append("page_text_confidence_below_threshold")
    if min(page.layout_confidence for page in page_metrics) < gate.min_layout_confidence:
        flags.append("page_layout_confidence_below_threshold")

    hard_fail = any(flag.endswith("above_threshold") for flag in flags)
    status: QualityStatus = "reject" if hard_fail else ("review" if flags else "pass")
    return OCRQualityReport(
        schema_version="kems.ocr-quality.v1",
        run_id=run_id,
        document_id=document_id,
        engine=engine,
        model_version=model_version,
        page_metrics=page_metrics,
        cer=cer,
        field_accuracy=field_accuracy,
        table_cell_f1=table_cell_f1,
        status=status,
        review_flags=tuple(flags),
        evidence_refs=evidence_refs,
    )
