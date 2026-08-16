# pyright: reportMissingImports=false
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
KOS_SRC_DIR = Path(__file__).resolve().parents[2] / "packages" / "kos" / "src"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(KOS_SRC_DIR))

from kems_build_eval_manifest import (
    ManifestInputError,
    build_manifest,
    build_manifest_from_database,
    write_manifest,
)
from kos.kems import AdjudicationStore


def record(*, sample_id: str = "sample-1", status: str = "adjudicated") -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": status,
        "labels": {"title": "通知"},
        "annotation_version": "ann-1",
    }


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n", encoding="utf-8")


def test_build_manifest_keeps_only_redacted_contract_fields(tmp_path: Path) -> None:
    input_path = tmp_path / "adjudicated.jsonl"
    write_jsonl(input_path, [record() | {"reviewer": "human-1", "private_note": "discarded"}])

    manifest = build_manifest(input_path, dataset_id="kems-real", dataset_version="2026-08-01")

    assert manifest.redaction_status == "verified"
    assert manifest.to_dict()["samples"] == [record()]


def test_build_manifest_rejects_non_adjudicated_samples(tmp_path: Path) -> None:
    input_path = tmp_path / "pending.jsonl"
    write_jsonl(input_path, [record(status="reviewed")])

    with pytest.raises(ManifestInputError, match="not adjudicated"):
        build_manifest(input_path, dataset_id="kems-real", dataset_version="v1")


def test_build_manifest_rejects_nested_raw_content(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.jsonl"
    item = record()
    item["labels"] = {"title": "通知", "evidence": {"text": "private"}}
    write_jsonl(input_path, [item])

    with pytest.raises(ManifestInputError, match="raw content key"):
        build_manifest(input_path, dataset_id="kems-real", dataset_version="v1")


def test_build_manifest_rejects_duplicate_ids_and_invalid_hash(tmp_path: Path) -> None:
    duplicate_path = tmp_path / "duplicate.jsonl"
    write_jsonl(duplicate_path, [record(), record()])
    with pytest.raises(ManifestInputError, match="duplicated"):
        build_manifest(duplicate_path, dataset_id="kems-real", dataset_version="v1")

    invalid_path = tmp_path / "invalid.jsonl"
    invalid = record()
    invalid["source_sha256"] = "not-a-sha"
    write_jsonl(invalid_path, [invalid])
    with pytest.raises(ManifestInputError, match="source_sha256 is invalid"):
        build_manifest(invalid_path, dataset_id="kems-real", dataset_version="v1")


def test_write_manifest_is_parseable(tmp_path: Path) -> None:
    input_path = tmp_path / "adjudicated.jsonl"
    output_path = tmp_path / "out" / "manifest.json"
    write_jsonl(input_path, [record()])
    write_manifest(build_manifest(input_path, dataset_id="kems-real", dataset_version="v1"), output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "kems.evaluation-manifest.v1"
    assert not list(output_path.parent.glob(".*.tmp"))


def test_build_manifest_from_persisted_adjudication(tmp_path: Path) -> None:
    database_path = tmp_path / "adjudication.sqlite"
    store = AdjudicationStore(database_path)
    store.ingest_queue([record(status="pending")])
    store.claim("sample-1", annotator="annotator-a")
    store.claim("sample-1", annotator="annotator-b")
    store.submit_annotation("sample-1", labels={"title": "通知"}, annotation_version="ann-1", annotator="annotator-a")
    store.submit_annotation("sample-1", labels={"title": "通知"}, annotation_version="ann-1", annotator="annotator-b")
    store.adjudicate("sample-1", labels={"title": "通知"}, annotation_version="ann-1", adjudicator="reviewer")

    manifest = build_manifest_from_database(database_path, dataset_id="kems-real", dataset_version="v1")

    assert manifest.to_dict()["samples"] == [record()]
    assert "annotator" not in manifest.to_json()


def test_build_manifest_from_database_rejects_pending_only_queue(tmp_path: Path) -> None:
    database_path = tmp_path / "adjudication.sqlite"
    store = AdjudicationStore(database_path)
    store.ingest_queue([record(status="pending")])

    with pytest.raises(ManifestInputError, match="no adjudicated samples"):
        build_manifest_from_database(database_path, dataset_id="kems-real", dataset_version="v1")
