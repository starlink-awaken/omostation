#!/usr/bin/env python3
"""Evaluate a redacted forecast candidate against a deterministic baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from kos.kems.model_acceptance import ModelInputError, evaluate_candidate


def _manifest_binding(path: Path) -> tuple[str, str, str, int]:
    raw = path.expanduser().resolve().read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "kems.evaluation-manifest.v1":
        raise ModelInputError("evaluation manifest has an unsupported schema")
    if payload.get("redaction_status") != "verified":
        raise ModelInputError("evaluation manifest must be redaction-verified")
    dataset_id = payload.get("dataset_id")
    dataset_version = payload.get("dataset_version")
    if (
        not isinstance(dataset_id, str)
        or not dataset_id.strip()
        or not isinstance(dataset_version, str)
        or not dataset_version.strip()
    ):
        raise ModelInputError("evaluation manifest dataset identity is incomplete")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ModelInputError("evaluation manifest has no samples")
    return dataset_id.strip(), dataset_version.strip(), hashlib.sha256(raw).hexdigest(), len(samples)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="redacted forecast cases JSON")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-model-id", required=True)
    parser.add_argument("--baseline-model-id", default="naive-last-v1")
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    parser.add_argument("--evaluation-manifest", required=True, type=Path, help="adjudicated evaluation manifest")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        dataset_id, dataset_version, manifest_sha256, sample_count = _manifest_binding(args.evaluation_manifest)
        result = evaluate_candidate(
            payload,
            candidate_model_id=args.candidate_model_id,
            baseline_model_id=args.baseline_model_id,
            min_cases=args.min_cases,
            min_relative_improvement=args.min_relative_improvement,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            evaluation_manifest_sha256=manifest_sha256,
            dataset_sample_count=sample_count,
        )
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ModelInputError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
