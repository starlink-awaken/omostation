"""Tests for persisted, redaction-verified evaluation datasets."""

import pytest
from kos.kems import EvaluationManifest, EvaluationSample, EvaluationStore, evaluate_field_mapping


def manifest(source_ref="vault://redacted/policy-1.pdf"):
    sample = EvaluationSample(
        "sample-1", "a" * 64, source_ref, "policy-analysis", "test", "adjudicated", {"title": "通知"}, "ann-1"
    )
    return EvaluationManifest("kems.evaluation-manifest.v1", "pilot", "v1", "verified", (sample,))


def test_store_requires_redacted_vault_sources_and_is_idempotent(tmp_path):
    store = EvaluationStore(tmp_path / "evaluation.sqlite")
    assert store.register_manifest(manifest()) is True
    assert store.register_manifest(manifest()) is False
    assert store.sample_count("pilot", "v1") == 1
    with pytest.raises(ValueError, match="redacted vault"):
        store.register_manifest(manifest("file:///private/raw.pdf"))


def test_store_persists_regression_report(tmp_path):
    store = EvaluationStore(tmp_path / "evaluation.sqlite")
    store.register_manifest(manifest())
    run = evaluate_field_mapping(
        dataset_id="pilot",
        dataset_version="v1",
        model_id="rules-v1",
        expected={"title": "通知"},
        actual={"title": "通知"},
    )
    store.record_run("eval-run-1", run)
    stored = store.get_run("eval-run-1")
    assert stored is not None
    assert stored["accuracy"] == 1.0
    assert stored["report"]["model_id"] == "rules-v1"  # type: ignore[reportIndexIssue]
