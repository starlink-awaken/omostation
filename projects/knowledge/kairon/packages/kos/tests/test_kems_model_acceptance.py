from __future__ import annotations

import pytest
from kos.kems import ModelAcceptanceStore, ModelInputError, evaluate_candidate


def cases() -> list[dict[str, object]]:
    return [
        {"case_id": "a", "predictions": [2, 2], "actual": [2, 3], "baseline_value": 4},
        {"case_id": "b", "predictions": [5, 5], "actual": [5, 6], "baseline_value": 8},
    ]


def test_candidate_result_is_redacted_and_store_is_idempotent(tmp_path) -> None:
    report = evaluate_candidate(cases(), candidate_model_id="moving-average-v1", min_cases=2)
    store = ModelAcceptanceStore(tmp_path / "acceptance.sqlite")

    assert report["status"] == "shadow_pass"
    assert report["promotion"] == "blocked_until_omo_approval"
    assert store.record("run-1", report) is True
    assert store.record("run-1", report) is False
    assert store.get("run-1")["report"] == report  # type: ignore[reportOptionalSubscript]


def test_acceptance_store_cannot_authorize_promotion(tmp_path) -> None:
    report = evaluate_candidate(cases(), candidate_model_id="candidate-v1") | {"promotion": "approved"}
    with pytest.raises(ValueError, match="cannot authorize"):
        ModelAcceptanceStore(tmp_path / "acceptance.sqlite").record("run-1", report)


def test_candidate_rejects_raw_content() -> None:
    with pytest.raises(ModelInputError, match="raw content"):
        evaluate_candidate(cases() + [{"case_id": "bad", "text": "private"}], candidate_model_id="candidate-v1")


def test_candidate_can_bind_acceptance_to_evaluation_manifest() -> None:
    report = evaluate_candidate(
        cases(),
        candidate_model_id="candidate-v1",
        dataset_id="kems-real",
        dataset_version="v1",
        evaluation_manifest_sha256="a" * 64,
        dataset_sample_count=2,
    )
    assert report["dataset_id"] == "kems-real"
    assert report["dataset_version"] == "v1"
    assert report["evaluation_manifest_sha256"] == "a" * 64
    assert report["dataset_sample_count"] == 2


def test_candidate_rejects_partial_manifest_binding() -> None:
    with pytest.raises(ModelInputError, match="required together"):
        evaluate_candidate(cases(), candidate_model_id="candidate-v1", dataset_id="kems-real")
