#!/usr/bin/env python3
"""Build a redacted KEMS evaluation manifest from adjudicated JSONL or SQLite data."""
# pyright: reportInvalidTypeForm=false

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SPLITS = {"train", "validation", "test", "shadow"}


class ManifestInputError(ValueError):
    """The adjudication input cannot be admitted to a redacted manifest."""


def _load_evaluation_types() -> tuple[type, type]:
    """Load only the KEMS contract so system Python skips unrelated package imports."""
    try:
        from kos.kems import EvaluationManifest, EvaluationSample

        return EvaluationManifest, EvaluationSample
    except (ImportError, TypeError):
        module_path = (
            Path(__file__).resolve().parents[1] / "packages" / "kos" / "src" / "kos" / "kems" / "evaluation.py"
        )
        spec = importlib.util.spec_from_file_location("kems_evaluation_contract", module_path)
        if spec is None or spec.loader is None:
            raise ManifestInputError("KEMS evaluation contract is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module.EvaluationManifest, module.EvaluationSample


EvaluationManifest, EvaluationSample = _load_evaluation_types()


def _forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return str(key)
            found = _forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _forbidden_key(child)
            if found:
                return found
    return None


def _required_string(sample: dict[str, Any], field: str, line_number: int) -> str:
    value = sample.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestInputError(f"line {line_number}: {field} must be a non-empty string")
    return value.strip()


def _validate_sample(sample: object, line_number: int, seen_ids: set[str]) -> dict[str, Any]:
    if not isinstance(sample, dict):
        raise ManifestInputError(f"line {line_number}: sample must be an object")
    forbidden = _forbidden_key(sample)
    if forbidden:
        raise ManifestInputError(f"line {line_number}: raw content key is forbidden")

    sample_id = _required_string(sample, "sample_id", line_number)
    if sample_id in seen_ids:
        raise ManifestInputError(f"line {line_number}: sample_id is duplicated")
    source_sha256 = _required_string(sample, "source_sha256", line_number)
    if not SHA256.fullmatch(source_sha256):
        raise ManifestInputError(f"line {line_number}: source_sha256 is invalid")
    source_ref = _required_string(sample, "source_ref", line_number)
    if not source_ref.startswith("vault://redacted/"):
        raise ManifestInputError(f"line {line_number}: source_ref must be redacted")
    scenario_id = _required_string(sample, "scenario_id", line_number)
    split = _required_string(sample, "split", line_number)
    if split not in SPLITS:
        raise ManifestInputError(f"line {line_number}: split is unsupported")
    annotation_status = _required_string(sample, "annotation_status", line_number)
    if annotation_status != "adjudicated":
        raise ManifestInputError(f"line {line_number}: sample is not adjudicated")
    annotation_version = _required_string(sample, "annotation_version", line_number)
    labels = sample.get("labels")
    if not isinstance(labels, dict) or not labels:
        raise ManifestInputError(f"line {line_number}: labels must be a non-empty object")
    seen_ids.add(sample_id)
    return {
        "sample_id": sample_id,
        "source_sha256": source_sha256,
        "source_ref": source_ref,
        "scenario_id": scenario_id,
        "split": split,
        "annotation_status": annotation_status,
        "labels": labels,
        "annotation_version": annotation_version,
    }


def build_manifest(input_path: Path, *, dataset_id: str, dataset_version: str) -> EvaluationManifest:
    if not dataset_id.strip() or not dataset_version.strip():
        raise ManifestInputError("dataset_id and dataset_version are required")
    if not input_path.is_file():
        raise ManifestInputError("adjudication JSONL is unavailable")

    try:
        lines = input_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ManifestInputError(f"unable to read adjudication JSONL: {type(exc).__name__}") from exc
    records: list[tuple[int, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append((line_number, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ManifestInputError(f"line {line_number}: invalid JSON") from exc
    return _build_manifest_from_records(
        records,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        empty_message="adjudication JSONL has no samples",
    )


def build_manifest_from_database(
    database_path: Path, *, dataset_id: str, dataset_version: str, limit: int = 10000
) -> EvaluationManifest:
    """Build a manifest from persisted, already-adjudicated redacted records."""
    if not database_path.is_file():
        raise ManifestInputError("adjudication database is unavailable")
    if limit <= 0:
        raise ManifestInputError("database limit must be positive")
    try:
        from kos.kems import AdjudicationStore
    except (ImportError, TypeError) as exc:
        raise ManifestInputError("KEMS adjudication store is unavailable") from exc
    try:
        records = AdjudicationStore(database_path).adjudicated_items(limit=limit)
    except (OSError, ValueError) as exc:
        raise ManifestInputError(f"unable to read adjudication database: {type(exc).__name__}") from exc
    return _build_manifest_from_records(
        [(index, record) for index, record in enumerate(records, start=1)],
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        empty_message="adjudication database has no adjudicated samples",
    )


def _build_manifest_from_records(
    records: list[tuple[int, object]],
    *,
    dataset_id: str,
    dataset_version: str,
    empty_message: str,
) -> EvaluationManifest:
    if not dataset_id.strip() or not dataset_version.strip():
        raise ManifestInputError("dataset_id and dataset_version are required")
    samples: list[EvaluationSample] = []  # type: ignore[reportInvalidTypeForm]
    seen_ids: set[str] = set()
    for line_number, record in records:
        validated = _validate_sample(record, line_number, seen_ids)
        samples.append(EvaluationSample(**validated))
    if not samples:
        raise ManifestInputError(empty_message)
    return EvaluationManifest(
        schema_version="kems.evaluation-manifest.v1",
        dataset_id=dataset_id.strip(),
        dataset_version=dataset_version.strip(),
        redaction_status="verified",
        samples=tuple(samples),
    )


def write_manifest(manifest: EvaluationManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        temporary.write_text(
            manifest.to_json() + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="adjudicated JSONL metadata")
    source.add_argument("--database", type=Path, help="persistent adjudication SQLite database")
    parser.add_argument("--output", required=True, type=Path, help="redacted manifest JSON")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()
    try:
        if args.database is not None:
            manifest = build_manifest_from_database(
                args.database.expanduser().resolve(),
                dataset_id=args.dataset_id,
                dataset_version=args.dataset_version,
            )
        else:
            manifest = build_manifest(
                args.input.expanduser().resolve(),
                dataset_id=args.dataset_id,
                dataset_version=args.dataset_version,
            )
        write_manifest(manifest, args.output.expanduser().resolve())
    except (ManifestInputError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "succeeded",
                "schema_version": manifest.schema_version,
                "dataset_id": manifest.dataset_id,
                "sample_count": len(manifest.samples),
                "output": str(args.output.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
