#!/usr/bin/env python3
"""Evaluate a redacted candidate model and persist its manifest-bound acceptance report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from kos.kems import ModelAcceptanceStore
from kos.kems.model_acceptance import ModelInputError, evaluate_candidate

try:
    from scripts.kems_predict_candidate import _manifest_binding, predict_cases
except ModuleNotFoundError:
    from kems_predict_candidate import _manifest_binding, predict_cases


def _database_argument() -> Path:
    return Path(os.environ.get("KEMS_MODEL_ACCEPTANCE_DB", str(Path.home() / ".kems" / "model-acceptance.sqlite")))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="redacted history/actual JSON")
    parser.add_argument("--evaluation-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="canonical acceptance report JSON")
    parser.add_argument("--run-id", required=True, help="immutable acceptance run identity")
    parser.add_argument("--database", type=Path, default=_database_argument())
    parser.add_argument("--candidate-model-id", required=True)
    parser.add_argument("--baseline-model-id", default="naive-last-v1")
    parser.add_argument("--strategy", choices=("naive-last", "moving-average"), default="moving-average")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        cases = predict_cases(payload, strategy=args.strategy, window=args.window)
        dataset_id, dataset_version, manifest_sha256, sample_count = _manifest_binding(
            args.evaluation_manifest.expanduser().resolve()
        )
        report = evaluate_candidate(
            cases,
            candidate_model_id=args.candidate_model_id,
            baseline_model_id=args.baseline_model_id,
            min_cases=args.min_cases,
            min_relative_improvement=args.min_relative_improvement,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            evaluation_manifest_sha256=manifest_sha256,
            dataset_sample_count=sample_count,
        )
        report["prediction_strategy"] = args.strategy
        report["prediction_window"] = args.window
        inserted = ModelAcceptanceStore(args.database.expanduser().resolve()).record(args.run_id, report)
        _write_report(args.output.expanduser().resolve(), report)
    except (OSError, json.JSONDecodeError, ModelInputError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {"status": "succeeded", "inserted": inserted, "run_id": args.run_id, **report},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
