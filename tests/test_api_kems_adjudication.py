from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client() -> TestClient:
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def item() -> dict[str, object]:
    return {
        "sample_id": "sample-1",
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": "pending",
    }


def test_adjudication_lifecycle_and_manifest(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEMS_ADJUDICATION_DB", str(tmp_path / "adjudication.sqlite"))
    monkeypatch.setenv("KEMS_EVALUATION_DB", str(tmp_path / "evaluation.sqlite"))
    api = client()

    assert api.post("/api/kems/adjudication/queue", json={"items": [item()]}).status_code == 200
    assert api.get("/api/kems/adjudication/queue?status=pending").json()["count"] == 1
    assert api.post("/api/kems/adjudication/sample-1/claim", json={"annotator": "reviewer-1"}).status_code == 200
    response = api.post(
        "/api/kems/adjudication/sample-1/adjudicate",
        json={"labels": {"category": "notice"}, "annotation_version": "ann-1", "annotator": "reviewer-1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "adjudicated"

    response = api.post("/api/kems/adjudication/manifest", json={"dataset_id": "kems-real", "dataset_version": "v1"})
    assert response.status_code == 200
    assert response.json()["sample_count"] == 1


def test_adjudication_api_rejects_raw_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEMS_ADJUDICATION_DB", str(tmp_path / "adjudication.sqlite"))
    response = client().post("/api/kems/adjudication/queue", json={"items": [item() | {"text": "private"}]})
    assert response.status_code == 422
