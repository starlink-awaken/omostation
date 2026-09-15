from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, "scripts")

from kems_evaluate_model_candidate import (  # type: ignore[reportMissingImports]
    ModelInputError,
    evaluate_candidate,
    main,
)


def case(case_id: str, predictions: list[float], actual: list[float], baseline: float) -> dict[str, object]:
    return {"case_id": case_id, "predictions": predictions, "actual": actual, "baseline_value": baseline}


def test_candidate_passes_only_when_aggregate_improves_baseline() -> None:
    result = evaluate_candidate(
        [case("a", [2, 2], [2, 3], 4), case("b", [5, 5], [5, 6], 8)],
        candidate_model_id="candidate-v1",
        min_cases=2,
    )

    assert result["schema_version"] == "kems.model-acceptance.v1"
    assert result["status"] == "shadow_pass"
    assert result["promotion"] == "blocked_until_omo_approval"
    assert result["case_ids"] == ["a", "b"]


def test_threshold_and_case_count_can_keep_candidate_in_review() -> None:
    result = evaluate_candidate(
        [case("a", [3], [2], 4)],
        candidate_model_id="candidate-v1",
        min_cases=2,
        min_relative_improvement=0.2,
    )

    assert result["status"] == "needs_review"


def test_raw_text_is_not_an_accepted_input_shape() -> None:
    with pytest.raises(ModelInputError):
        evaluate_candidate(
            [{"case_id": "a", "text": "private", "predictions": [1], "actual": [1], "baseline_value": 2}],
            candidate_model_id="candidate-v1",
        )


def test_duplicate_case_ids_are_rejected() -> None:
    with pytest.raises(ModelInputError, match="unique"):
        evaluate_candidate(
            [case("a", [1], [1], 2), case("a", [1], [1], 2)],
            candidate_model_id="candidate-v1",
        )


def test_cli_emits_manifest_bound_report(tmp_path, monkeypatch) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([case("a", [2], [2], 4)]), encoding="utf-8")
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
            "kems_evaluate_model_candidate.py",
            "--input",
            str(cases_path),
            "--output",
            str(output_path),
            "--candidate-model-id",
            "candidate-v1",
            "--evaluation-manifest",
            str(manifest_path),
        ],
    )
    assert main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["dataset_id"] == "kems-real"
    assert report["dataset_sample_count"] == 1
