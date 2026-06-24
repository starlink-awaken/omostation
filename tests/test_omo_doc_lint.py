from __future__ import annotations

import json
from pathlib import Path

from omo.omo_doc_lint import run_doc_lint, update_doc_lint_index, write_doc_lint_outputs


def test_doc_lint_persistence_helpers(tmp_path: Path) -> None:
    findings = {
        "generated_at": "2026-06-20T00:00:00Z",
        "key_docs": {
            "expected": 6,
            "present": ["docs/PANORAMA.md"],
            "missing": [],
            "drift": False,
        },
        "phase_doc_consistency": [{"phase": "P4", "drift": False}],
        "dead_links": [],
        "term_consistency_issues": [],
        "drift_total": 0,
    }
    history = update_doc_lint_index(tmp_path, findings)
    findings["history"] = history
    json_path, md_path = write_doc_lint_outputs(tmp_path, findings, "2026-06-20")

    assert history["summary"]["run_count"] == 1
    assert json.loads(json_path.read_text(encoding="utf-8"))["drift_total"] == 0
    assert md_path.exists()


def test_run_doc_lint_executes_full_check(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in [
        "PANORAMA.md",
        "ENTRY-CONVERGENCE.md",
        "JOURNEY-PROBES.md",
        "OPC-ROADMAP.md",
        "OPC-MASTER-EXECUTION-PLAYBOOK.md",
        "OPC-GOVERNANCE-CARRIERS-INDEX.md",
        "OPC-PHASE4-MODEL-COMPUTE.md",
    ]:
        (docs / name).write_text("> Status: passed\n", encoding="utf-8")
    planned = tmp_path / ".omo" / "tasks" / "planned"
    planned.mkdir(parents=True)
    (planned / "OPC-P4-MODEL-COMPUTE.yaml").write_text(
        "gate: Gate E\ngate_status: passed\n", encoding="utf-8"
    )
    findings, json_path, md_path = run_doc_lint(
        tmp_path,
        key_docs=[
            "docs/PANORAMA.md",
            "docs/ENTRY-CONVERGENCE.md",
            "docs/JOURNEY-PROBES.md",
            "docs/OPC-ROADMAP.md",
            "docs/OPC-MASTER-EXECUTION-PLAYBOOK.md",
            "docs/OPC-GOVERNANCE-CARRIERS-INDEX.md",
        ],
        phase_plan_docs=[
            ("P4", "OPC-P4-MODEL-COMPUTE", "docs/OPC-PHASE4-MODEL-COMPUTE.md")
        ],
        generated_at="2026-06-21T00:00:00Z",
        today="2026-06-21",
    )
    assert findings["drift_total"] == 0
    assert json_path.exists()
    assert md_path.exists()


def test_run_doc_lint_accepts_multi_document_phase_plan_yaml(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in [
        "PANORAMA.md",
        "ENTRY-CONVERGENCE.md",
        "JOURNEY-PROBES.md",
        "OPC-ROADMAP.md",
        "OPC-MASTER-EXECUTION-PLAYBOOK.md",
        "OPC-GOVERNANCE-CARRIERS-INDEX.md",
        "OPC-PHASE4-MODEL-COMPUTE.md",
    ]:
        (docs / name).write_text("> Status: passed\n", encoding="utf-8")
    planned = tmp_path / ".omo" / "tasks" / "planned"
    planned.mkdir(parents=True)
    (planned / "OPC-P4-MODEL-COMPUTE.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "gate: Gate E\n"
        "gate_status: passed\n",
        encoding="utf-8",
    )

    findings, _, _ = run_doc_lint(
        tmp_path,
        key_docs=[
            "docs/PANORAMA.md",
            "docs/ENTRY-CONVERGENCE.md",
            "docs/JOURNEY-PROBES.md",
            "docs/OPC-ROADMAP.md",
            "docs/OPC-MASTER-EXECUTION-PLAYBOOK.md",
            "docs/OPC-GOVERNANCE-CARRIERS-INDEX.md",
        ],
        phase_plan_docs=[
            ("P4", "OPC-P4-MODEL-COMPUTE", "docs/OPC-PHASE4-MODEL-COMPUTE.md")
        ],
        generated_at="2026-06-21T01:00:00Z",
        today="2026-06-21",
    )

    assert findings["drift_total"] == 0
