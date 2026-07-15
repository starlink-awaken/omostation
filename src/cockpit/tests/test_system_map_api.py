import json
from pathlib import Path

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web import api_system_map
from cockpit.web.api_system_map import build_source_ref_preview, build_system_map


def _seed_workflow_events(workspace_root: Path) -> Path:
    """Create a minimal agent-workflow events.jsonl so cockpit has workflow runs."""
    events_dir = workspace_root / ".omo" / "_delivery" / "agent-workflows"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / "events.jsonl"
    events = [
        {
            "event": "agent_workflow_start",
            "run_id": "cockpit-run-1",
            "workflow_id": "cockpit-docs",
            "objective": "test",
            "ts": "2024-01-01T00:00:00Z",
        },
        {
            "event": "agent_workflow_claim",
            "run_id": "cockpit-run-1",
            "paths": ["projects/cockpit"],
            "ts": "2024-01-01T00:00:01Z",
        },
        {
            "event": "agent_workflow_verify",
            "run_id": "cockpit-run-1",
            "changed_files": ["projects/cockpit/README.md"],
            "ok": True,
            "checks": ["check-1"],
            "ts": "2024-01-01T00:00:02Z",
        },
        {
            "event": "agent_workflow_closeout",
            "run_id": "cockpit-run-1",
            "ok": True,
            "status": "closed",
            "ts": "2024-01-01T00:00:03Z",
        },
    ]
    events_path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
    return events_path


def test_system_map_builds_workspace_dimensions():
    workspace_root = Path(__file__).resolve().parents[4]
    events_path = _seed_workflow_events(workspace_root)
    try:
        payload = build_system_map()
    finally:
        events_path.unlink(missing_ok=True)

    assert payload["schema_version"] == "v1"
    assert payload["architecture"]["model"] == "5+4+1+1"
    assert payload["summary"]["projects"] >= 1
    assert payload["summary"]["layers"] >= 1
    assert payload["summary"]["feature_domains"] >= 1
    assert payload["source_paths"]["project_registry"]["exists"] is True
    assert any(page["id"] == "SystemMap" for page in payload["cockpit_pages"])
    assert any(page["id"] == "Guide" for page in payload["cockpit_pages"])
    # domain-app-write-gates is a legitimate dynamic gap when domain-apps are
    # unavailable or have security issues; assert gap shape instead of absence.
    assert all(gap.get("id") and gap.get("severity") for gap in payload["gaps"])
    assert any(layer["id"] == "L3" for layer in payload["layers"])
    assert any(project["id"] == "cockpit" for project in payload["projects"])
    assert any(domain["title"] == "治理与合规" for domain in payload["feature_domains"])
    assert any(path["id"] == "governance-loop" for path in payload["usage_paths"])
    assert payload["summary"]["roadmap_items"] >= 1
    assert payload["summary"]["ready_projects"] >= 1
    assert "partial_projects" in payload["summary"]
    assert "running_projects" in payload["summary"]
    assert payload["summary"]["playbooks"] >= 1
    assert payload["summary"]["source_refs"] >= 1
    assert payload["summary"]["project_actions"] >= 1
    assert "projects_needing_action" in payload["summary"]
    assert payload["summary"]["project_triage_commands"] >= 1
    assert "project_coverage_score" in payload["summary"]
    assert payload["summary"]["project_portfolio_score"] == payload["summary"]["project_coverage_score"]
    assert "blocked_projects" in payload["summary"]
    assert "at_risk_projects" in payload["summary"]
    assert payload["summary"]["domain_apps"] >= 3
    assert "domain_app_score" in payload["summary"]
    assert "domain_app_security_attention" in payload["summary"]
    domain_apps = payload["domain_apps"]
    assert domain_apps["summary"]["total"] == payload["summary"]["domain_apps"]
    assert domain_apps["summary"]["score"] == payload["summary"]["domain_app_score"]
    assert domain_apps["summary"]["security_posture"] in {"passed", "attention", "blocked"}
    assert domain_apps["status"] in {"ready", "watch", "attention", "blocked", "unavailable"}
    assert domain_apps["items"]
    family_app = next(item for item in domain_apps["items"] if item["id"] == "family-dashboard-app")
    assert family_app["integration_mode"] == "external_mount"
    assert family_app["security_posture"] in {"passed", "attention", "blocked"}
    assert family_app["next_action"]
    assert "attention_items" in domain_apps
    assert domain_apps["next_action"]
    assert payload["summary"]["page_maturity_ready"] >= 1
    assert "page_maturity_score" in payload["summary"]
    assert payload["summary"]["page_maturity_gap"] >= 0
    assert payload["summary"]["page_maturity_watch"] >= 0
    page_maturity = payload["page_maturity"]
    assert page_maturity["summary"]["total"] == payload["summary"]["cockpit_pages"]
    assert page_maturity["summary"]["score"] == payload["summary"]["page_maturity_score"]
    assert (
        page_maturity["summary"]["ready"] + page_maturity["summary"]["watch"] + page_maturity["summary"]["gap"]
        == page_maturity["summary"]["total"]
    )
    assert all(item["status"] in {"ready", "gap", "watch"} for item in page_maturity["items"])
    assert all(item["next_action"] for item in page_maturity["items"])
    assert all(item["domains"] for item in page_maturity["items"])
    assert any(item["page_id"] == "SystemMap" for item in page_maturity["items"])
    maturity_by_page = {item["page_id"]: item for item in page_maturity["items"]}
    assert "runtime" in maturity_by_page["Home"]["projects"]
    assert "ecos" in maturity_by_page["Protocol"]["projects"]
    assert "observability" in maturity_by_page["Topology"]["projects"]
    assert "family-hub" in maturity_by_page["QuestBoard"]["projects"]
    assert "compute-routing" in maturity_by_page["Compute"]["usage_paths"]
    assert payload["project_focus"]["summary"]["needs_action"] >= 1
    needs_action_queue = next(queue for queue in payload["project_focus"]["queues"] if queue["id"] == "needs-action")
    assert needs_action_queue["top_projects"]
    assert needs_action_queue["top_projects"][0]["diagnostics"]
    coverage = payload["project_capability_coverage"]
    assert coverage["summary"]["dimensions"] >= 8
    assert coverage["summary"]["total_cells"] == coverage["summary"]["projects"] * coverage["summary"]["dimensions"]
    assert coverage["summary"]["ready_cells"] >= 1
    assert coverage["dimension_summary"]
    assert any(item["id"] == "verification" for item in coverage["dimension_summary"])
    assert coverage["weakest_dimensions"]
    assert coverage["matrix"]
    portfolio = payload["project_portfolio"]
    assert portfolio["summary"]["projects"] == payload["summary"]["projects"]
    assert portfolio["summary"]["score"] == coverage["summary"]["score"]
    assert {bucket["id"] for bucket in portfolio["buckets"]} == {"blocked", "at_risk", "watch", "healthy"}
    assert portfolio["priority_projects"]
    assert all(project["id"] for project in portfolio["priority_projects"])
    assert all(project["next_action"] for project in portfolio["priority_projects"])
    assert all(
        project["status"] in {"blocked", "at_risk", "watch", "healthy"} for project in portfolio["priority_projects"]
    )
    assert portfolio["weakest_dimensions"] == coverage["weakest_dimensions"]
    assert any(queue["id"] == "verification-gap" for queue in payload["project_focus"]["queues"])
    triage = payload["project_triage"]
    assert triage["summary"]["total_commands"] >= 1
    assert triage["summary"]["verification_commands"] >= 1
    assert {queue["id"] for queue in triage["queues"]} == {"runtime", "verification", "coverage"}
    assert any(queue["commands"] for queue in triage["queues"])
    assert all(command["executes"] is False for queue in triage["queues"] for command in queue["commands"])
    assert all(command["guard"] for queue in triage["queues"] for command in queue["commands"])
    assert all(command["project_id"] for queue in triage["queues"] for command in queue["commands"])
    assert all(gap["id"] != "system-map-first-mile" for gap in payload["gaps"])
    assert payload["roadmap"]["summary"]["p0"] >= 1
    global_search = next(item for item in payload["roadmap"]["items"] if item["id"] == "global-search-routing")
    assert global_search["status"] == "shipped"
    domain_actions = next(item for item in payload["roadmap"]["items"] if item["id"] == "domain-app-health-actions")
    assert domain_actions["status"] == "shipped"
    project_status = next(item for item in payload["roadmap"]["items"] if item["id"] == "project-native-status")
    assert project_status["status"] == "shipped"
    runtime_probes = next(item for item in payload["roadmap"]["items"] if item["id"] == "project-runtime-probes")
    assert runtime_probes["status"] == "shipped"
    runtime_actions = next(item for item in payload["roadmap"]["items"] if item["id"] == "project-runtime-actions")
    assert runtime_actions["status"] == "shipped"
    ssot_links = next(item for item in payload["roadmap"]["items"] if item["id"] == "ssot-deep-links")
    assert ssot_links["status"] == "shipped"
    assert ssot_links["source_refs"][0]["line"]
    source_preview = next(item for item in payload["roadmap"]["items"] if item["id"] == "source-open-actions")
    assert source_preview["status"] == "shipped"
    assert all(gap["id"] != "source-link-depth" for gap in payload["gaps"])
    guided_ops = next(item for item in payload["roadmap"]["items"] if item["id"] == "guided-ops-checklists")
    assert guided_ops["status"] == "shipped"
    playbook_persistence = next(
        item for item in payload["roadmap"]["items"] if item["id"] == "playbook-evidence-persistence"
    )
    assert playbook_persistence["status"] == "shipped"
    assert all(item["acceptance"] for item in payload["roadmap"]["items"])
    daily_playbook = next(item for item in payload["playbooks"] if item["id"] == "daily-health-check")
    assert daily_playbook["frequency"] == "daily"
    assert daily_playbook["steps"]
    assert all(step["page"]["id"] == step["page_id"] for step in daily_playbook["steps"])
    assert all(step["action"] and step["evidence"] and step["done_when"] for step in daily_playbook["steps"])
    cockpit_project = next(project for project in payload["projects"] if project["id"] == "cockpit")
    assert cockpit_project["operational"]["docs"]["present"] >= 1
    assert cockpit_project["operational"]["commands"]
    mesh_router = next(project for project in payload["projects"] if project["id"] == "mesh-router")
    assert mesh_router["operational"]["surface_type"] == "implemented-in-bin"
    assert mesh_router["operational"]["status"] == "ready"
    metaos_project = next(project for project in payload["projects"] if project["id"] == "metaos")
    assert any("pytest" in command for command in metaos_project["operational"]["commands"])
    toolbox_project = next(project for project in payload["projects"] if project["id"] == "toolbox")
    assert toolbox_project["operational"]["surface_type"] == "external-storage"
    toolbox_docs = next(check for check in toolbox_project["coverage_checks"] if check["id"] == "project_docs")
    assert toolbox_docs["status"] == "ready"
    assert cockpit_project["operational"]["next_action"]
    assert cockpit_project["source_refs"]
    assert cockpit_project["source_refs"][0]["source_key"] == "project_registry"
    assert cockpit_project["source_refs"][0]["line"]
    assert cockpit_project["actions"]
    assert "triage_commands" in cockpit_project
    assert cockpit_project["workflow"]["summary"]["runs"] >= 1
    assert cockpit_project["portfolio"]["score"] >= 0
    assert cockpit_project["portfolio"]["status"] in {"blocked", "at_risk", "watch", "healthy"}
    assert cockpit_project["portfolio"]["next_action"]
    assert cockpit_project["workflow"]["latest_run_id"]
    assert cockpit_project["workflow"]["runs"]
    assert cockpit_project["workflow"]["runs"][0]["events"]
    assert any(
        event["type"] in {"claim", "verify", "closeout"}
        for run in cockpit_project["workflow"]["runs"]
        for event in run["events"]
    )
    assert cockpit_project["diagnostics"]
    assert all(item["next_action"] for item in cockpit_project["diagnostics"])
    assert cockpit_project["coverage_checks"]
    assert {check["id"] for check in cockpit_project["coverage_checks"]} >= {
        "cockpit_surface",
        "project_docs",
        "commands",
        "manifest",
        "runtime_probe",
        "verification",
        "source_refs",
        "operator_actions",
    }
    assert all(check["next_action"] for check in cockpit_project["coverage_checks"])
    assert any(action["id"] == "copy-project-path" for action in cockpit_project["actions"])
    assert any(action["id"] == "copy-verify-command" for action in cockpit_project["actions"])
    assert all(action["executes"] is False for action in cockpit_project["actions"])
    assert all(action["guard"] for action in cockpit_project["actions"])
    assert any(port["port"] == 8090 for port in cockpit_project["runtime"]["ports"])
    cockpit_port = next(port for port in cockpit_project["runtime"]["ports"] if port["port"] == 8090)
    assert cockpit_port["source_ref"]["source_key"] == "port_registry"
    assert cockpit_port["source_ref"]["line"]
    assert cockpit_project["runtime"]["profile"] in {"service", "library", "cli", "static", "unknown"}
    assert isinstance(cockpit_project["runtime"]["needs_runtime"], bool)
    assert cockpit_project["runtime"]["probe_reason"]
    assert cockpit_project["runtime"]["latest_verification"]["status"] in {
        "verified",
        "failed",
        "documented",
        "unknown",
    }
    assert "not_applicable_projects" in payload["summary"]
    assert "verification_ready" in payload["project_focus"]["summary"]
    governance_domain = next(domain for domain in payload["feature_domains"] if domain["title"] == "治理与合规")
    assert governance_domain["source_refs"][0]["source_key"] == "functional_capability_map"
    assert governance_domain["source_refs"][0]["line"]


def test_system_map_route_is_mounted():
    client = TestClient(app)

    resp = client.get("/api/cockpit/system-map")

    assert resp.status_code == 200
    assert resp.json()["schema_version"] == "v1"


def test_source_ref_preview_reads_workspace_context():
    payload = build_system_map()
    ref = payload["projects"][0]["source_refs"][0]

    preview = build_source_ref_preview(target=ref["target"], context=1)

    assert preview["workspace_relative_path"]
    assert preview["line"] == ref["line"]
    assert preview["lines"]
    assert any(line["highlight"] for line in preview["lines"])
    assert "不执行本机打开命令" in preview["guard"]


def test_source_ref_preview_route_rejects_external_paths():
    client = TestClient(app)

    resp = client.get("/api/cockpit/source-ref", params={"target": "/etc/hosts:1"})

    assert resp.status_code == 403


def test_source_ref_preview_route_is_mounted():
    payload = build_system_map()
    ref = payload["projects"][0]["source_refs"][0]
    client = TestClient(app)

    resp = client.get("/api/cockpit/source-ref", params={"target": ref["target"], "context": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["target"] == ref["target"]
    assert any(line["highlight"] for line in body["lines"])


def test_runtime_status_marks_static_frontend_as_not_applicable(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "cockpit-ui"
    (project_path / "src").mkdir(parents=True, exist_ok=True)
    (project_path / "AGENTS.md").write_text("## Commands\n```bash\nbun run dev\nbun run build\n```\n", encoding="utf-8")
    (project_path / "README.md").write_text("# cockpit-ui\n", encoding="utf-8")
    (project_path / "CLAUDE.md").write_text("# cockpit-ui\n", encoding="utf-8")
    (project_path / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite", "build": "vite build"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (project_path / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    (project_path / "src" / "main.tsx").write_text("console.log('cockpit-ui')\n", encoding="utf-8")
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(
        api_system_map,
        "_latest_project_verification",
        lambda _project_id, _project_path, _operational: {
            "status": "unknown",
            "run_id": None,
            "ts": None,
            "checks": 0,
            "command": None,
            "source": "missing",
        },
    )

    operational = api_system_map._project_operational_status("cockpit-ui")
    runtime = api_system_map._project_runtime_status(
        "cockpit-ui",
        {"role": "Web 控制台 UI", "stack": "TypeScript (Vite, React)"},
        operational,
        {"ports": {}, "types": {}},
        workspace_root / "protocols" / "port-registry.yaml",
    )

    assert runtime["status"] == "not_applicable"
    assert runtime["profile"] == "static"
    assert runtime["needs_runtime"] is False
    assert "静态前端" in runtime["probe_reason"]

    checks = api_system_map._project_coverage_checks(
        {
            "id": "cockpit-ui",
            "coverage": "native",
            "cockpit_page": "SystemMap",
            "operational": operational,
            "runtime": runtime,
            "source_refs": [{"exists": True}],
            "actions": [{"id": "copy-project-path"}],
        }
    )
    runtime_check = next(check for check in checks if check["id"] == "runtime_probe")
    assert runtime_check["status"] == "ready"
    assert "形态：static" in runtime_check["detail"]


def test_runtime_status_does_not_probe_stdio_ports_as_tcp(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "ToolBox"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "CLAUDE.md").write_text("# toolbox\n", encoding="utf-8")
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(
        api_system_map,
        "_latest_project_verification",
        lambda _project_id, _project_path, _operational: {
            "status": "unknown",
            "run_id": None,
            "ts": None,
            "checks": 0,
            "command": None,
            "source": "missing",
        },
    )

    operational = api_system_map._project_operational_status("toolbox", {"storage": str(project_path)})
    runtime = api_system_map._project_runtime_status(
        "toolbox",
        {"role": "本地工具集合", "stack": "MCP / Skill / CLI"},
        operational,
        {
            "ports": {
                18801: {"name": "wps-office-mcp-stdio", "transport": "stdio"},
                18802: {"name": "wps-skills-stdio", "transport": "stdio"},
            },
            "types": {},
        },
        workspace_root / "protocols" / "port-registry.yaml",
    )

    assert runtime["status"] == "not_applicable"
    assert runtime["profile"] == "stdio"
    assert runtime["needs_runtime"] is False
    assert all(port["probeable"] is False and port["listening"] is None for port in runtime["ports"])
    assert "stdio" in runtime["probe_reason"]


def test_runtime_status_keeps_service_projects_unobserved_without_port_registry(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "family-hub"
    (project_path / "api").mkdir(parents=True, exist_ok=True)
    (project_path / "AGENTS.md").write_text("## Commands\n```bash\nbun run dev\nbun run lint\n```\n", encoding="utf-8")
    (project_path / "README.md").write_text("# family-hub\n", encoding="utf-8")
    (project_path / "package.json").write_text(
        json.dumps({"scripts": {"dev": "bun --watch api/server.ts", "build": "vite build"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (project_path / "api" / "server.ts").write_text("export const app = {}\n", encoding="utf-8")
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(
        api_system_map,
        "_latest_project_verification",
        lambda _project_id, _project_path, _operational: {
            "status": "unknown",
            "run_id": None,
            "ts": None,
            "checks": 0,
            "command": None,
            "source": "missing",
        },
    )

    operational = api_system_map._project_operational_status("family-hub")
    runtime = api_system_map._project_runtime_status(
        "family-hub",
        {"role": "家庭数字枢纽服务", "stack": "TypeScript (Vite, API server)"},
        operational,
        {"ports": {}, "types": {}},
        workspace_root / "protocols" / "port-registry.yaml",
    )

    assert runtime["status"] == "unobserved"
    assert runtime["profile"] == "service"
    assert runtime["needs_runtime"] is True
    assert "服务入口" in runtime["probe_reason"]


def test_latest_project_verification_falls_back_to_documented_command(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "runtime"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "AGENTS.md").write_text("## Commands\n```bash\nuv run pytest -q\n```\n", encoding="utf-8")
    (project_path / "pyproject.toml").write_text("[project]\nname='runtime'\n", encoding="utf-8")
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)

    operational = api_system_map._project_operational_status("runtime")
    verification = api_system_map._latest_project_verification("runtime", project_path, operational)

    assert verification["status"] == "documented"
    assert verification["source"] == "project_commands"
    assert "uv run pytest -q" in (verification["command"] or "")


def test_latest_project_verification_reads_blocked_yaml_run(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "cockpit"
    project_path.mkdir(parents=True, exist_ok=True)
    runs_dir = workspace_root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "run.yaml").write_text(
        "\n".join(
            [
                "run_id: run-blocked",
                "status: blocked",
                "updated_at: '2026-07-15T02:01:27Z'",
                "claims:",
                "  - paths:",
                "      - projects/cockpit",
                "evidence:",
                "  - 'agent-workflow verify: 1 checks ok=False'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("cockpit", project_path, {})

    assert verification == {
        "status": "failed",
        "run_id": "run-blocked",
        "ts": "2026-07-15T02:01:27Z",
        "checks": 1,
        "command": None,
        "source": "agent_workflow_run",
    }


def test_latest_project_verification_reads_omo_controlled_execution(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "demo"
    project_path.mkdir(parents=True, exist_ok=True)
    task_path = workspace_root / ".omo" / "tasks" / "active" / "cockpit-action-demo-copy-verify-command.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """id: cockpit-action-demo-copy-verify-command
metadata:
  execution_audit:
    command: cd "/workspace/projects/demo" && printf hello
    exit_code: 0
    log_ref: runtime/omo/demo.log
    actor: cockpit-task-center
    recorded_at: '2026-07-15T05:40:00Z'
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_system_map, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("demo", project_path, {})

    assert verification["status"] == "verified"
    assert verification["source"] == "omo_task_execution"
    assert verification["log_ref"] == "runtime/omo/demo.log"
    assert verification["actor"] == "cockpit-task-center"
