from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_work_cases
from cockpit.web.api_work_cases import router
from cockpit.web.router_health import ROUTER_MODULES


def test_work_cases_endpoint_returns_an_empty_projection_when_omo_has_no_cases(monkeypatch):
    monkeypatch.setattr(api_work_cases, "get_tasks_from_omo", lambda: [])
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get("/api/work-cases?scope=active")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_work_cases_router_is_registered_for_dashboard_loading():
    assert "cockpit.web.api_work_cases" in ROUTER_MODULES


def test_work_cases_endpoint_projects_only_omo_tasks_marked_as_cases(monkeypatch):
    monkeypatch.setattr(
        api_work_cases,
        "get_tasks_from_omo",
        lambda: [
            {
                "id": "TASK-CASE-1",
                "title": "数据调查",
                "status": "in_progress",
                "work_case": {
                    "status": "awaiting_confirmation",
                    "risk": "high",
                    "next_action": "确认发送批次",
                    "plan_confirmed": True,
                    "submissions": [
                        {"unit_id": "unit-a", "version": 1, "valid": True},
                        {"unit_id": "unit-a", "version": 2, "valid": True},
                        {"unit_id": "unit-b", "version": 1, "valid": False},
                    ],
                },
            },
            {"id": "TASK-OTHER", "title": "普通任务", "status": "in_progress"},
        ],
    )
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get("/api/work-cases?scope=active")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": "TASK-CASE-1",
            "title": "数据调查",
            "status": "awaiting_confirmation",
            "risk": "high",
            "next_action": "确认发送批次",
            "plan_confirmed": True,
            "valid_submission_count": 1,
            "submission_version_count": 3,
        }
    ]


def test_work_case_draft_endpoint_delegates_to_omo_ingress(monkeypatch):
    seen = {}

    def fake_draft(omo_dir, *, case_id, title, source_ref):
        seen.update(omo_dir=omo_dir, case_id=case_id, title=title, source_ref=source_ref)
        return {"id": case_id, "title": title, "work_case": {"status": "draft"}}

    monkeypatch.setattr(api_work_cases, "create_work_case_draft", fake_draft)
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/api/work-cases/drafts",
        json={"case_id": "CASE-001", "title": "数据调查", "source_ref": "oa://task-1"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert seen["source_ref"] == "oa://task-1"


def test_plan_request_endpoint_delegates_only_the_plan_digest(monkeypatch):
    seen = {}

    def fake_request(omo_dir, *, case_id, plan_digest):
        seen.update(omo_dir=omo_dir, case_id=case_id, plan_digest=plan_digest)
        return {"id": case_id}

    monkeypatch.setattr(api_work_cases, "request_work_case_plan_confirmation", fake_request)
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post("/api/work-cases/CASE-001/plan-requests", json={"plan_digest": "sha256:plan-v1"})

    assert response.status_code == 200
    assert response.json() == {"id": "CASE-001", "status": "awaiting_confirmation"}
    assert seen["plan_digest"] == "sha256:plan-v1"


def test_submission_endpoint_delegates_only_summary_fields(monkeypatch):
    seen = {}

    def fake_submission(omo_dir, *, case_id, unit_id, digest, valid):
        seen.update(omo_dir=omo_dir, case_id=case_id, unit_id=unit_id, digest=digest, valid=valid)
        return {"id": case_id}

    monkeypatch.setattr(api_work_cases, "record_work_case_submission", fake_submission)
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/api/work-cases/CASE-001/submissions",
        json={"unit_id": "unit-a", "digest": "sha256:reply-v1", "valid": True},
    )

    assert response.status_code == 200
    assert response.json() == {"id": "CASE-001", "status": "submission_recorded"}
    assert seen == {"omo_dir": api_work_cases.WORKSPACE_DIR / ".omo", "case_id": "CASE-001", "unit_id": "unit-a", "digest": "sha256:reply-v1", "valid": True}
