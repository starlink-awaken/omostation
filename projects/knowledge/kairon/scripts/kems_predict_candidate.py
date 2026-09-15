#!/usr/bin/env python3
"""Run a redacted numeric candidate predictor and emit a manifest-bound report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from kos.kems.model_acceptance import ModelInputError, evaluate_candidate

_FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}


def _number(value: object, *, field: str, case_id: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ModelInputError(f"case {case_id}: {field} must be a finite number")
    return float(value)


def _series(value: object, *, field: str, case_id: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ModelInputError(f"case {case_id}: {field} must be a non-empty list")
    return [_number(item, field=field, case_id=case_id) for item in value]


def _manifest_binding(path: Path) -> tuple[str, str, str, int]:
    raw = path.expanduser().resolve().read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "kems.evaluation-manifest.v1":
        raise ModelInputError("evaluation manifest has an unsupported schema")
    if payload.get("redaction_status") != "verified":
        raise ModelInputError("evaluation manifest must be redaction-verified")
    dataset_id = payload.get("dataset_id")
    dataset_version = payload.get("dataset_version")
    samples = payload.get("samples")
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ModelInputError("evaluation manifest dataset identity is incomplete")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ModelInputError("evaluation manifest dataset identity is incomplete")
    if not isinstance(samples, list) or not samples:
        raise ModelInputError("evaluation manifest has no samples")
    return dataset_id.strip(), dataset_version.strip(), hashlib.sha256(raw).hexdigest(), len(samples)


def predict_cases(payload: object, *, strategy: str, window: int) -> list[dict[str, Any]]:
    """Convert redacted history/actual cases into acceptance-contract cases."""
    if strategy not in {"naive-last", "moving-average"}:
        raise ModelInputError("unsupported prediction strategy")
    if window <= 0:
        raise ModelInputError("window must be positive")
    if not isinstance(payload, list) or not payload:
        raise ModelInputError("prediction input must be a non-empty list")

    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(payload, start=1):
        if not isinstance(record, dict):
            raise ModelInputError(f"case {index}: record must be an object")
        if _FORBIDDEN_KEYS.intersection(str(key).lower() for key in record):
            raise ModelInputError(f"case {index}: raw content fields are forbidden")
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ModelInputError(f"case {index}: case_id is required")
        case_id = case_id.strip()
        if case_id in seen_ids:
            raise ModelInputError("case_id values must be unique")
        seen_ids.add(case_id)
        history = _series(record.get("history"), field="history", case_id=case_id)
        actual = _series(record.get("actual"), field="actual", case_id=case_id)
        baseline_value = history[-1]
        if strategy == "naive-last":
            prediction = baseline_value
        else:
            recent = history[-window:]
            prediction = sum(recent) / len(recent)
        result.append(
            {
                "case_id": case_id,
                "predictions": [prediction] * len(actual),
                "actual": actual,
                "baseline_value": baseline_value,
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="redacted history/actual JSON")
    parser.add_argument("--output", required=True, type=Path, help="manifest-bound acceptance report JSON")
    parser.add_argument("--candidate-model-id", required=True)
    parser.add_argument("--strategy", choices=("naive-last", "moving-average"), default="moving-average")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    parser.add_argument("--evaluation-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        cases = predict_cases(payload, strategy=args.strategy, window=args.window)
        dataset_id, dataset_version, manifest_sha256, sample_count = _manifest_binding(args.evaluation_manifest)
        report = evaluate_candidate(
            cases,
            candidate_model_id=args.candidate_model_id,
            min_cases=args.min_cases,
            min_relative_improvement=args.min_relative_improvement,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            evaluation_manifest_sha256=manifest_sha256,
            dataset_sample_count=sample_count,
        )
        report["prediction_strategy"] = args.strategy
        report["prediction_window"] = args.window
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ModelInputError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
