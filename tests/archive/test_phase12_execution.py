from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OMO_ROOT = REPO_ROOT / ".omo"


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def test_phase12_registry_and_scenario_evidence_are_complete() -> None:
    capabilities = _read_yaml("registry/projects-capabilities.yaml")["capabilities"]
    sharedwork = _read_yaml("registry/sharedwork-sample.yaml")["capabilities"]
    trace = _read_yaml("evidence/phase12/research-pipeline-trace.yaml")
    dry_run = _read_yaml("evidence/phase12/package-dry-run.yaml")
    samples = _read_yaml("registry/article-samples.yaml")["samples"]

    assert len(capabilities) >= 50
    assert len(sharedwork) >= 10
    assert trace["status"] == "ready"
    assert trace["mode"] == "dry-run"
    assert trace["missing_capabilities"] == []
    assert {step["capability_id"] for step in trace["steps"]} == {
        "kairon.kronos",
        "kairon.ontoderive",
        "kairon.minerva",
        "project.gbrain",
    }
    assert dry_run["mode"] == "dry-run"
    assert dry_run["mutations_applied"] == 0
    assert len(samples) == 5
    assert all(sample["quality_score"] >= 70 for sample in samples)


def test_phase12_cli_commands_are_usable() -> None:
    registry = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "omo"), "registry", "browse"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert '"total"' in registry.stdout

    discover = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "omo"), "capability", "discover", "--tag", "research-pipeline"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "kairon.kronos" in discover.stdout

    bind = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "omo"),
            "capability",
            "bind",
            "--scenario",
            str(OMO_ROOT / "scenarios" / "research-pipeline.yaml"),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert '"status": "ready"' in bind.stdout


def test_phase12_closeout_and_handoff_documents_exist() -> None:
    required = [
        "standards/capability-metamodel.md",
        "standards/capabilities.schema.yaml",
        "standards/scenario.schema.yaml",
        "standards/capability-binding-policy.md",
        "standards/article-ingestion-policy.md",
        "registry/INDEX.md",
        "registry/pilot-contract.yaml",
        "plans/phase12-p0-pilot-adr.md",
        "evidence/phase12/pilot-rollback.md",
        "evidence/phase12/promotion-checklist.md",
        "_knowledge/management/phase12-cross-audit.md",
        "_knowledge/management/phase12-redteam.md",
        "summaries/phase12-pilot-closeout.md",
        "summaries/phase12-retrospective.md",
        "summaries/phase12-closeout.md",
    ]

    for rel_path in required:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    closeout = (OMO_ROOT / "summaries" / "phase12-closeout.md").read_text(encoding="utf-8")
    redteam = (OMO_ROOT / "_knowledge" / "management" / "phase12-redteam.md").read_text(encoding="utf-8")
    backlog = (OMO_ROOT / "plans" / "phase14-deferred-ecosystem-backlog.md").read_text(encoding="utf-8")
    assert "Phase 12 is complete" in closeout
    assert "No Critical finding blocks Phase 12 closeout" in redteam
    assert "memU" in backlog
    assert "install/add/remove/list" in backlog
