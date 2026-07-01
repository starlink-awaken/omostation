from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "governance-evolution.py"


def _python_with_yaml() -> str:
    candidates = [
        os.environ.get("GOVERNANCE_EVOLUTION_TEST_PYTHON"),
        shutil.which("python3.14"),
        shutil.which("python3"),
        sys.executable,
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result = subprocess.run(
            [candidate, "-c", "import yaml"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    return sys.executable


PYTHON = _python_with_yaml()


def _run_evolution(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_governance_evolution_registry_validates() -> None:
    result = _run_evolution("validate", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["initiative_count"] >= 8
    assert report["errors"] == []
    assert "bos://governance/evolution/loop" in report["entrypoints"]["bos"]


def test_governance_evolution_exposes_required_initiatives() -> None:
    result = _run_evolution("status", "--json")

    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    initiative_ids = {item["id"] for item in status["initiatives"]}

    assert "worktree-release-convergence" in initiative_ids
    assert "cockpit-governance-status-plane" in initiative_ids
    assert "claim-policy-tiering" in initiative_ids
    assert "bos-governance-evolution-routes" in initiative_ids
    assert "capability-traceability" in initiative_ids
    assert "governance-operating-rhythm" in initiative_ids
    assert "golden-path-e2e" in initiative_ids
    assert "entrypoint-convergence" in initiative_ids


def test_governance_evolution_traces_are_machine_readable() -> None:
    result = _run_evolution("traces", "--json")

    assert result.returncode == 0, result.stderr
    traces = json.loads(result.stdout)
    trace_ids = {item["id"] for item in traces}
    assert "trace.agent-governance-control-plane" in trace_ids
    assert "trace.governance-evolution-roadmap" in trace_ids
    assert "trace.release-package-convergence" in trace_ids
    assert "trace.omo-evolution-loop" in trace_ids


def test_governance_evolution_bos_routes_are_aligned() -> None:
    result = _run_evolution("status", "--json")

    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    assert status["errors"] == []
    assert {
        "bos://governance/evolution/status",
        "bos://governance/evolution/validate",
        "bos://governance/evolution/traces",
        "bos://governance/evolution/golden-paths",
        "bos://governance/evolution/packages",
        "bos://governance/evolution/loop",
    } == set(status["entrypoints"]["bos"])


def test_governance_evolution_golden_paths_are_machine_readable() -> None:
    result = _run_evolution("golden-paths", "--json")

    assert result.returncode == 0, result.stderr
    paths = json.loads(result.stdout)
    path_ids = {item["id"] for item in paths}
    assert {"agent-change", "strategy-ingress", "bos-invocation", "release-package-review"} <= path_ids


def test_governance_evolution_packages_are_machine_readable() -> None:
    result = _run_evolution("packages", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert "entry_count" in report
    assert "packages" in report
    assert "release_order" in report
    assert "recommended_next" in report
    assert "release_ready" in report
    assert "review_count" in report
    assert "review_workflows" in report
    assert "review_plan" in report
    assert "decision_count" in report
    assert "decision_template" in report
    assert "review_findings" in report
    assert report["unknown_count"] == 0
    assert report["decision_count"] == len(report["decision_template"])


def test_governance_evolution_packages_accepts_decision_file(tmp_path: Path) -> None:
    result = _run_evolution("packages", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    decision_file = tmp_path / "release-decisions.json"
    decision_file.write_text(
        json.dumps(
            {
                "decisions": [
                    {"decision_id": item["decision_id"], "decision": "defer", "notes": "test decision"}
                    for item in report["decision_template"]
                ]
            }
        ),
        encoding="utf-8",
    )

    decided = _run_evolution("packages", "--decisions", str(decision_file), "--json")

    assert decided.returncode == 0, decided.stderr
    decided_report = json.loads(decided.stdout)
    assert decided_report["ok"] is True
    assert decided_report["release_ready"] is True
    assert decided_report["decision_source"] == str(decision_file)
    assert decided_report["decision_summary"]["pending"] == 0
    assert decided_report["decision_summary"]["invalid"] == 0
    assert decided_report["decision_summary"]["defer"] == decided_report["decision_count"]
    assert {item["decision"] for item in decided_report["decision_template"]} <= {"defer"}


def test_governance_evolution_packages_writes_decision_template(tmp_path: Path) -> None:
    decision_file = tmp_path / "release-decisions.yaml"

    result = _run_evolution("packages", "--write-decisions-template", str(decision_file), "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["decision_template_written"] == str(decision_file)
    template_text = decision_file.read_text(encoding="utf-8")
    assert template_text.startswith("decisions:")
    assert template_text.count("decision_id:") == report["decision_count"]
    assert template_text.count("decision: null") == report["decision_count"]


def test_governance_evolution_packages_writes_defaulted_decisions(tmp_path: Path) -> None:
    decision_file = tmp_path / "release-decisions.yaml"

    result = _run_evolution(
        "packages",
        "--write-decisions-template",
        str(decision_file),
        "--decision-default",
        "defer",
        "--require-ready",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["release_ready"] is True
    assert report["decision_template_default"] == "defer"
    assert report["decision_summary"]["pending"] == 0
    assert report["decision_summary"]["defer"] == report["decision_count"]
    template_text = decision_file.read_text(encoding="utf-8")
    assert template_text.count("decision: defer") == report["decision_count"]

    decided = _run_evolution("packages", "--decisions", str(decision_file), "--require-ready", "--json")

    assert decided.returncode == 0, decided.stderr
    decided_report = json.loads(decided.stdout)
    assert decided_report["release_ready"] is True
    assert decided_report["decision_summary"]["pending"] == 0


def test_governance_evolution_packages_rejects_missing_decision_template_parent(tmp_path: Path) -> None:
    decision_file = tmp_path / "missing" / "release-decisions.yaml"

    result = _run_evolution("packages", "--write-decisions-template", str(decision_file), "--json")

    assert result.returncode == 2
    assert "release decisions output parent not found" in result.stderr
    assert not decision_file.exists()


def test_governance_evolution_packages_require_ready_blocks_pending_decisions() -> None:
    result = _run_evolution("packages", "--require-ready", "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert report["release_ready"] is False
    assert report["release_gate"] == {"required": True, "ok": False, "blocking": True}
    assert report["decision_summary"]["pending"] == report["decision_count"]
    assert report["recommended_next"] == "Complete release decisions before packaging."


def test_governance_evolution_packages_require_ready_accepts_complete_decisions(tmp_path: Path) -> None:
    result = _run_evolution("packages", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    decision_file = tmp_path / "ready-release-decisions.json"
    decision_file.write_text(
        json.dumps(
            {
                "decisions": [
                    {"decision_id": item["decision_id"], "decision": "exclude", "notes": "ready gate test"}
                    for item in report["decision_template"]
                ]
            }
        ),
        encoding="utf-8",
    )

    ready = _run_evolution("packages", "--decisions", str(decision_file), "--require-ready", "--json")

    assert ready.returncode == 0, ready.stderr
    ready_report = json.loads(ready.stdout)
    assert ready_report["ok"] is True
    assert ready_report["release_ready"] is True
    assert ready_report["release_gate"] == {"required": True, "ok": True, "blocking": False}
    assert ready_report["decision_summary"]["pending"] == 0
    assert ready_report["decision_summary"]["exclude"] == ready_report["decision_count"]


def test_governance_evolution_packages_rejects_invalid_decision_file(tmp_path: Path) -> None:
    decision_file = tmp_path / "bad-release-decisions.json"
    decision_file.write_text(
        json.dumps({"decisions": [{"path": "not/in/current/template", "decision": "include"}]}),
        encoding="utf-8",
    )

    result = _run_evolution("packages", "--decisions", str(decision_file), "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert report["release_ready"] is False
    assert report["decision_summary"]["invalid"] == 1
    assert report["decision_summary"]["invalid_decisions"][0]["reason"] == "decision target not in current template"
    assert report["recommended_next"] == "Fix invalid release decision records."


def test_release_readiness_flags_review_required_packages() -> None:
    code = f"""
import importlib.util
import json
spec = importlib.util.spec_from_file_location("governance_evolution", {str(SCRIPT)!r})
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
packages = {{
    "governance-task-lifecycle": {{"paths": [".omo/tasks/planned/example.yaml"]}},
    "governance-audit-report": {{"paths": ["debt-audit-report.md"]}},
    "strategy-ingress-artifact": {{"paths": [".c2g_data/pitches/example.md"]}},
    "archived-artifact": {{"paths": ["_archived/example/README.md"]}},
    "workspace-config": {{"paths": [".github/workflows/governance-check.yml"]}},
    "submodule-pointer": {{"paths": ["projects/agora"]}},
    "runtime-or-control-output": {{"paths": [".omo/_control/evolution/drift/example.json"]}},
    "data-output": {{"paths": ["data/cards/example.db"]}},
}}
findings = module.release_review_findings(packages)
print(json.dumps({{
    "findings": findings,
    "plan": module.release_review_plan(findings),
    "decision_template": module.release_decision_template(findings),
}}))
"""
    result = subprocess.run(
        [PYTHON, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    findings = payload["findings"]
    plan = payload["plan"]
    decision_template = payload["decision_template"]
    assert {item["package"] for item in findings} == {
        "governance-task-lifecycle",
        "governance-audit-report",
        "strategy-ingress-artifact",
        "archived-artifact",
        "workspace-config",
        "submodule-pointer",
        "runtime-or-control-output",
        "data-output",
    }
    assert all(item["severity"] == "review" for item in findings)
    assert {item["workflow"] for item in findings} == {
        "c2g-spec-ingress",
        "governance-state-mutation",
        "observer-audit",
        "project-code-change",
        "project-doc-change",
        "submodule-pointer-close",
    }
    assert all(item["owner"] for item in findings)
    assert all(item["recommended_action"] for item in findings)
    assert {item["workflow"] for item in plan} == {
        "c2g-spec-ingress",
        "governance-state-mutation",
        "observer-audit",
        "project-code-change",
        "project-doc-change",
        "submodule-pointer-close",
    }
    profiles_by_workflow = {item["workflow"]: item["profile"] for item in plan}
    assert profiles_by_workflow["submodule-pointer-close"] == "release-agent"
    assert profiles_by_workflow["observer-audit"] == "observer-agent"
    assert all(item["start_command"][-4:-2] == ["--profile", item["profile"]] for item in plan)
    assert all(item["path_count"] >= item["package_count"] for item in plan)
    assert all(item["decision_options"] == ["include", "exclude", "defer"] for item in plan)
    assert all(item["claim_commands"] for item in plan)
    assert all(command[-2] == "--path" for item in plan for command in item["claim_commands"])
    assert all(
        item["closeout_command_template"][-2] == "--evidence" and item["closeout_command_template"][7] == "<run-id>"
        for item in plan
    )
    claimed_paths = {command[-1] for item in plan for command in item["claim_commands"]}
    assert ".github/workflows/governance-check.yml" in claimed_paths
    assert "projects/agora" in claimed_paths
    assert len(decision_template) == sum(item["count"] for item in findings)
    assert {item["decision"] for item in decision_template} == {None}
    assert all(item["decision_required"] is True for item in decision_template)
    assert all(item["allowed_decisions"] == ["include", "exclude", "defer"] for item in decision_template)
    assert all(item["claim_command"][-2] == "--path" for item in decision_template)
    assert {item["path"] for item in decision_template} == claimed_paths


def test_release_package_classifier_covers_convergence_edges() -> None:
    paths = [
        ".env.example",
        ".gitignore",
        ".githooks/pre-push",
        ".github/workflows/cockpit-ui-ci.yml",
        "pyproject.toml",
        "bin/README.md",
        "bin/gac-worktree.sh",
        "tests/README.md",
        "scripts",
        "projects/omo",
        ".omo/state/system_health.yaml",
        ".omo/tasks/planned/OPC-P6-SELF-EVOLUTION-doc-gate-e.yaml",
        ".omo/tasks/registry/done/OPC-P7-H1/retrospective-v2026-07-01-r1.md",
        "debt-audit-report.md",
        ".c2g_data/pitches/example.md",
        "_archived/agora-dashboard/README.md",
        "ecos/src/ecos/ssot/mof/m1/mechanism/MECH-AGORA-SWARM.yaml",
    ]
    code = f"""
import importlib.util
import json
spec = importlib.util.spec_from_file_location("governance_evolution", {str(SCRIPT)!r})
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps({{path: module.classify_release_package(path)[0] for path in {paths!r}}}))
"""
    result = subprocess.run(
        [PYTHON, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    packages = json.loads(result.stdout)
    assert packages == {
        ".env.example": "workspace-config",
        ".gitignore": "workspace-config",
        ".githooks/pre-push": "workspace-config",
        ".github/workflows/cockpit-ui-ci.yml": "workspace-config",
        "pyproject.toml": "workspace-config",
        "bin/README.md": "governance-control-plane",
        "bin/gac-worktree.sh": "governance-control-plane",
        "tests/README.md": "governance-control-plane",
        "scripts": "submodule-pointer",
        "projects/omo": "submodule-pointer",
        ".omo/state/system_health.yaml": "runtime-or-control-output",
        ".omo/tasks/planned/OPC-P6-SELF-EVOLUTION-doc-gate-e.yaml": "governance-task-lifecycle",
        ".omo/tasks/registry/done/OPC-P7-H1/retrospective-v2026-07-01-r1.md": "governance-task-lifecycle",
        "debt-audit-report.md": "governance-audit-report",
        ".c2g_data/pitches/example.md": "strategy-ingress-artifact",
        "_archived/agora-dashboard/README.md": "archived-artifact",
        "ecos/src/ecos/ssot/mof/m1/mechanism/MECH-AGORA-SWARM.yaml": "mof-model-registry",
    }


def test_release_package_parser_decodes_git_quoted_paths() -> None:
    code = f"""
import importlib.util
import json
spec = importlib.util.spec_from_file_location("governance_evolution", {str(SCRIPT)!r})
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
status, path = module.parse_status_line('D  ".c2g_data/pitches/Idea-P46-mof-\\\\345\\\\267\\\\245.md"')
print(json.dumps({{"status": status, "path": path, "package": module.classify_release_package(path)[0]}}))
"""
    result = subprocess.run(
        [PYTHON, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed == {
        "status": "D",
        "path": ".c2g_data/pitches/Idea-P46-mof-工.md",
        "package": "strategy-ingress-artifact",
    }
