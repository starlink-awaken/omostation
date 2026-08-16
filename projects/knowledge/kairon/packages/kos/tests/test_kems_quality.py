"""Tests for KEMS OCR quality gates and evaluation contracts."""

import pytest
from kos.kems import (
    EvaluationManifest,
    EvaluationSample,
    OCRPageQuality,
    assess_ocr_quality,
    evaluate_field_mapping,
)


def page(*, text: float = 0.98, layout: float = 0.95) -> OCRPageQuality:
    return OCRPageQuality(page=1, text_confidence=text, layout_confidence=layout)


def test_ocr_quality_passes_only_when_all_metrics_clear_gate():
    report = assess_ocr_quality(
        run_id="ocr-1",
        document_id="doc-1",
        engine="local-ocr",
        model_version="v1",
        page_metrics=(page(),),
        cer=0.02,
        field_accuracy=0.98,
        table_cell_f1=0.95,
        evidence_refs=("source:doc-1#page=1",),
    )

    assert report.status == "pass"
    assert report.review_flags == ()
    assert report.to_dict()["schema_version"] == "kems.ocr-quality.v1"


def test_ocr_quality_routes_missing_metrics_to_review():
    report = assess_ocr_quality(
        run_id="ocr-2",
        document_id="doc-2",
        engine="arkcli",
        model_version="v2",
        page_metrics=(page(),),
        cer=0.02,
        field_accuracy=None,
        table_cell_f1=None,
    )

    assert report.status == "review"
    assert "missing_field_accuracy" in report.review_flags
    assert "missing_table_cell_f1" in report.review_flags


def test_ocr_quality_rejects_error_rate_above_threshold():
    report = assess_ocr_quality(
        run_id="ocr-3",
        document_id="doc-3",
        engine="local-ocr",
        model_version="v1",
        page_metrics=(page(),),
        cer=0.12,
        field_accuracy=0.98,
        table_cell_f1=0.95,
    )

    assert report.status == "reject"
    assert "cer_above_threshold" in report.review_flags


def test_evaluation_manifest_requires_redaction_and_unique_samples():
    sample = EvaluationSample(
        sample_id="sample-1",
        source_sha256="a" * 64,
        source_ref="vault://redacted/sample-1.pdf",
        scenario_id="policy-analysis",
        split="test",
        annotation_status="adjudicated",
        labels={"title": "通知"},
        annotation_version="ann-1",
    )

    manifest = EvaluationManifest(
        schema_version="kems.evaluation-manifest.v1",
        dataset_id="kems-pilot",
        dataset_version="2026-07-31",
        redaction_status="verified",
        samples=(sample,),
    )

    assert manifest.to_dict()["samples"][0]["sample_id"] == "sample-1"
    with pytest.raises(ValueError, match="redaction-verified"):
        EvaluationManifest(
            schema_version="kems.evaluation-manifest.v1",
            dataset_id="kems-pilot",
            dataset_version="bad",
            redaction_status="required",
            samples=(sample,),
        )


def test_field_evaluation_keeps_mismatches_visible():
    result = evaluate_field_mapping(
        dataset_id="kems-pilot",
        dataset_version="2026-07-31",
        model_id="rules-baseline",
        expected={"title": "通知", "issuer": "省卫生健康委"},
        actual={"title": "通知", "issuer": ""},
    )

    assert result.status == "needs_review"
    assert result.accuracy == 0.5
    assert result.to_dict()["fields"][1]["matched"] == 0
