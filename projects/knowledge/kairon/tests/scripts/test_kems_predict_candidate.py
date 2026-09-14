from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, "scripts")

from kems_predict_candidate import ModelInputError, main, predict_cases  # type: ignore[reportMissingImports]


def test_moving_average_generates_predictions_without_raw_content() -> None:
    result = predict_cases(
        [{"case_id": "a", "history": [2, 4, 6], "actual": [5, 6]}],
        strategy="moving-average",
        window=2,
    )
    assert result == [{"case_id": "a", "predictions": [5.0, 5.0], "actual": [5.0, 6.0], "baseline_value": 6.0}]


def test_predictor_rejects_private_content_and_duplicate_ids() -> None:
    with pytest.raises(ModelInputError, match="raw content"):
        predict_cases(
            [{"case_id": "a", "text": "private", "history": [1], "actual": [1]}], strategy="naive-last", window=1
        )
    with pytest.raises(ModelInputError, match="unique"):
        predict_cases(
            [{"case_id": "a", "history": [1], "actual": [1]}, {"case_id": "a", "history": [2], "actual": [2]}],
            strategy="naive-last",
            window=1,
        )


def test_cli_emits_manifest_bound_report(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "cases.json"
    input_path.write_text(json.dumps([{"case_id": "a", "history": [2, 4], "actual": [4, 5]}]), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "kems.evaluation-manifest.v1",
                "dataset_id": "kems-real",
                "dataset_version": "v1",
                "redaction_status": "verified",
                "samples": [{"sample_id": "s-1"}],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "acceptance.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kems_predict_candidate.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--candidate-model-id",
            "moving-average-v1",
            "--evaluation-manifest",
            str(manifest_path),
        ],
    )
    assert main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["candidate_model_id"] == "moving-average-v1"
    assert report["prediction_strategy"] == "moving-average"
    assert report["promotion"] == "blocked_until_omo_approval"
