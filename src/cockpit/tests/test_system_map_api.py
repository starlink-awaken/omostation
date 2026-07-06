from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web.api_system_map import build_source_ref_preview, build_system_map


def test_system_map_builds_workspace_dimensions():
    payload = build_system_map()

    assert payload["schema_version"] == "v1"
    assert payload["architecture"]["model"] == "5+4+1+1"
    assert payload["summary"]["projects"] >= 1
    assert payload["summary"]["layers"] >= 1
    assert payload["summary"]["feature_domains"] >= 1
    assert payload["source_paths"]["project_registry"]["exists"] is True
    assert any(page["id"] == "SystemMap" for page in payload["cockpit_pages"])
    assert all(gap["id"] != "domain-app-write-gates" for gap in payload["gaps"])
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
    assert payload["summary"]["page_maturity_gap"] >= 1
    page_maturity = payload["page_maturity"]
    assert page_maturity["summary"]["total"] == payload["summary"]["cockpit_pages"]
    assert page_maturity["summary"]["score"] == payload["summary"]["page_maturity_score"]
    assert page_maturity["attention_items"]
    assert all(item["status"] in {"gap", "watch"} for item in page_maturity["attention_items"])
    assert all(item["next_action"] for item in page_maturity["items"])
    assert any(item["page_id"] == "SystemMap" for item in page_maturity["items"])
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
    assert cockpit_project["runtime"]["latest_verification"]["status"] in {"verified", "failed", "unknown"}
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
