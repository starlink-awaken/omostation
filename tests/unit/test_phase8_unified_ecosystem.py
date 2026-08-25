"""
Unit tests for Phase 8 Unified Ecosystem, Root Resolver, Watchdog, and Domain Scenarios.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

env_resolver = _load_module_from_file("env_resolver", WORKSPACE / "bin" / "cockpit" / "env-resolver.py")
_ROOT = env_resolver.setup_workspace_paths()


import importlib.util

def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

daemon_watchdog = _load_module_from_file("daemon_watchdog", WORKSPACE / "bin" / "gac" / "daemon-watchdog.py")
real_scenario_runner = _load_module_from_file("real_scenario_runner", WORKSPACE / "bin" / "ssot" / "real-scenario-runner.py")


def test_env_resolver_workspace_paths():
    root = env_resolver.get_workspace_root()
    assert (root / "AGENTS.md").exists()
    assert (root / "projects").is_dir()
    assert str(root / "projects" / "omo" / "src") in sys.path
    assert str(root / "projects" / "ecos" / "src") in sys.path
    assert str(root / "projects" / "agora" / "src") in sys.path


def test_daemon_watchdog_probing():
    probe = daemon_watchdog.check_daemon_health(timeout=1.0)
    assert "ok" in probe
    assert "port" in probe
    assert probe["port"] == 7432
    assert "latency_ms" in probe


def test_weijian_domain_scenario_evaluation():
    sc_path = WORKSPACE / "spaces" / "domain-scenarios" / "weijian_hospital_cloud_review.yaml"
    assert sc_path.exists()
    manifest = real_scenario_runner.load_scenario(sc_path)

    res = real_scenario_runner.evaluate_weijian_scenario(manifest)
    assert res["scenario_id"] == "SC-WJ-HOSPITAL-CLOUD-001"
    assert res["domain"] == "work-weijian"
    assert res["status"] == "APPROVED"
    assert len(res["evaluations"]) == 2
    assert res["evaluations"][0]["rule_id"] == "E-POL-WJ-001"
    assert res["evaluations"][0]["verdict"] == "PASS"
    assert res["evaluations"][1]["rule_id"] == "E-POL-WJ-002"
    assert res["evaluations"][1]["verdict"] == "PASS"


def test_tech_transfer_domain_scenario_evaluation():
    sc_path = WORKSPACE / "spaces" / "domain-scenarios" / "tech_transfer_team_allocation.yaml"
    assert sc_path.exists()
    manifest = real_scenario_runner.load_scenario(sc_path)

    res = real_scenario_runner.evaluate_transfer_scenario(manifest)
    assert res["scenario_id"] == "SC-TF-SURGICAL-NAV-001"
    assert res["domain"] == "work-transfer"
    assert res["status"] == "APPROVED"
    assert len(res["evaluations"]) == 2
    assert res["evaluations"][0]["rule_id"] == "E-POL-TF-001"
    assert res["evaluations"][0]["verdict"] == "PASS"
    assert res["evaluations"][1]["rule_id"] == "E-POL-TF-002"
    assert res["evaluations"][1]["verdict"] == "PASS"


def test_resident_decision_proposal_structure():
    mock_eval = {
        "scenario_id": "TEST-SC-001",
        "domain": "test-domain",
        "title": "Unit Test Domain Scenario",
        "status": "APPROVED",
        "evaluations": [
            {
                "rule_id": "E-POL-TEST-001",
                "name": "Test Rule",
                "verdict": "PASS",
                "detail": "Test verification passed",
            }
        ],
    }

    json_file, md_file = real_scenario_runner.record_resident_decision(mock_eval)
    assert json_file.exists()
    assert md_file.exists()

    # Verify JSON proposal structure
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "resident-decision/v1"
    assert data["trigger_event"]["event_type"] == "DomainScenarioEvaluated"
    assert data["proposals"][0]["level"] == "L3_STRATEGIC"
    assert data["proposals"][0]["action"] == "AUTHORIZE_WORKFLOW_EXECUTION"

    # Verify Markdown proposal structure
    md_text = md_file.read_text(encoding="utf-8")
    assert "---" in md_text
    assert "id: DEC-" in md_text
    assert "status: accepted" in md_text
    assert "## 2. Policy-as-Code 规则审查明细" in md_text

    # Cleanup mock test files
    if json_file.exists():
        json_file.unlink()
    if md_file.exists():
        md_file.unlink()
