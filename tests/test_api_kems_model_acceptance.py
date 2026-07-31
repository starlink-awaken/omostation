from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client() -> TestClient:
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def cases() -> list[dict[str, object]]:
    return [
        {"case_id": "case-1", "predictions": [10, 12], "actual": [11, 13], "baseline_value": 8},
        {"case_id": "case-2", "predictions": [20, 19], "actual": [19, 18], "baseline_value": 16},
    ]


def test_model_acceptance_persists_and_can_be_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEMS_MODEL_ACCEPTANCE_DB", str(tmp_path / "model-acceptance.sqlite"))
    api = client()

    response = api.post(
        "/api/kems/models/candidates/candidate-v1/evaluation",
        json={"run_id": "model-run-1", "cases": cases(), "min_cases": 2},
    )
    assert response.status_code == 200
    assert response.json()["evaluation"]["status"] == "shadow_pass"
    assert response.json()["evaluation"]["promotion"] == "blocked_until_omo_approval"

    response = api.get("/api/kems/models/evaluations/model-run-1")
    assert response.status_code == 200
    assert response.json()["report"]["candidate_model_id"] == "candidate-v1"


def test_model_acceptance_rejects_raw_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEMS_MODEL_ACCEPTANCE_DB", str(tmp_path / "model-acceptance.sqlite"))
    response = client().post(
        "/api/kems/models/candidates/candidate-v1/evaluation",
        json={"run_id": "model-run-raw", "cases": cases() + [{"text": "private"}]},
    )
    assert response.status_code == 422
