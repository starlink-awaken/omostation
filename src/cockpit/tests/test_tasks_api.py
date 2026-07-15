from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_tasks
from cockpit.web.api_system_map import build_system_map
from cockpit.web.api_tasks import (
    get_capability_gap_task_drafts,
    get_domain_app_task_drafts,
    get_page_maturity_task_drafts,
    get_playbook_task_drafts,
    get_project_portfolio_task_drafts,
    get_verification_ready_task_drafts,
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


def test_verification_ready_task_drafts_are_read_only():
    drafts = get_verification_ready_task_drafts()

    assert drafts
    assert all(draft["read_only"] is True for draft in drafts)
    assert all(draft["id"].startswith("verification-ready-") for draft in drafts)
    assert all(draft["source"]["type"] == "system_map_verification_ready" for draft in drafts)
    assert all(draft["draft"]["kind"] == "verification_ready_task" for draft in drafts)
    assert all(draft["draft"]["copy_text"] for draft in drafts)
    assert all("agent-workflow / C2G / OMO" in draft["draft"]["guard"] for draft in drafts)
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
    attention_items = build_system_map()["page_maturity"]["attention_items"]

    assert bool(drafts) is bool(attention_items)
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


def test_tasks_route_can_include_verification_ready_drafts():
    client = TestClient(app)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("verification-ready-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_verification_ready_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("verification-ready-") for item in draft_resp.json()["items"])

    combined_resp = client.get(
        "/api/tasks?include_project_portfolio_drafts=true&include_verification_ready_drafts=true"
    )
    assert combined_resp.status_code == 200
    combined_items = combined_resp.json()["items"]
    assert any(item["id"].startswith("portfolio-") for item in combined_items)
    assert any(item["id"].startswith("verification-ready-") for item in combined_items)


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
    has_attention = bool(build_system_map()["page_maturity"]["attention_items"])

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200
    assert all(not item["id"].startswith("page-maturity-") for item in default_resp.json()["items"])

    draft_resp = client.get("/api/tasks?include_page_maturity_drafts=true")
    assert draft_resp.status_code == 200
    assert any(item["id"].startswith("page-maturity-") for item in draft_resp.json()["items"]) is has_attention

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
    assert any(item["id"].startswith("page-maturity-") for item in combined_items) is has_attention


def test_task_pause_uses_omo_ingress(monkeypatch):
    client = TestClient(app)
    calls = []

    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")

    def fake_revert(*args, **kwargs):
        calls.append((args, kwargs))
        return {"id": "task-1"}

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.revert_task_to_planned", fake_revert)

    response = client.post("/api/tasks/task-1/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert calls[0][1]["task_id"] == "task-1"


def test_task_cancel_does_not_fabricate_a_cancelled_state(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")

    response = client.post("/api/tasks/task-1/cancel")

    assert response.status_code == 409
    assert "no cancelled state" in response.json()["detail"]


def test_task_draft_promotes_through_omo_ingress(monkeypatch):
    client = TestClient(app)
    draft = {
        "id": "verification-ready-demo",
        "title": "验证补证：demo",
        "description": "把 demo 的验证命令沉成 workflow 证据。",
        "status": "pending",
        "priority": "high",
        "tags": ["verification-ready", "draft"],
        "read_only": True,
        "source": {"type": "system_map_verification_ready", "id": "demo", "source_refs": []},
        "draft": {"guard": "只读草稿；正式写入需走 OMO。"},
    }
    calls = []
    monkeypatch.setattr(api_tasks, "_get_task_draft", lambda _draft_id: draft)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: None)

    def fake_create(*args, **kwargs):
        calls.append((args, kwargs))
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)

    response = client.post("/api/tasks/drafts/verification-ready-demo/promote")

    assert response.status_code == 200
    assert response.json()["id"] == "cockpit-verification-ready-demo"
    assert response.json()["created"] is True
    assert calls[0][1]["ingress_plane"] == "cockpit-task-center"
    assert calls[0][1]["source_ref"] == "cockpit:draft:verification-ready-demo"
    assert calls[0][1]["task_data"]["status"] == "pending"


def test_task_draft_promotion_is_idempotent_for_planned_task(monkeypatch):
    client = TestClient(app)
    draft = {
        "id": "playbook-demo",
        "title": "操作清单：demo",
        "description": "执行 demo 操作清单。",
        "status": "pending",
        "priority": "medium",
        "tags": ["playbook", "draft"],
        "read_only": True,
        "source": {"type": "system_map_playbook", "id": "demo", "source_refs": []},
        "draft": {"guard": "只读草稿。"},
    }
    monkeypatch.setattr(api_tasks, "_get_task_draft", lambda _draft_id: draft)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "planned")
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.create_planned_task",
        lambda *args, **kwargs: kwargs["task_data"],
    )

    response = client.post("/api/tasks/drafts/playbook-demo/promote")

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["status"] == "pending"


def test_task_draft_promotion_rejects_unknown_draft(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(api_tasks, "_get_task_draft", lambda _draft_id: None)

    response = client.post("/api/tasks/drafts/missing/promote")

    assert response.status_code == 404


def test_task_history_reads_omo_trail_without_shadowing_it(tmp_path, monkeypatch):
    task_root = tmp_path / ".omo" / "tasks" / "planned"
    task_root.mkdir(parents=True)
    (task_root / "task-history.yaml").write_text(
        "id: task-history\nstatus: pending\nmetadata:\n  created_at: '2026-07-15T01:00:00Z'\n  ingress_plane: cockpit-task-center\n  source_ref: cockpit:draft:demo\n",
        encoding="utf-8",
    )
    trail_path = tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "ingress-trail.jsonl"
    trail_path.parent.mkdir(parents=True)
    trail_path.write_text(
        '{"action":"promote_task_to_active","actor":"cockpit-task-center","target":".omo/tasks/planned/task-history.yaml","status":"ok","ts":"2026-07-15T02:00:00Z"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_tasks, "WORKSPACE_DIR", tmp_path)
    client = TestClient(app)

    response = client.get("/api/tasks/task-history/history")

    assert response.status_code == 200
    assert response.json()["source"] == "omo-ingress"
    assert [item["action"] for item in response.json()["items"]] == [
        "created",
        "promote_task_to_active",
    ]


def test_task_history_rejects_non_persisted_draft():
    client = TestClient(app)

    response = client.get("/api/tasks/playbook-demo/history")

    assert response.status_code == 404


def test_queue_project_action_creates_approval_gated_planned_task(monkeypatch):
    client = TestClient(app)
    system_map = {
        "projects": [
            {
                "id": "demo",
                "name": "Demo",
                "source_refs": [],
                "actions": [
                    {
                        "id": "copy-start-command",
                        "label": "复制启动",
                        "kind": "copy_command",
                        "value": "cd demo && make start",
                        "enabled": True,
                        "risk": "medium",
                        "guard": "人工确认后执行。",
                    }
                ],
            }
        ]
    }
    calls = []
    monkeypatch.setattr(api_tasks, "build_system_map", lambda: system_map)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: None)

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)

    response = client.post("/api/cockpit/projects/demo/actions/copy-start-command/queue")

    assert response.status_code == 200
    assert response.json()["executes"] is False
    assert calls[0]["task_data"]["human_approval_required"] is True
    assert calls[0]["task_data"]["allowed_operation_level"] == "L2"
    assert calls[0]["source_ref"] == "cockpit:project-action:demo:copy-start-command"


def test_queue_project_action_rejects_non_command_action(monkeypatch):
    monkeypatch.setattr(
        api_tasks,
        "build_system_map",
        lambda: {"projects": [{"id": "demo", "actions": [{"id": "open", "kind": "navigate", "enabled": True}]}]},
    )
    client = TestClient(app)

    response = client.post("/api/cockpit/projects/demo/actions/open/queue")

    assert response.status_code == 409


def test_queue_domain_app_action_creates_auditable_approval_task(monkeypatch):
    client = TestClient(app)
    domain_apps = {
        "items": [
            {
                "id": "family-hub",
                "name": "家庭任务服务",
                "paths": {"app_root": {"path": "/tmp/family-hub"}},
                "actions": [
                    {
                        "id": "copy-start",
                        "label": "复制启动命令",
                        "kind": "copy_command",
                        "value": "cd /tmp/family-hub && bun run api",
                        "enabled": True,
                        "risk": "medium",
                        "guard": "人工确认后执行。",
                    }
                ],
            }
        ]
    }
    calls = []
    monkeypatch.setattr(api_tasks, "build_domain_apps", lambda: domain_apps)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: None)

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)

    response = client.post("/api/cockpit/domain-apps/family-hub/actions/copy-start/queue")

    assert response.status_code == 200
    assert response.json()["executes"] is False
    task_data = calls[0]["task_data"]
    assert task_data["human_approval_required"] is True
    assert "domain app audit" in task_data["evidence_required"]
    assert calls[0]["ingress_plane"] == "cockpit-domain-apps"
    assert calls[0]["source_ref"] == "cockpit:domain-app-action:family-hub:copy-start"


def test_task_list_exposes_execution_contract(monkeypatch, tmp_path):
    planned = tmp_path / ".omo" / "tasks" / "planned"
    planned.mkdir(parents=True)
    (planned / "contract-task.yaml").write_text(
        """id: contract-task
title: Contract task
status: pending
priority: medium
metadata:
  command: echo verify
  cockpit_only: true
risk_level: L2
allowed_operation_level: L2
human_approval_required: true
entry_gate:
  - confirm
evidence_required:
  - exit code
deliverables:
  - log
test_plan:
  - run safely
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_tasks, "WORKSPACE_DIR", tmp_path)

    response = TestClient(app).get("/api/tasks")

    assert response.status_code == 200
    task = next(item for item in response.json()["items"] if item["id"] == "contract-task")
    assert task["execution_contract"]["human_approval_required"] is True
    assert task["execution_contract"]["executes"] is False
    assert task["execution_contract"]["command"] == "echo verify"
