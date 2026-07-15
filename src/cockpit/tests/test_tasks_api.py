import pytest
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


def test_queue_project_triage_command_creates_non_executing_task(monkeypatch):
    client = TestClient(app)
    system_map = {
        "projects": [
            {
                "id": "demo",
                "name": "Demo",
                "triage_commands": [
                    {
                        "id": "verification-rerun",
                        "label": "复跑验证",
                        "kind": "copy_command",
                        "value": 'cd "/workspace/demo" && make verify',
                        "enabled": True,
                        "risk": "low",
                        "guard": "受控验证只在任务中心显式执行，并回写日志与退出码。",
                        "reason": "补最近一次验证证据。",
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

    response = client.post("/api/cockpit/projects/demo/triage/verification-rerun/queue")

    assert response.status_code == 200
    assert response.json()["executes"] is False
    assert calls[0]["task_data"]["human_approval_required"] is False
    assert calls[0]["task_data"]["metadata"]["controlled_execution"] is True
    assert calls[0]["task_data"]["metadata"]["action_id"] == "copy-verify-command"
    assert calls[0]["source_ref"] == "cockpit:project-triage:demo:verification-rerun"


def test_queue_runtime_port_probe_exposes_structured_controlled_execution(monkeypatch):
    system_map = {
        "projects": [
            {
                "id": "demo",
                "name": "Demo",
                "triage_commands": [
                    {
                        "id": "runtime-check-ports",
                        "label": "检查端口",
                        "kind": "copy_command",
                        "value": "for port in 7437 7438; do lsof -nP -iTCP:$port -sTCP:LISTEN || true; done",
                        "enabled": True,
                        "risk": "low",
                        "reason": "补运行探针证据",
                    }
                ],
            }
        ]
    }
    calls = []
    monkeypatch.setattr(api_tasks, "build_system_map", lambda: system_map)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: None)
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.create_planned_task",
        lambda *args, **kwargs: calls.append(kwargs) or kwargs["task_data"],
    )

    response = TestClient(app).post("/api/cockpit/projects/demo/triage/runtime-check-ports/queue")

    assert response.status_code == 200
    metadata = calls[0]["task_data"]["metadata"]
    assert metadata["controlled_execution"] is True
    assert metadata["action_id"] == "runtime-check-ports"
    assert metadata["probe_ports"] == [7437, 7438]


def test_queue_verification_triage_batches_only_matching_commands(monkeypatch):
    system_map = {
        "projects": [
            {
                "id": "demo-a",
                "triage_commands": [{"id": "verification-rerun", "category": "verification", "enabled": True}],
            },
            {
                "id": "demo-b",
                "triage_commands": [{"id": "verification-find-evidence", "category": "verification", "enabled": True}],
            },
        ]
    }
    calls = []

    async def fake_queue(project_id, command_id):
        calls.append((project_id, command_id))
        return {"id": f"cockpit-triage-{project_id}-{command_id}", "executes": False}

    monkeypatch.setattr(api_tasks, "build_system_map", lambda: system_map)
    monkeypatch.setattr(api_tasks, "queue_project_triage_command", fake_queue)

    response = TestClient(app).post("/api/cockpit/triage/queue", json={"project_ids": ["demo-a", "demo-b"]})

    assert response.status_code == 200
    assert response.json()["summary"] == {"queued": 1, "skipped": 0, "errors": 0}
    assert calls == [("demo-a", "verification-rerun")]
    assert response.json()["executes"] is False


def test_queue_runtime_triage_uses_probe_fallback_per_project(monkeypatch):
    system_map = {
        "projects": [
            {
                "id": "service-a",
                "triage_commands": [{"id": "runtime-check-ports", "category": "runtime", "enabled": True}],
            },
            {
                "id": "service-b",
                "triage_commands": [{"id": "runtime-find-registry", "category": "runtime", "enabled": True}],
            },
        ]
    }
    calls = []

    async def fake_queue(project_id, command_id):
        calls.append((project_id, command_id))
        return {"id": f"cockpit-triage-{project_id}-{command_id}", "executes": False}

    monkeypatch.setattr(api_tasks, "build_system_map", lambda: system_map)
    monkeypatch.setattr(api_tasks, "queue_project_triage_command", fake_queue)

    response = TestClient(app).post("/api/cockpit/triage/queue", json={"category": "runtime"})

    assert response.status_code == 200
    assert response.json()["summary"] == {"queued": 2, "skipped": 0, "errors": 0}
    assert calls == [
        ("service-a", "runtime-check-ports"),
        ("service-b", "runtime-find-registry"),
    ]
    assert response.json()["executes"] is False


def test_queue_coverage_drafts_promotes_selected_dimension(monkeypatch):
    drafts = [
        {"id": "capability-gap-demo", "title": "能力缺口：demo"},
        {"id": "capability-gap-other", "title": "能力缺口：other"},
    ]
    promoted = []

    async def fake_promote(draft_id):
        promoted.append(draft_id)
        return {"id": draft_id, "created": draft_id.endswith("demo"), "status": "pending"}

    monkeypatch.setitem(api_tasks._COVERAGE_DRAFT_GETTERS, "capability_gaps", lambda limit=8: drafts[:limit])
    monkeypatch.setattr(api_tasks, "promote_task_draft", fake_promote)

    response = TestClient(app).post(
        "/api/cockpit/coverage/queue",
        json={"category": "capability_gaps", "limit": 2},
    )

    assert response.status_code == 200
    assert response.json()["summary"] == {"queued": 1, "skipped": 1, "errors": 0, "considered": 2}
    assert response.json()["executes"] is False
    assert promoted == ["capability-gap-demo", "capability-gap-other"]


def test_queue_coverage_drafts_rejects_unknown_category():
    response = TestClient(app).post(
        "/api/cockpit/coverage/queue",
        json={"category": "unknown"},
    )

    assert response.status_code == 400


def test_queue_all_coverage_dimensions_does_not_starve_later_categories(monkeypatch):
    categories = list(api_tasks._COVERAGE_DRAFT_GETTERS)
    promoted = []

    for category in categories:
        monkeypatch.setitem(
            api_tasks._COVERAGE_DRAFT_GETTERS,
            category,
            lambda limit=8, category=category: [{"id": f"{category}-draft"}],
        )

    async def fake_promote(draft_id):
        promoted.append(draft_id)
        return {"id": draft_id, "created": True, "status": "pending"}

    monkeypatch.setattr(api_tasks, "promote_task_draft", fake_promote)

    response = TestClient(app).post(
        "/api/cockpit/coverage/queue",
        json={"category": "all", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "queued": len(categories),
        "skipped": 0,
        "errors": 0,
        "considered": len(categories),
    }
    assert set(promoted) == {f"{category}-draft" for category in categories}


def test_queue_engine_execution_creates_omo_task_without_launching(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)

    response = TestClient(app).post(
        "/api/cockpit/engine/queue",
        json={"engine": "pipeline", "pipeline": "health-check", "task": "核对运行状态"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["executes"] is False
    assert payload["engine"] == "pipeline"
    assert calls[0]["ingress_plane"] == "cockpit-engine"
    assert calls[0]["task_data"]["human_approval_required"] is True
    assert calls[0]["task_data"]["metadata"]["pipeline"] == "health-check"


def test_queue_governance_drift_fix_requires_approval(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)
    response = TestClient(app).post("/api/cockpit/governance/queue", json={"action": "fix-drift"})

    assert response.status_code == 200
    assert response.json()["executes"] is False
    assert calls[0]["task_data"]["risk_level"] == "L3"
    assert calls[0]["task_data"]["human_approval_required"] is True
    assert calls[0]["task_data"]["metadata"]["governance_action"] == "fix-drift"


def test_queue_compute_wakeup_requires_approval(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)
    response = TestClient(app).post(
        "/api/cockpit/compute/queue",
        json={"operation": "wakeup", "node_id": "ENG-OLLAMA-MACMINI"},
    )

    assert response.status_code == 200
    assert response.json()["executes"] is False
    assert calls[0]["task_data"]["human_approval_required"] is True
    assert calls[0]["task_data"]["metadata"]["node_id"] == "ENG-OLLAMA-MACMINI"


@pytest.mark.parametrize(
    ("payload", "metadata_key", "metadata_value"),
    [
        ({"operation": "circuit_break", "broken": True}, "broken", True),
        ({"operation": "budget", "budget": 250}, "budget", 250),
    ],
)
def test_queue_compute_control_requires_approval(monkeypatch, payload, metadata_key, metadata_value):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)
    response = TestClient(app).post("/api/cockpit/compute/control/queue", json=payload)

    assert response.status_code == 200
    assert response.json()["executes"] is False
    task_data = calls[0]["task_data"]
    assert task_data["human_approval_required"] is True
    assert task_data["metadata"][metadata_key] == metadata_value
    assert task_data["metadata"]["compute_operation"] == payload["operation"]


def test_queue_sandbox_result_persists_follow_up_task(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)
    response = TestClient(app).post(
        "/api/cockpit/sandbox/queue",
        json={"code": "print('ok')", "output": "[执行成功] ok", "title": "沙箱结果验收"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executes"] is False
    task_data = calls[0]["task_data"]
    assert task_data["human_approval_required"] is False
    assert task_data["metadata"]["sandbox_result_digest"] == payload["result_digest"]
    assert task_data["metadata"]["output_excerpt"] == "[执行成功] ok"
    assert calls[0]["ingress_plane"] == "cockpit-sandbox"


def test_queue_compute_generation_result_persists_follow_up_task(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["task_data"]

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.create_planned_task", fake_create)
    response = TestClient(app).post(
        "/api/cockpit/compute/generation/queue",
        json={"prompt": "总结架构", "model": "coder", "content": "架构分为四层。"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executes"] is False
    task_data = calls[0]["task_data"]
    assert task_data["metadata"]["compute_operation"] == "generation_result"
    assert task_data["metadata"]["model"] == "coder"
    assert task_data["metadata"]["content_excerpt"] == "架构分为四层。"
    assert calls[0]["ingress_plane"] == "cockpit-compute"


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


def test_request_task_approval_uses_omo_brokers(monkeypatch):
    client = TestClient(app)
    payload = {
        "id": "approval-task",
        "status": "pending",
        "human_approval_required": True,
        "allowed_operation_level": "L2",
        "risk_level": "L2",
        "approval_ref": None,
    }
    calls = []
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "planned")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload.copy())
    monkeypatch.setattr(
        "omo.omo_governance.propose_truth_mutation",
        lambda *args, **kwargs: {"id": "approval-proposal"},
    )

    def fake_request(*args, **kwargs):
        calls.append(kwargs)
        return {**payload, "approval_ref": kwargs["approval_ref"]}

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.request_task_promotion_approval", fake_request)

    response = client.post("/api/tasks/approval-task/request-approval")

    assert response.status_code == 200
    assert response.json()["created"] is True
    assert response.json()["proposal_id"].endswith("-proposal")
    assert calls[0]["actor"] == "cockpit-task-center"


def test_approve_task_applies_governed_approval(monkeypatch):
    client = TestClient(app)
    approval_ref = ".omo/workers/runs/approval-task-promotion-approval-2026-07-15T00-00-00Z.yaml"
    payload = {
        "id": "approval-task",
        "status": "pending",
        "human_approval_required": True,
        "approval_ref": approval_ref,
    }
    calls = []
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "planned")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)
    monkeypatch.setattr(
        "omo.omo_governance.approve_truth_mutation",
        lambda *args, **kwargs: calls.append(("approve", args, kwargs)) or {"status": "approved"},
    )
    monkeypatch.setattr(
        "omo.omo_governance.apply_truth_mutation",
        lambda *args, **kwargs: calls.append(("apply", args, kwargs)) or {"status": "verified"},
    )

    response = client.post("/api/tasks/approval-task/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "granted"
    assert [call[0] for call in calls] == ["approve", "apply"]


def test_resume_rejects_unapproved_human_gate(monkeypatch):
    client = TestClient(app)
    payload = {"id": "approval-task", "status": "pending", "human_approval_required": True, "approval_ref": None}
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "planned")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)

    response = client.post("/api/tasks/approval-task/resume")

    assert response.status_code == 409
    assert "request and grant approval" in response.json()["detail"]


def test_dispatch_creates_worker_run_without_launching(monkeypatch):
    client = TestClient(app)
    payload = {
        "id": "dispatch-task",
        "status": "pending",
        "human_approval_required": False,
        "deliverables": ["projects/demo/"],
        "evidence_required": ["worker log"],
    }
    calls = []
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)
    monkeypatch.setattr("omo.omo_worker_core._default_enabled_worker_id", lambda _registry: "coder")
    monkeypatch.setattr("omo.omo_worker_core._dispatch_allowed_write_paths", lambda _task: ["projects/demo/"])

    def fake_dispatch(*args, **kwargs):
        calls.append((args, kwargs))
        return {"dispatch_id": "dispatch-task-coder-now", "dispatch_path": ".omo/workers/runs/dispatch-task.yaml"}

    monkeypatch.setattr("omo.omo_worker_dispatch.dispatch_task", fake_dispatch)

    response = client.post("/api/tasks/dispatch-task/dispatch")

    assert response.status_code == 200
    assert response.json()["launched"] is False
    assert calls[0][1]["launch"] is False
    assert calls[0][1]["transport"] == "cli_prompt"


def test_dispatch_rejects_unapproved_active_task(monkeypatch):
    client = TestClient(app)
    payload = {"id": "dispatch-task", "status": "pending", "human_approval_required": True, "approval_ref": None}
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)

    response = client.post("/api/tasks/dispatch-task/dispatch")

    assert response.status_code == 409
    assert "approval must be granted" in response.json()["detail"]


def test_controlled_execute_routes_project_verification_through_omo(monkeypatch):
    client = TestClient(app)
    payload = {
        "id": "verify-task",
        "status": "in_progress",
        "human_approval_required": False,
        "metadata": {
            "controlled_execution": True,
            "command": 'cd "/workspace/projects/demo" && printf hello',
        },
    }
    calls = []
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)

    def fake_execute(*args, **kwargs):
        calls.append(kwargs)
        return {
            "execution_ref": ".omo/_delivery/task-center/execution/verify-task.yaml",
            "exit_code": 0,
            "log_ref": "runtime/omo/verify-task.log",
            "timed_out": False,
        }

    monkeypatch.setattr("omo.omo_ingress_task_lifecycle.execute_controlled_task", fake_execute)

    response = client.post("/api/tasks/verify-task/execute")

    assert response.status_code == 200
    assert response.json()["exit_code"] == 0
    assert calls[0]["task_id"] == "verify-task"
    assert calls[0]["source_ref"] == "cockpit:task:execute:verify-task"


def test_execution_endpoint_reports_worker_artifacts(monkeypatch, tmp_path):
    run_dir = tmp_path / ".omo" / "workers" / "runs"
    run_dir.mkdir(parents=True)
    dispatch_ref = ".omo/workers/runs/dispatch-task.yaml"
    (tmp_path / dispatch_ref).write_text(
        """dispatch_id: dispatch-task
dispatch_state: checkpointed
worker_id: coder
inputs:
  envelope_file: .omo/workers/runs/dispatch-task-envelope.yaml
  prompt_file: .omo/workers/runs/dispatch-task-prompt.md
execution:
  checkpoint_refs:
    - .omo/workers/runs/dispatch-task-checkpoint.md
  log_ref: .omo/workers/runs/dispatch-task-stdout.log
handoff:
  output_summary_ref: .omo/workers/runs/dispatch-task-review.md
reclaim:
  note_ref: .omo/workers/runs/dispatch-task-reclaim.md
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/workers/runs/dispatch-task-checkpoint.md").write_text("checkpoint", encoding="utf-8")
    payload = {"id": "dispatch-task", "status": "in_progress", "run_ref": dispatch_ref, "dispatch_id": "dispatch-task"}
    monkeypatch.setattr(api_tasks, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)

    response = TestClient(app).get("/api/tasks/dispatch-task/execution")

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "checkpointed"
    assert execution["artifacts"]["checkpoint"]["exists"] is True
    assert execution["artifacts"]["review"]["exists"] is False


def test_complete_passes_existing_evidence_to_omo(monkeypatch, tmp_path):
    evidence = tmp_path / "evidence.md"
    evidence.write_text("verified", encoding="utf-8")
    payload = {"id": "evidence-task", "status": "in_progress"}
    calls = []
    monkeypatch.setattr(api_tasks, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(api_tasks, "_task_group", lambda _task_id: "active")
    monkeypatch.setattr(api_tasks, "_load_persisted_task", lambda _task_id, _group: payload)
    monkeypatch.setattr(
        "omo.omo_ingress_task_lifecycle.complete_task",
        lambda *args, **kwargs: calls.append(kwargs) or {"completed_at": "now"},
    )

    response = TestClient(app).post(
        "/api/tasks/evidence-task/complete",
        json={"evidence_paths": ["evidence.md"]},
    )

    assert response.status_code == 200
    assert calls[0]["evidence_paths"] == ["evidence.md"]


def test_complete_rejects_missing_evidence_file(monkeypatch, tmp_path):
    monkeypatch.setattr(api_tasks, "WORKSPACE_DIR", tmp_path)
    response = TestClient(app).post(
        "/api/tasks/evidence-task/complete",
        json={"evidence_paths": ["missing.md"]},
    )
    assert response.status_code == 422
