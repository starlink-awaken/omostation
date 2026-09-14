from __future__ import annotations

import json
from pathlib import Path

from scripts.kems_evaluate_and_record_model import main


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    input_path = tmp_path / "cases.json"
    input_path.write_text(json.dumps([{"case_id": "case-1", "history": [1, 2, 3], "actual": [2, 2]}]), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "kems.evaluation-manifest.v1",
                "dataset_id": "kems-real",
                "dataset_version": "v1",
                "redaction_status": "verified",
                "samples": [{"sample_id": "sample-1"}],
            }
        ),
        encoding="utf-8",
    )
    return input_path, manifest_path


def test_evaluate_and_record_is_single_idempotent_flow(tmp_path: Path, capsys) -> None:
    input_path, manifest_path = _write_inputs(tmp_path)
    output_path = tmp_path / "acceptance.json"
    database_path = tmp_path / "acceptance.sqlite"
    args = [
        "--input",
        str(input_path),
        "--evaluation-manifest",
        str(manifest_path),
        "--output",
        str(output_path),
        "--run-id",
        "run-1",
        "--database",
        str(database_path),
        "--candidate-model-id",
        "moving-average-v1",
        "--min-cases",
        "1",
    ]

    assert main(args) == 0
    first = json.loads(output_path.read_text(encoding="utf-8"))
    assert first["status"] == "shadow_pass"
    assert first["dataset_id"] == "kems-real"
    assert output_path.stat().st_mode & 0o777 == 0o600

    assert main(args) == 0
    output = capsys.readouterr().out
    assert '"inserted": true' in output
    assert '"inserted": false' in output


def test_evaluate_and_record_fails_before_writing_unbound_manifest(tmp_path: Path, capsys) -> None:
    input_path, manifest_path = _write_inputs(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["redaction_status"] = "required"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        main(
            [
                "--input",
                str(input_path),
                "--evaluation-manifest",
                str(manifest_path),
                "--output",
                str(tmp_path / "acceptance.json"),
                "--run-id",
                "run-blocked",
                "--database",
                str(tmp_path / "acceptance.sqlite"),
                "--candidate-model-id",
                "candidate-v1",
            ]
        )
        == 1
    )
    assert "redaction-verified" in capsys.readouterr().out
