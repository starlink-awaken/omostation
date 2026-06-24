from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


from .omo_io import write_text_atomic
from .opc_phase_paths import resolve_opc_phase_task_path
from .omo_shared import load_yaml_docs


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(workspace_root: Path, rel: str) -> str:
    return (workspace_root / rel).read_text(encoding="utf-8")


def _read_yaml(workspace_root: Path, rel: str) -> dict[str, Any]:
    return load_yaml_docs(_read(workspace_root, rel))


def detect_entry_drift(workspace_root: Path) -> dict[str, Any]:
    cli = _read(workspace_root, "projects/cockpit/src/cockpit/cli.py")
    has_radar = (
        'scenario_sub.add_parser("radar"' in cli
        or 'sub.add_parser("radar"' in cli
        or 'add_parser(\n        "radar"' in cli
    )
    has_assistant = (
        'scenario_sub.add_parser("assistant"' in cli
        or 'sub.add_parser("assistant"' in cli
        or 'add_parser(\n        "assistant"' in cli
    )
    has_health = (
        'scenario_sub.add_parser("health"' in cli
        or 'sub.add_parser("health"' in cli
        or 'add_parser(\n        "health"' in cli
    )
    missing = [
        name
        for name, present in [
            ("radar", has_radar),
            ("assistant", has_assistant),
            ("health", has_health),
        ]
        if not present
    ]
    return {
        "kind": "entry_drift",
        "ts": _now_iso(),
        "expected": ["radar", "assistant", "health"],
        "present": [
            name
            for name, present in [
                ("radar", has_radar),
                ("assistant", has_assistant),
                ("health", has_health),
            ]
            if present
        ],
        "missing": missing,
        "drift": len(missing) > 0,
    }


def detect_doc_drift(workspace_root: Path) -> dict[str, Any]:
    plan_rel = str(
        resolve_opc_phase_task_path(
            workspace_root, "OPC-P4-MODEL-COMPUTE"
        ).relative_to(workspace_root)
    )
    plan = _read_yaml(workspace_root, plan_rel)
    phase_doc_path = workspace_root / "docs" / "OPC-PHASE4-MODEL-COMPUTE.md"
    doc_exists = phase_doc_path.exists()
    phase_doc = phase_doc_path.read_text(encoding="utf-8") if doc_exists else ""
    plan_gate_status = plan.get("gate_status")
    doc_says_passed = (
        "Gate E passed" in phase_doc and "opc_phase4_gate_e_passed" in phase_doc
    )
    consistent = doc_exists and plan_gate_status == "passed" and doc_says_passed
    return {
        "kind": "doc_drift",
        "ts": _now_iso(),
        "plan_ref": plan_rel,
        "doc_ref": "docs/OPC-PHASE4-MODEL-COMPUTE.md",
        "doc_exists": doc_exists,
        "plan_gate_status": plan_gate_status,
        "doc_says_passed": doc_says_passed,
        "consistent": consistent,
        "drift": not consistent,
    }


def detect_duplicate_facts(workspace_root: Path) -> dict[str, Any]:
    sys_state = _read_yaml(workspace_root, ".omo/state/system.yaml")
    goals = _read_yaml(workspace_root, ".omo/goals/current.yaml")
    sys_health = sys_state.get("health_score")
    findings: list[str] = []
    if isinstance(sys_health, (int, float)) and sys_health < 100 and goals:
        maturity = goals.get("governance", {}).get("ecosystem_maturity_score")
        if maturity == 100:
            findings.append(
                f"system.yaml health_score={sys_health} but goals.governance.ecosystem_maturity_score=100"
            )
    return {
        "kind": "duplicate_facts",
        "ts": _now_iso(),
        "findings": findings,
        "drift": len(findings) > 0,
    }


def detect_agora_bypass(workspace_root: Path) -> dict[str, Any]:
    bypass_patterns: list[dict[str, str]] = []
    forbidden_imports = (
        "from openai import",
        "import openai",
        "from anthropic import",
        "import anthropic",
        "from vertexai",
        "import vertexai",
    )
    scanned_files = [
        "projects/runtime/src/runtime/executor/engine.py",
        "projects/cockpit/src/cockpit/commands/scenario.py",
        "projects/runtime/src/runtime/executor/config/__init__.py",
    ]
    for rel in scanned_files:
        try:
            content = _read(workspace_root, rel)
        except FileNotFoundError:
            continue
        for pattern in forbidden_imports:
            if pattern in content:
                bypass_patterns.append({"file": rel, "pattern": pattern})
    return {
        "kind": "agora_bypass",
        "ts": _now_iso(),
        "scanned_files": scanned_files,
        "bypass_patterns": bypass_patterns,
        "drift": len(bypass_patterns) > 0,
    }


def build_drift_report(workspace_root: Path) -> dict[str, Any]:
    results = [
        detect_entry_drift(workspace_root),
        detect_doc_drift(workspace_root),
        detect_duplicate_facts(workspace_root),
        detect_agora_bypass(workspace_root),
    ]
    return {
        "generated_at": _now_iso(),
        "kinds": len(results),
        "drift_count": sum(1 for item in results if item["drift"]),
        "results": results,
    }


def write_drift_report(workspace_root: Path, report: dict[str, Any]) -> Path:
    out_dir = workspace_root / ".omo" / "_control" / "evolution" / "drift"
    out_path = out_dir / f"{datetime.now(UTC).strftime('%Y-%m-%dT%H%M%S')}.json"
    write_text_atomic(
        out_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    return out_path
