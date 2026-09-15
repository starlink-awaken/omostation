from __future__ import annotations

import pytest
from kos.kems import OCRPageQuality, OCRQualityStore, assess_ocr_quality


def report(run_id: str = "ocr-1", *, status: str = "pass"):
    quality = assess_ocr_quality(
        run_id=run_id,
        document_id="doc-1",
        engine="local-ocr",
        model_version="v1",
        page_metrics=(OCRPageQuality(page=1, text_confidence=0.98, layout_confidence=0.96),),
        cer=0.02 if status == "pass" else 0.12,
        field_accuracy=0.98,
        table_cell_f1=0.95,
    )
    return quality


def test_report_is_persisted_without_raw_text_and_replay_is_idempotent(tmp_path):
    store = OCRQualityStore(tmp_path / "ocr.sqlite")
    quality = report()
    assert store.record_report(quality, source_sha256="a" * 64) is True
    assert store.record_report(quality, source_sha256="a" * 64) is False
    stored = store.get_report("ocr-1")
    assert stored["quality_status"] == "pass"  # type: ignore[reportOptionalSubscript]
    assert "text" not in stored["report"]  # type: ignore[reportOptionalSubscript]
    assert store.can_admit("ocr-1") is True


def test_review_and_reject_enter_queue_but_are_not_admitted(tmp_path):
    store = OCRQualityStore(tmp_path / "ocr.sqlite")
    review = assess_ocr_quality(
        run_id="ocr-review",
        document_id="doc-2",
        engine="arkcli",
        model_version="v2",
        page_metrics=(OCRPageQuality(page=1, text_confidence=0.70, layout_confidence=0.70),),
    )
    rejected = report("ocr-reject", status="reject")
    store.record_report(review, source_sha256="b" * 64)
    store.record_report(rejected, source_sha256="c" * 64)
    assert [item["run_id"] for item in store.review_queue()] == ["ocr-review", "ocr-reject"]
    assert store.can_admit("ocr-review") is False
    assert store.can_admit("ocr-reject") is False


def test_correction_is_append_only_and_removes_item_from_pending_queue(tmp_path):
    store = OCRQualityStore(tmp_path / "ocr.sqlite")
    quality = report("ocr-review", status="review")
    store.record_report(quality, source_sha256="d" * 64)
    correction_id = store.record_correction(
        "ocr-review",
        corrected_sha256="e" * 64,
        correction_ref="vault://redacted/corrections/ocr-review.json",
        annotator="reviewer-1",
    )
    assert correction_id > 0
    assert store.review_queue() == []
    assert store.get_report("ocr-review")["review_status"] == "corrected"  # type: ignore[reportOptionalSubscript]


def test_store_rejects_raw_or_invalid_hashes(tmp_path):
    store = OCRQualityStore(tmp_path / "ocr.sqlite")
    with pytest.raises(ValueError, match="SHA-256"):
        store.record_report(report(), source_sha256="not-a-hash")
