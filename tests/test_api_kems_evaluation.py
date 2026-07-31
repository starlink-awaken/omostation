from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client():
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def sample(**overrides):
    value = {
        "sample_id": "sample-1",
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": "adjudicated",
        "labels": {"category": "notice"},
        "annotation_version": "ann-1",
    }
    value.update(overrides)
    return value


def test_registers_redaction_verified_adjudicated_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("KEMS_EVALUATION_DB", str(tmp_path / "evaluation.sqlite"))
    result = client().post(
        "/api/kems/evaluations/manifests",
        json={"dataset_id": "kems-real", "dataset_version": "2026-07-31", "samples": [sample()]},
    )
    assert result.status_code == 200
    assert result.json()["sample_count"] == 1
    assert result.json()["redaction_status"] == "verified"


def test_rejects_unadjudicated_or_raw_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("KEMS_EVALUATION_DB", str(tmp_path / "evaluation.sqlite"))
    response = client().post(
        "/api/kems/evaluations/manifests",
        json={"dataset_id": "kems-real", "dataset_version": "v1", "samples": [sample(annotation_status="reviewed")]},
    )
    assert response.status_code == 422
    response = client().post(
        "/api/kems/evaluations/manifests",
        json={"dataset_id": "kems-real", "dataset_version": "v1", "samples": [sample(text="private")]},
    )
    assert response.status_code == 422


def test_records_and_reads_evaluation_run(monkeypatch, tmp_path):
    monkeypatch.setenv("KEMS_EVALUATION_DB", str(tmp_path / "evaluation.sqlite"))
    assert (
        client()
        .post(
            "/api/kems/evaluations/manifests",
            json={"dataset_id": "kems-real", "dataset_version": "v1", "samples": [sample()]},
        )
        .status_code
        == 200
    )
    result = client().post(
        "/api/kems/evaluations/runs/run-1",
        json={
            "dataset_id": "kems-real",
            "dataset_version": "v1",
            "model_id": "baseline-exact",
            "expected": {"category": "notice"},
            "actual": {"category": "notice"},
        },
    )
    assert result.status_code == 200
    assert result.json()["evaluation"]["accuracy"] == 1.0
    assert client().get("/api/kems/evaluations/runs/run-1").json()["model_id"] == "baseline-exact"
