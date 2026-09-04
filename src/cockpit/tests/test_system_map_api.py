import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from cockpit import compat
from cockpit.dashboard_server import app
from cockpit.web import api_system_map, api_system_map_io_commands, api_system_map_status, system_map_status_helpers
from cockpit.web.api_system_map import build_source_ref_preview, build_system_map


def _workflow_lifecycle_fixture(project_id: str) -> dict:
    """Return deterministic workflow evidence without touching a live Workspace."""
    if project_id != "cockpit":
        return {
            "latest_run_id": None,
            "latest_status": "unknown",
            "latest_ts": None,
            "runs": [],
            "summary": {"runs": 0, "verified": 0, "failed": 0, "active": 0},
        }
    run = {
        "run_id": "cockpit-run-1",
        "workflow_id": "cockpit-docs",
        "objective": "test",
        "status": "closed",
        "verify_status": "verified",
        "verify_checks": 1,
        "latest_ts": "2024-01-01T00:00:03Z",
        "paths": ["projects/cockpit"],
        "events": [
            {
                "type": "claim",
                "status": "claimed",
                "ts": "2024-01-01T00:00:01Z",
                "summary": "claimed 1 path(s)",
                "paths": ["projects/cockpit"],
            },
            {
                "type": "verify",
                "status": "verified",
                "ts": "2024-01-01T00:00:02Z",
                "summary": "checks=1",
                "paths": ["projects/cockpit/README.md"],
            },
            {
                "type": "closeout",
                "status": "closed",
                "ts": "2024-01-01T00:00:03Z",
                "summary": "status=closed",
            },
        ],
    }
    return {
        "latest_run_id": run["run_id"],
        "latest_status": run["status"],
        "latest_ts": run["latest_ts"],
        "runs": [run],
        "summary": {"runs": 1, "verified": 1, "failed": 0, "active": 0},
    }


def test_system_map_builds_workspace_dimensions(monkeypatch, tmp_path):
    original_operational_status = api_system_map._project_operational_status

    def isolated_operational_status(project_id, project_data=None, project_path=None):
        if project_id == "toolbox":
            missing_storage = tmp_path / "missing-toolbox"
            isolated_data = {**(project_data or {}), "storage": str(missing_storage)}
            return original_operational_status(project_id, isolated_data, missing_storage)
        return original_operational_status(project_id, project_data, project_path)

    monkeypatch.setattr(api_system_map, "_project_operational_status", isolated_operational_status)
    monkeypatch.setattr(api_system_map, "_project_workflow_lifecycle", _workflow_lifecycle_fixture)
    payload = build_system_map()

    assert payload["schema_version"] == "v1"
    assert payload["architecture"]["model"] == "5+4+1+1"
    assert payload["summary"]["projects"] >= 1
    assert payload["summary"]["layers"] >= 1
    assert payload["summary"]["feature_domains"] >= 1
    assert payload["source_paths"]["project_registry"]["exists"] is True
    assert any(page["id"] == "SystemMap" for page in payload["cockpit_pages"])
    assert any(page["id"] == "Guide" for page in payload["cockpit_pages"])
    assert any(page["id"] == "GBrainAdmin" for page in payload["cockpit_pages"])
    # domain-app-write-gates is a legitimate dynamic gap when domain-apps are
    # unavailable or have security issues; assert gap shape instead of absence.
    assert all(gap.get("id") and gap.get("severity") for gap in payload["gaps"])
    assert any(layer["id"] == "L3" for layer in payload["layers"])
    assert any(project["id"] == "cockpit" for project in payload["projects"])
    assert any(domain["title"] == "治理与合规" for domain in payload["feature_domains"])
    assert any(path["id"] == "governance-loop" for path in payload["usage_paths"])
    runtime_path = next(path for path in payload["usage_paths"] if path["id"] == "runtime-diagnostics")
    assert "AlertCenter" in runtime_path["steps"]
    runtime_playbook = next(item for item in payload["playbooks"] if item["id"] == "runtime-diagnostic-loop")
    assert any(step["page_id"] == "AlertCenter" for step in runtime_playbook["steps"])
    assert payload["summary"]["roadmap_items"] >= 1
    page_contract = next(item for item in payload["roadmap"]["items"] if item["id"] == "page-contract-home")
    assert page_contract["status"] == "shipped"
    assert page_contract["cockpit_page"] == "Home"
    assert page_contract["verification"]["status"] == "passed"
    assert all(check["status"] == "passed" for check in page_contract["verification"]["checks"])
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
    assert payload["summary"]["page_maturity_ready"] == payload["summary"]["cockpit_pages"]
    assert any(step["page_id"] == "Compute" for playbook in payload["playbooks"] for step in playbook["steps"])
    assert any(step["page_id"] == "GBrainAdmin" for playbook in payload["playbooks"] for step in playbook["steps"])
    home_maturity = next(item for item in payload["page_maturity"]["items"] if item["page_id"] == "Home")
    assert home_maturity["roadmap_status"] == "shipped"
    assert "同步" in home_maturity["traceability_next_action"]
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
    projects_by_id = {project["id"]: project for project in payload["projects"]}
    assert "runtime" in maturity_by_page["Home"]["projects"]
    assert "ecos" in maturity_by_page["Protocol"]["projects"]
    assert "observability" in maturity_by_page["Topology"]["projects"]
    assert "family-hub" in maturity_by_page["QuestBoard"]["projects"]
    assert "compute-routing" in maturity_by_page["Compute"]["usage_paths"]
    # The root project registry folds gbrain into the `knowledge` compound.
    # SystemMap must not manufacture a retired standalone project merely
    # because GBrainAdmin remains a valid operator page.
    assert "gbrain" not in projects_by_id
    assert "gbrain" in projects_by_id["knowledge"]["role"].lower()
    assert maturity_by_page["GBrainAdmin"]["projects"] == []
    assert {"capability-1", "capability-2"} <= set(maturity_by_page["GBrainAdmin"]["domains"])
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
    registry_dimension = next(item for item in coverage["dimension_summary"] if item["id"] == "registry_contract")
    assert registry_dimension["status"] in {"ready", "warning", "failed"}
    assert (
        registry_dimension["ready"] + registry_dimension["warning"] + registry_dimension["failed"]
        == coverage["summary"]["projects"]
    )
    assert {item["id"] for item in registry_dimension["attention_projects"]} == {
        project["id"]
        for project in payload["projects"]
        if next(check for check in project["coverage_checks"] if check["id"] == "registry_contract")["status"]
        != "ready"
    }
    runtime_dimension = next(item for item in coverage["dimension_summary"] if item["id"] == "runtime_probe")
    runtime_attention_ids = {item["id"] for item in runtime_dimension["attention_projects"]}
    assert runtime_dimension["attention_count"] == len(runtime_dimension["attention_projects"])
    # 数据驱动断言（与 registry_contract 一致）：attention 集合必须与 payload 中
    # runtime_probe 非 ready 的项目一致，避免硬编码项目集合随 workspace 数据漂移而脆化
    assert runtime_attention_ids == {
        project["id"]
        for project in payload["projects"]
        if next(check for check in project["coverage_checks"] if check["id"] == "runtime_probe")["status"] != "ready"
    }
    verification_dimension = next(item for item in coverage["dimension_summary"] if item["id"] == "verification")
    assert verification_dimension["documented"] == verification_dimension["warning"]
    assert verification_dimension["evidence_score"] >= verification_dimension["score"]
    assert coverage["summary"]["documented_cells"] == verification_dimension["documented"]
    assert coverage["summary"]["evidence_score"] >= coverage["summary"]["score"]
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
    assert triage["summary"]["verification_commands"] >= 0
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
    project_execution = next(
        item for item in payload["roadmap"]["items"] if item["id"] == "project-action-execution-audit"
    )
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
    assert project_execution["status"] == "shipped"
    daily_playbook = next(item for item in payload["playbooks"] if item["id"] == "daily-health-check")
    assert daily_playbook["frequency"] == "daily"
    assert daily_playbook["steps"]
    assert all(step["page"]["id"] == step["page_id"] for step in daily_playbook["steps"])
    assert all(step["action"] and step["evidence"] and step["done_when"] for step in daily_playbook["steps"])
    cockpit_project = next(project for project in payload["projects"] if project["id"] == "cockpit")
    # registry 契约版本随工作区演进 (0.4.0→0.5.0…), 断言 semver 形态而非具体版本号
    version_parts = str(cockpit_project["registry_contract"]["version"]).split(".")
    assert len(version_parts) == 3 and all(part.isdigit() for part in version_parts)
    assert cockpit_project["registry_contract"]["python"] == ">=3.13"
    assert cockpit_project["registry_contract"]["build_backend"] == "hatchling"
    assert cockpit_project["registry_contract"]["coverage"]
    assert cockpit_project["registry_contract"]["missing_fields"] == []
    assert cockpit_project["registry_contract"]["status_text"] == "ready"
    assert cockpit_project["registry_contract"]["observed_location"] == "projects/cockpit/src"
    assert cockpit_project["registry_contract"]["implementation_traceability"] == "declared"
    assert cockpit_project["operational"]["docs"]["present"] >= 1
    assert cockpit_project["operational"]["commands"]
    mesh_router = next(project for project in payload["projects"] if project["id"] == "mesh-router")
    assert mesh_router["operational"]["surface_type"] == "implemented-in-bin"
    assert mesh_router["operational"]["status"] == "ready"
    mesh_contract = mesh_router["registry_contract"]
    assert mesh_contract["status"] == "archived"
    archive_path = Path(mesh_contract["physical_location"])
    assert archive_path.parts[:2] == ("bin", "_archive")
    mesh_verify = next(action for action in mesh_router["actions"] if action["id"] == "copy-verify-command")
    assert mesh_verify["value"] == (f'cd "{compat.WORKSPACE_ROOT}" && uv run python "{archive_path}" --check')
    assert not any(action["id"] == "copy-start-command" for action in mesh_router["actions"])
    metaos_project = next(project for project in payload["projects"] if project["id"] == "metaos")
    assert any("pytest" in command for command in metaos_project["operational"]["commands"])
    toolbox_project = next(project for project in payload["projects"] if project["id"] == "toolbox")
    assert toolbox_project["operational"]["surface_type"] == "external-storage"
    assert toolbox_project["operational"]["status"] == "missing"
    assert toolbox_project["operational"]["docs"]["present"] == 0
    assert toolbox_project["operational"]["docs"]["expected"] == 1
    toolbox_docs = next(check for check in toolbox_project["coverage_checks"] if check["id"] == "project_docs")
    assert toolbox_docs["status"] == "failed"
    docs_dimension = next(item for item in coverage["dimension_summary"] if item["id"] == "project_docs")
    assert docs_dimension["failed"] >= 1
    assert "toolbox" in {item["id"] for item in docs_dimension["attention_projects"]}
    assert cockpit_project["operational"]["next_action"]
    assert cockpit_project["source_refs"]
    assert cockpit_project["source_refs"][0]["source_key"] == "project_registry"
    assert cockpit_project["source_refs"][0]["line"]
    assert cockpit_project["actions"]
    if cockpit_project["registry_contract"]["status_text"] != "ready":
        assert any(command["id"] == "registry-contract" for command in cockpit_project["triage_commands"])
    security_check = next(check for check in cockpit_project["coverage_checks"] if check["id"] == "security_contract")
    assert security_check["status"] == "ready"
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
        "registry_contract",
        "security_contract",
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
    task_center_page = next(item for item in payload["page_maturity"]["items"] if item["page_id"] == "TaskCenter")
    complete_task_action = next(
        action for action in task_center_page["operator_action_details"] if action["id"] == "complete-task"
    )
    assert complete_task_action["label"] == "完成任务"
    assert complete_task_action["kind"] == "queue"
    assert complete_task_action["risk"] == "medium"
    assert complete_task_action["description"]
    assert "not_applicable_projects" in payload["summary"]
    assert "verification_ready" in payload["project_focus"]["summary"]
    governance_domain = next(domain for domain in payload["feature_domains"] if domain["title"] == "治理与合规")
    assert governance_domain["source_refs"][0]["source_key"] == "functional_capability_map"
    assert governance_domain["source_refs"][0]["line"]


def test_stopped_runtime_projects_expose_documented_start_actions():
    payload = build_system_map()
    projects = {project["id"]: project for project in payload["projects"]}

    expected_commands = {
        "ecos": "ecos.services.events_sse serve",
        "l4-kernel": "l4_kernel.mcp_server --sse",
        "observability": "docker compose up -d",
    }
    for project_id, fragment in expected_commands.items():
        action = next(action for action in projects[project_id]["actions"] if action["id"] == "copy-start-command")
        assert fragment in action["value"]
        assert action["executes"] is False
        assert action["risk"] == "medium"

    assert not any(action["id"] == "copy-start-command" for action in projects["bus-foundation"]["actions"])
    assert not any(action["id"] == "copy-start-command" for action in projects["mesh-router"]["actions"])
    # aetherforge 是否在 system_map，跟随主仓 registry 实际注册状态
    # （独立环境无主仓 registry 时 projects 为空，自动回退到 not in）
    _reg_path = compat.WORKSPACE_ROOT / "docs" / "project-registry.yaml"
    if _reg_path.exists():
        import yaml

        _reg = yaml.safe_load(_reg_path.read_text(encoding="utf-8")) or {}
        _expect_aetherforge = "aetherforge" in (_reg.get("projects") or {})
    else:
        _expect_aetherforge = False
    if _expect_aetherforge:
        assert "aetherforge" in projects
    else:
        assert "aetherforge" not in projects


def test_mesh_router_verify_normalization_requires_exact_script_basename():
    project_path = compat.WORKSPACE_ROOT / "bin" / "gac"
    unrelated = 'python3 "bin/gac/not-gac-mesh-router.py"'

    assert api_system_map_io_commands._project_verify_command(project_path, [unrelated], []) == (
        f'cd "{project_path}" && {unrelated}'
    )


def test_verify_command_tolerates_unbalanced_documented_quotes():
    project_path = compat.WORKSPACE_ROOT / "projects" / "demo"
    malformed = 'uv run pytest "unterminated'

    assert api_system_map_io_commands._project_verify_command(project_path, [malformed], []) == (
        f'cd "{project_path}" && {malformed}'
    )


def test_runtime_probe_command_is_successful_when_no_ports_are_listening():
    payload = build_system_map()
    project = next(item for item in payload["projects"] if item["id"] == "observability")
    command = next(item for item in project["triage_commands"] if item["id"] == "runtime-check-ports")["value"]

    assert command.endswith("; exit 0")
    assert "|| true" in command


def test_system_map_conflict_diagnostics_clear_after_port_alignment():
    payload = build_system_map()
    projects = {project["id"]: project for project in payload["projects"]}

    for project_id in ("ecos",):
        project = projects[project_id]
        assert project["runtime"]["port_conflicts"] == []
        assert all(not port.get("conflict_projects") for port in project["runtime"]["ports"])
    # aetherforge 是否在 system_map，跟随主仓 registry 实际注册状态
    _reg_path = compat.WORKSPACE_ROOT / "docs" / "project-registry.yaml"
    if _reg_path.exists():
        import yaml

        _reg = yaml.safe_load(_reg_path.read_text(encoding="utf-8")) or {}
        _expect_aetherforge = "aetherforge" in (_reg.get("projects") or {})
    else:
        _expect_aetherforge = False
    if _expect_aetherforge:
        assert "aetherforge" in projects
    else:
        assert "aetherforge" not in projects


def test_bus_foundation_metrics_is_optional_embedded_runtime():
    payload = build_system_map()
    project = next(item for item in payload["projects"] if item["id"] == "bus-foundation")

    assert project["runtime"]["profile"] == "library"
    assert project["runtime"]["needs_runtime"] is False
    assert project["runtime"]["status"] == "not_applicable"
    assert "按需开启" in project["runtime"]["probe_reason"]


def test_omo_dashboard_is_converged_to_cockpit_runtime():
    payload = build_system_map()
    project = next(item for item in payload["projects"] if item["id"] == "omo")

    assert project["runtime"]["profile"] == "converged"
    assert project["runtime"]["needs_runtime"] is False
    assert project["runtime"]["status"] == "not_applicable"
    assert "收敛到 Cockpit" in project["runtime"]["probe_reason"]
    assert not any(action["id"] == "copy-start-command" for action in project["actions"])


def test_evidence_freshness_distinguishes_fresh_stale_and_unknown():
    now = datetime(2026, 7, 28, tzinfo=UTC)

    fresh = api_system_map_status._evidence_freshness("2026-07-27T12:00:00Z", 24, now)
    stale = api_system_map_status._evidence_freshness("2026-07-26T12:00:00Z", 24, now)
    unknown = api_system_map_status._evidence_freshness(None, 24, now)

    assert fresh["status"] == "fresh"
    assert stale["status"] == "stale"
    assert unknown["status"] == "unknown"
    assert "重新执行" in stale["next_action"]


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
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)
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
    assert runtime["checked_at"]
    assert runtime["probe_source"] == "runtime_profile"
    assert runtime["probe_task"]["status"] == "not_queued"

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


def test_controlled_verification_audit_downgrades_stale_failure_to_closeout_warning(monkeypatch):
    monkeypatch.setattr(
        system_map_status_helpers,
        "_latest_controlled_verification",
        lambda _project_id: {"exit_code": 0, "log_ref": "runtime/omo/verification.log"},
    )
    checks = api_system_map._project_coverage_checks(
        {
            "id": "cockpit",
            "coverage": "native",
            "cockpit_page": "SystemMap",
            "operational": {
                "docs": {"present": 2, "expected": 2},
                "commands": ["verify"],
                "manifests": ["pyproject.toml"],
            },
            "runtime": {
                "status": "running",
                "profile": "service",
                "latest_verification": {"status": "failed", "checks": 1},
            },
            "source_refs": [{"exists": True}],
            "actions": [{"id": "copy-verify-command"}],
        }
    )
    verification = next(check for check in checks if check["id"] == "verification")
    assert verification["status"] == "warning"
    assert "受控重跑已通过" in verification["detail"]
    assert "agent-workflow" in verification["next_action"]


def test_runtime_status_does_not_probe_stdio_ports_as_tcp(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "ToolBox"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "CLAUDE.md").write_text("# toolbox\n", encoding="utf-8")
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)
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
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)
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
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    operational = api_system_map._project_operational_status("runtime")
    verification = api_system_map._latest_project_verification("runtime", project_path, operational)

    assert verification["status"] == "documented"
    assert verification["source"] == "project_commands"
    assert "uv run pytest -q" in (verification["command"] or "")


def test_unknown_project_without_verify_command_gets_verification_plan_triage(tmp_path):
    project_path = tmp_path / "projects" / "demo"
    project_path.mkdir(parents=True, exist_ok=True)
    commands = api_system_map_io_commands._project_triage_commands(
        {
            "id": "demo",
            "path": str(project_path),
            "runtime": {"status": "unobserved", "latest_verification": {"status": "unknown"}, "ports": []},
            "actions": [],
            "operational": {"status": "missing"},
            "registry_contract": {"missing_fields": []},
        }
    )
    plan = next(command for command in commands if command["id"] == "verification-plan")
    assert plan["category"] == "verification"
    assert "pytest" in plan["value"]
    assert plan["executes"] is False


def test_project_without_security_contract_gets_security_triage(tmp_path):
    project_path = tmp_path / "projects" / "demo"
    project_path.mkdir(parents=True, exist_ok=True)
    commands = api_system_map_io_commands._project_triage_commands(
        {
            "id": "demo",
            "path": str(project_path),
            "runtime": {"status": "not_applicable", "latest_verification": {"status": "verified"}, "ports": []},
            "actions": [],
            "operational": {"status": "ready"},
            "registry_contract": {"missing_fields": []},
        }
    )

    security = next(command for command in commands if command["id"] == "security-contract")
    assert security["category"] == "coverage"
    assert security["executes"] is False


def test_project_with_security_audit_uses_audit_as_security_evidence(tmp_path):
    (tmp_path / "AUDIT.md").write_text("# Security audit\n", encoding="utf-8")
    checks = api_system_map._project_coverage_checks(
        {
            "id": "toolbox",
            "coverage": "native",
            "cockpit_page": "Assets",
            "path": str(tmp_path),
            "operational": {
                "docs": {"present": 1, "expected": 1},
                "commands": ["audit"],
                "manifests": ["package.json"],
            },
            "runtime": {"status": "not_applicable", "profile": "external"},
            "registry_contract": {"missing_fields": []},
            "source_refs": [{"exists": True}],
            "actions": [{"id": "copy-project-path"}],
        }
    )
    security = next(check for check in checks if check["id"] == "security_contract")
    assert security["status"] == "ready"
    assert "AUDIT.md" in security["detail"]


def test_project_ports_observe_compose_host_ports_without_registry_entry(tmp_path, monkeypatch):
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(
        'services:\n  langfuse-server:\n    ports:\n      - "3050:3000"\n  db:\n    ports:\n      - "5433:5432"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_system_map_io_commands, "_is_port_listening", lambda _port: False)
    ports = api_system_map_io_commands._project_ports("observability", {}, compose_path, tmp_path)
    assert [(port["port"], port["service"]) for port in ports] == [
        (3050, "observability/langfuse-server"),
        (5433, "observability/db"),
    ]
    assert all(port["source_ref"]["source_key"] == "project_compose" for port in ports)


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
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("cockpit", project_path, {})

    assert verification == {
        "status": "failed",
        "run_id": "run-blocked",
        "ts": "2026-07-15T02:01:27Z",
        "checks": 1,
        "command": None,
        "source": "agent_workflow_run",
    }


def test_latest_project_verification_reads_ok_yaml_run_as_verified(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "agora"
    project_path.mkdir(parents=True, exist_ok=True)
    runs_dir = workspace_root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "run.yaml").write_text(
        """run_id: run-ok
status: ok
updated_at: '2026-07-15T03:01:27Z'
closed_at: '2026-07-15T03:01:28Z'
claims:
  - paths:
      - projects/agora/tests/test_analysis.py
evidence:
  - 'agent-workflow verify: 1 checks ok=True'
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("agora", project_path, {})

    assert verification == {
        "status": "verified",
        "run_id": "run-ok",
        "ts": "2026-07-15T03:01:27Z",
        "checks": 1,
        "command": None,
        "source": "agent_workflow_run",
        "closeout_status": "closed",
        "closeout_ref": ".omo/_delivery/agent-workflows/runs/run.yaml",
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
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("demo", project_path, {})

    assert verification["status"] == "verified"
    assert verification["source"] == "omo_task_execution"
    assert verification["log_ref"] == "runtime/omo/demo.log"
    assert verification["actor"] == "cockpit-task-center"


def test_latest_project_verification_reads_triage_execution_and_closeout_state(tmp_path, monkeypatch):
    workspace_root = tmp_path
    project_path = workspace_root / "projects" / "demo"
    project_path.mkdir(parents=True, exist_ok=True)
    task_path = workspace_root / ".omo" / "tasks" / "done" / "cockpit-triage-demo-verification-rerun.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """id: cockpit-triage-demo-verification-rerun
metadata:
  execution_audit:
    command: cd "/workspace/projects/demo" && printf hello
    exit_code: 0
    log_ref: runtime/omo/demo.log
    closeout_ref: null
    actor: cockpit-task-center
    recorded_at: '2026-07-15T05:40:00Z'
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    verification = api_system_map._latest_project_verification("demo", project_path, {})

    assert verification["status"] == "verified"
    assert verification["run_id"] == "cockpit-triage-demo-verification-rerun"
    assert verification["closeout_status"] == "missing"


def test_triage_posture_reads_latest_retry_attempt(tmp_path, monkeypatch):
    workspace_root = tmp_path
    task_path = workspace_root / ".omo" / "tasks" / "done" / "cockpit-triage-demo-runtime-check-ports-r2.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """id: cockpit-triage-demo-runtime-check-ports-r2
status: completed
metadata:
  execution_audit:
    exit_code: 1
    log_ref: runtime/omo/probe-r2.log
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(compat, "WORKSPACE_ROOT", workspace_root)

    posture = api_system_map_io_commands._triage_task_posture("demo", "runtime-check-ports")

    assert posture["task_id"] == "cockpit-triage-demo-runtime-check-ports-r2"
    assert posture["status"] == "failed"
    assert posture["execution_audit"]["log_ref"] == "runtime/omo/probe-r2.log"


def test_triage_posture_reads_archived_done_execution(tmp_path, monkeypatch):
    workspace_root = tmp_path
    task_path = workspace_root / ".omo" / "tasks" / "archived" / "done" / "cockpit-triage-demo-verification-rerun.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """id: cockpit-triage-demo-verification-rerun
status: done
metadata:
  execution_audit:
    exit_code: 0
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_system_map_io_commands.compat, "WORKSPACE_ROOT", workspace_root)
    posture = api_system_map_io_commands._triage_task_posture("demo", "verification-rerun")
    assert posture["status"] == "succeeded"
    assert posture["task_id"] == "cockpit-triage-demo-verification-rerun"


def test_triage_posture_exposes_runtime_approval_state(tmp_path, monkeypatch):
    workspace_root = tmp_path
    task_path = workspace_root / ".omo" / "tasks" / "planned" / "cockpit-triage-demo-runtime-check-ports.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """id: cockpit-triage-demo-runtime-check-ports
status: pending
human_approval_required: true
metadata: {}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(api_system_map_io_commands.compat, "WORKSPACE_ROOT", workspace_root)

    posture = api_system_map_io_commands._triage_task_posture("demo", "runtime-check-ports")

    assert posture["human_approval_required"] is True
    assert posture["approval_state"] == "missing"
    assert posture["next_action"] == "先申请人工审批"


def test_external_ui_worktree_is_resolved_from_registry_path_env(tmp_path, monkeypatch):
    ui_root = tmp_path / "cockpit-ui-worktree"
    (ui_root / "src").mkdir(parents=True)
    (ui_root / "AGENTS.md").write_text("## Commands\n```bash\nbun run build\n```\n", encoding="utf-8")
    (ui_root / "README.md").write_text("# cockpit-ui\n", encoding="utf-8")
    (ui_root / "CLAUDE.md").write_text("# cockpit-ui\n", encoding="utf-8")
    (ui_root / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}}),
        encoding="utf-8",
    )
    (ui_root / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    monkeypatch.setenv("COCKPIT_UI_ROOT", str(ui_root))

    project_data = {
        "id": "cockpit-ui",
        "path_env": "COCKPIT_UI_ROOT",
        "role": "Web 控制台 UI",
        "stack": "TypeScript (Vite, React)",
    }
    operational = api_system_map._project_operational_status("cockpit-ui", project_data)

    assert operational["status"] == "ready"
    assert operational["surface_type"] == "external-worktree"
    assert operational["path_configured"] is True
    assert operational["path_env"] == "COCKPIT_UI_ROOT"
    assert operational["next_action"] == "保持项目注册表与 Cockpit 映射同步。"


def test_available_external_storage_keeps_project_docs_ready(tmp_path):
    storage = tmp_path / "toolbox"
    storage.mkdir()
    (storage / "README.md").write_text("# Toolbox\n", encoding="utf-8")
    (storage / "AGENTS.md").write_text(
        "## Commands\n```bash\npython -m toolbox\n```\n",
        encoding="utf-8",
    )
    (storage / "pyproject.toml").write_text("[project]\nname = 'toolbox'\n", encoding="utf-8")

    operational = api_system_map._project_operational_status(
        "toolbox",
        {"storage": str(storage)},
        storage,
    )
    checks = api_system_map._project_coverage_checks(
        {
            "id": "toolbox",
            "path": str(storage),
            "coverage": "native",
            "cockpit_page": "SystemMap",
            "operational": operational,
            "runtime": {
                "status": "not_applicable",
                "profile": "static",
                "latest_verification": {},
            },
            "source_refs": [{"exists": True}],
            "actions": [{"id": "copy-project-path"}],
        }
    )
    docs = next(check for check in checks if check["id"] == "project_docs")

    assert operational["status"] == "ready"
    assert operational["surface_type"] == "external-storage"
    assert operational["docs"]["present"] >= operational["docs"]["expected"]
    assert docs["status"] == "ready"
