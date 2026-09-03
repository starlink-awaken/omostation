from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web.api_work_cases import router
from cockpit.web.router_health import ROUTER_MODULES


def test_work_cases_endpoint_reports_unavailable_without_an_omo_projection():
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get("/api/work-cases?scope=active")

    assert response.status_code == 503
    assert response.json()["detail"] == "work-case projection is unavailable"


def test_work_cases_router_is_registered_for_dashboard_loading():
    assert "cockpit.web.api_work_cases" in ROUTER_MODULES
