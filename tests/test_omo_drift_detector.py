from __future__ import annotations

import json
from pathlib import Path

import yaml

from omo.omo_drift_detector import build_drift_report, write_drift_report


def test_build_and_write_drift_report(tmp_path: Path) -> None:
    (tmp_path / "projects" / "cockpit" / "src" / "cockpit").mkdir(
        parents=True, exist_ok=True
    )
    (
        tmp_path / "projects" / "runtime" / "src" / "runtime" / "executor" / "config"
    ).mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "_truth" / "goals").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "tasks" / "planned").mkdir(parents=True, exist_ok=True)
    (tmp_path / "runtime" / "omo" / "_control" / "evolution" / "drift").mkdir(
        parents=True, exist_ok=True
    )

    (tmp_path / "projects" / "cockpit" / "src" / "cockpit" / "cli.py").write_text(
        "\n".join(
            [
                'scenario_sub.add_parser("radar")',
                'scenario_sub.add_parser("assistant")',
                'scenario_sub.add_parser("health")',
            ]
        ),
        encoding="utf-8",
    )
    (
        tmp_path / "projects" / "runtime" / "src" / "runtime" / "executor" / "engine.py"
    ).write_text("# clean\n", encoding="utf-8")
    (
        tmp_path
        / "projects"
        / "runtime"
        / "src"
        / "runtime"
        / "executor"
        / "config"
        / "__init__.py"
    ).write_text("# clean\n", encoding="utf-8")
    (tmp_path / "projects" / "cockpit" / "src" / "cockpit" / "commands").mkdir(
        parents=True, exist_ok=True
    )
    (
        tmp_path
        / "projects"
        / "cockpit"
        / "src"
        / "cockpit"
        / "commands"
        / "scenario.py"
    ).write_text("# clean\n", encoding="utf-8")
    (tmp_path / "docs" / "OPC-PHASE4-MODEL-COMPUTE.md").write_text(
        "Gate E passed\nopc_phase4_gate_e_passed\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "tasks" / "planned" / "OPC-P4-MODEL-COMPUTE.yaml").write_text(
        "id: OPC-P4-MODEL-COMPUTE\ngate_status: passed\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "state" / "system.yaml").write_text(
        yaml.safe_dump({"health_score": 100}, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "_truth" / "goals" / "current.yaml").write_text(
        yaml.safe_dump(
            {"governance": {"ecosystem_maturity_score": 100}}, sort_keys=False
        ),
        encoding="utf-8",
    )
    goals_link = tmp_path / ".omo" / "goals"
    goals_link.symlink_to(
        tmp_path / ".omo" / "_truth" / "goals", target_is_directory=True
    )

    payload = build_drift_report(tmp_path)
    output_path = write_drift_report(tmp_path, payload)

    assert payload["kinds"] == 4
    assert payload["drift_count"] == 0
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["results"][0]["kind"] == "entry_drift"


def test_build_drift_report_accepts_multi_document_yaml(tmp_path: Path) -> None:
    (tmp_path / "projects" / "cockpit" / "src" / "cockpit").mkdir(
        parents=True, exist_ok=True
    )
    (
        tmp_path / "projects" / "runtime" / "src" / "runtime" / "executor" / "config"
    ).mkdir(parents=True, exist_ok=True)
    (tmp_path / "projects" / "cockpit" / "src" / "cockpit" / "commands").mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "_truth" / "goals").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "tasks" / "planned").mkdir(parents=True, exist_ok=True)

    (tmp_path / "projects" / "cockpit" / "src" / "cockpit" / "cli.py").write_text(
        'scenario_sub.add_parser("radar")\nscenario_sub.add_parser("assistant")\nscenario_sub.add_parser("health")\n',
        encoding="utf-8",
    )
    (
        tmp_path / "projects" / "runtime" / "src" / "runtime" / "executor" / "engine.py"
    ).write_text("# clean\n", encoding="utf-8")
    (
        tmp_path
        / "projects"
        / "runtime"
        / "src"
        / "runtime"
        / "executor"
        / "config"
        / "__init__.py"
    ).write_text("# clean\n", encoding="utf-8")
    (
        tmp_path
        / "projects"
        / "cockpit"
        / "src"
        / "cockpit"
        / "commands"
        / "scenario.py"
    ).write_text("# clean\n", encoding="utf-8")
    (tmp_path / "docs" / "OPC-PHASE4-MODEL-COMPUTE.md").write_text(
        "Gate E passed\nopc_phase4_gate_e_passed\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "tasks" / "planned" / "OPC-P4-MODEL-COMPUTE.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "id: OPC-P4-MODEL-COMPUTE\n"
        "gate_status: passed\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "state" / "system.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\nhealth_score: 100\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo" / "_truth" / "goals" / "current.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "governance:\n"
        "  ecosystem_maturity_score: 100\n",
        encoding="utf-8",
    )
    goals_link = tmp_path / ".omo" / "goals"
    goals_link.symlink_to(
        tmp_path / ".omo" / "_truth" / "goals", target_is_directory=True
    )

    payload = build_drift_report(tmp_path)

    assert payload["drift_count"] == 0
    assert payload["results"][1]["kind"] == "doc_drift"
