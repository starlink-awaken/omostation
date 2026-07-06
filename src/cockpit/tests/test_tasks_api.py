from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web.api_tasks import (
    get_capability_gap_task_drafts,
    get_domain_app_task_drafts,
    get_page_maturity_task_drafts,
    get_playbook_task_drafts,
    get_project_portfolio_task_drafts,
)


def test_playbook_task_drafts_are_read_only():
    drafts = get_playbook_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("playbook-") for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all(draft["draft"]["guard"] for draft in drafts)


def test_tasks_route_can_include_playbook_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("playbook-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_playbook_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("playbook-") for item in draft_resp.json()["items"])


def test_project_portfolio_task_drafts_are_read_only():
    drafts = get_project_portfolio_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("portfolio-") for draft in drafts)
    assert all(draft["source"]["type"] == "system_map_project_portfolio" for draft in drafts)
    assert all(draft["draft"]["kind"] == "project_portfolio_task" for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all("正式写入需走 C2G/OMO" in draft["draft"]["guard"] for draft in drafts)
    assert all(draft["draft"]["evidence_fields"] for draft in drafts)


def test_domain_app_task_drafts_are_read_only():
    drafts = get_domain_app_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("domain-app-") for draft in drafts)
    assert all(draft["source"]["type"] == "system_map_domain_app" for draft in drafts)
    assert all(draft["draft"]["kind"] == "domain_app_task" for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all("领域 app 自身认证/审计" in draft["draft"]["guard"] for draft in drafts)
    assert all(draft["draft"]["evidence_fields"] for draft in drafts)


def test_capability_gap_task_drafts_are_read_only():
    drafts = get_capability_gap_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("capability-gap-") for draft in drafts)
    assert all(draft["source"]["type"] == "system_map_capability_gap" for draft in drafts)
    assert all(draft["draft"]["kind"] == "capability_gap_task" for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all("正式写入需走 C2G/OMO" in draft["draft"]["guard"] for draft in drafts)
    assert all(draft["draft"]["evidence_fields"] for draft in drafts)


def test_page_maturity_task_drafts_are_read_only():
    drafts = get_page_maturity_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("page-maturity-") for draft in drafts)
    assert all(draft["source"]["type"] == "system_map_page_maturity" for draft in drafts)
    assert all(draft["draft"]["kind"] == "page_maturity_task" for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all("正式写入需走 C2G/OMO" in draft["draft"]["guard"] for draft in drafts)
    assert all(draft["draft"]["evidence_fields"] for draft in drafts)


def test_tasks_route_can_include_project_portfolio_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("portfolio-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_project_portfolio_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("portfolio-") for item in draft_resp.json()["items"])

    combined_resp = client.get("/api/tasks?include_playbook_drafts=true&include_project_portfolio_drafts=true")
    assert combined_resp.status_code == 200
    combined_items = combined_resp.json()["items"]
    assert any(item["id"].startswith("playbook-") for item in combined_items)
    assert any(item["id"].startswith("portfolio-") for item in combined_items)


def test_tasks_route_can_include_domain_app_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("domain-app-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_domain_app_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("domain-app-") for item in draft_resp.json()["items"])

    combined_resp = client.get(
        "/api/tasks?include_playbook_drafts=true&include_project_portfolio_drafts=true&include_domain_app_drafts=true"
    )
    assert combined_resp.status_code == 200
    combined_items = combined_resp.json()["items"]
    assert any(item["id"].startswith("playbook-") for item in combined_items)
    assert any(item["id"].startswith("portfolio-") for item in combined_items)
    assert any(item["id"].startswith("domain-app-") for item in combined_items)


def test_tasks_route_can_include_capability_gap_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("capability-gap-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_capability_gap_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("capability-gap-") for item in draft_resp.json()["items"])

    combined_resp = client.get(
        "/api/tasks?"
        "include_playbook_drafts=true&"
        "include_project_portfolio_drafts=true&"
        "include_domain_app_drafts=true&"
        "include_capability_gap_drafts=true"
    )
    assert combined_resp.status_code == 200
    combined_items = combined_resp.json()["items"]
    assert any(item["id"].startswith("playbook-") for item in combined_items)
    assert any(item["id"].startswith("portfolio-") for item in combined_items)
    assert any(item["id"].startswith("domain-app-") for item in combined_items)
    assert any(item["id"].startswith("capability-gap-") for item in combined_items)


def test_tasks_route_can_include_page_maturity_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("page-maturity-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_page_maturity_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("page-maturity-") for item in draft_resp.json()["items"])

    combined_resp = client.get(
        "/api/tasks?"
        "include_playbook_drafts=true&"
        "include_project_portfolio_drafts=true&"
        "include_domain_app_drafts=true&"
        "include_capability_gap_drafts=true&"
        "include_page_maturity_drafts=true"
    )
    assert combined_resp.status_code == 200
    combined_items = combined_resp.json()["items"]
    assert any(item["id"].startswith("playbook-") for item in combined_items)
    assert any(item["id"].startswith("portfolio-") for item in combined_items)
    assert any(item["id"].startswith("domain-app-") for item in combined_items)
    assert any(item["id"].startswith("capability-gap-") for item in combined_items)
    assert any(item["id"].startswith("page-maturity-") for item in combined_items)
