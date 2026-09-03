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
        }
    ]
