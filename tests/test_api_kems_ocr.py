# mock-heavy test file: monkeypatch assigns untyped attrs, so the attribute rule is disabled here.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


class FakeReport:
    run_id = "ocr-1"
    status = "review"
    needs_human_review = True

    def to_dict(self):
        return {"schema_version": "kems.ocr-quality.v1", "run_id": self.run_id, "status": self.status}


class FakeStore:
    def __init__(self, path):
        self.reports = {}

    def record_report(self, report, *, source_sha256):
        self.reports[report.run_id] = report
        return True

    def review_queue(self, *, limit):
        return [{"run_id": "ocr-1", "document_id": "doc-1", "quality_status": "review", "review_status": "pending"}]

    def get_report(self, run_id):
        return {
            "run_id": run_id,
            "document_id": "doc-1",
            "quality_status": "review",
            "review_status": "pending",
            "report": {
                "cer": 0.1,
                "field_accuracy": 0.8,
                "evidence_refs": ["vault://redacted/evidence"],
                "model_version": "v1",
            },
        }

    def record_correction(self, run_id, **kwargs):
        return 7


def _install_fake_kos(monkeypatch):
    class FakePage:
        def __init__(self, **kwargs):
            self.data = kwargs

    def assess(**kwargs):
        return FakeReport()

    fake_kems = types.ModuleType("kos.kems")
    fake_kems.OCRPageQuality = FakePage
    fake_kems.OCRQualityStore = FakeStore
    fake_kems.assess_ocr_quality = assess
    fake_kos = types.ModuleType("kos")
    fake_kos.kems = fake_kems
    monkeypatch.setitem(sys.modules, "kos", fake_kos)
    monkeypatch.setitem(sys.modules, "kos.kems", fake_kems)


def client():
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def test_ocr_report_routes_review_and_rejects_raw_content(monkeypatch):
    _install_fake_kos(monkeypatch)
    result = client().post(
        "/api/kems/ocr/reports",
        json={
            "run_id": "ocr-1",
            "document_id": "doc-1",
            "source_sha256": "a" * 64,
            "engine": "local-ocr",
            "model_version": "v1",
            "page_metrics": [{"page": 1, "text_confidence": 0.8, "layout_confidence": 0.8}],
        },
    )
    assert result.status_code == 200
    assert result.json()["review_required"] is True
    result = client().post(
        "/api/kems/ocr/reports",
        json={
            "run_id": "ocr-2",
            "document_id": "doc-2",
            "source_sha256": "b" * 64,
            "engine": "local-ocr",
            "model_version": "v1",
            "page_metrics": [{"page": 1, "text_confidence": 0.9, "layout_confidence": 0.9}],
            "ocr_text": "secret",
        },
    )
    assert result.status_code == 422


def test_ocr_queue_run_and_correction_endpoints(monkeypatch):
    _install_fake_kos(monkeypatch)
    queue = client().get("/api/kems/ocr/review-queue").json()
    assert queue["count"] == 1
    assert queue["items"][0]["source_ref"] == "doc-1"
    assert queue["items"][0]["review_status"] == "review"
    detail = client().get("/api/kems/ocr/runs/ocr-1").json()
    assert detail["admitted"] is False
    assert detail["metrics"]["field_accuracy"] == 0.8
    assert detail["evidence_ref"] == "vault://redacted/evidence"
    result = client().post(
        "/api/kems/ocr/runs/ocr-1/correction",
        json={
            "corrected_sha256": "c" * 64,
            "correction_ref": "vault://redacted/correction.json",
            "annotator": "reviewer-1",
        },
    )
    assert result.status_code == 200
    assert result.json()["correction_id"] == 7
