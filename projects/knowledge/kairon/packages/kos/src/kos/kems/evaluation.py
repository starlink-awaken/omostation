"""Versioned manifest and deterministic baseline contracts for KEMS evaluation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

EvaluationSplit = Literal["train", "validation", "test", "shadow"]
AnnotationStatus = Literal["pending", "reviewed", "adjudicated"]


@dataclass(frozen=True)
class EvaluationSample:
    sample_id: str
    source_sha256: str
    source_ref: str
    scenario_id: str
    split: EvaluationSplit
    annotation_status: AnnotationStatus
    labels: Mapping[str, Any]
    annotation_version: str

    def __post_init__(self) -> None:
        if not self.sample_id or not self.source_sha256 or len(self.source_sha256) != 64:
            raise ValueError("sample_id and a 64-character source_sha256 are required")
        if not self.source_ref or not self.scenario_id or not self.annotation_version:
            raise ValueError("source_ref, scenario_id, and annotation_version are required")
        if not self.labels:
            raise ValueError("evaluation samples require labels")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationManifest:
    schema_version: str
    dataset_id: str
    dataset_version: str
    redaction_status: Literal["required", "verified"]
    samples: tuple[EvaluationSample, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id or not self.dataset_version:
            raise ValueError("dataset_id and dataset_version are required")
        if not self.samples:
            raise ValueError("evaluation manifests require at least one sample")
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("evaluation sample_id values must be unique")
        if self.redaction_status != "verified":
            raise ValueError("evaluation manifests must be redaction-verified before use")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["samples"] = [sample.to_dict() for sample in self.samples]
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)


@dataclass(frozen=True)
class FieldEvaluation:
    field: str
    checked: int
    matched: int

    @property
    def accuracy(self) -> float:
        return self.matched / self.checked if self.checked else 0.0


@dataclass(frozen=True)
class EvaluationRun:
    schema_version: str
    dataset_id: str
    dataset_version: str
    model_id: str
    fields: tuple[FieldEvaluation, ...]
    status: Literal["pass", "needs_review"]

    @property
    def accuracy(self) -> float:
        checked = sum(item.checked for item in self.fields)
        matched = sum(item.matched for item in self.fields)
        return matched / checked if checked else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["fields"] = [{**asdict(item), "accuracy": item.accuracy} for item in self.fields]
        result["accuracy"] = self.accuracy
        return result


def evaluate_field_mapping(
    *,
    dataset_id: str,
    dataset_version: str,
    model_id: str,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> EvaluationRun:
    """Run an exact-match baseline while preserving missing fields for review."""
    fields = tuple(
        FieldEvaluation(field=field, checked=1, matched=int(actual.get(field) == value))
        for field, value in expected.items()
    )
    return EvaluationRun(
        schema_version="kems.evaluation-run.v1",
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        model_id=model_id,
        fields=fields,
        status="pass" if all(item.matched for item in fields) else "needs_review",
    )
