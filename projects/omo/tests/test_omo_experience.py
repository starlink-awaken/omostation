from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

import yaml

# Ensure Workspace root is on sys.path for scripts.* imports
_ws_root = Path(__file__).resolve().parents[2]
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))

from scripts.cost_track_org import cost_summary_by_org
from omo.omo_experience import (
    bridge_request_to_task,
    build_session_bootstrap,
    evaluate_control_gate,
    record_confirmation_evidence,
    route_request_with_control_gate,
    write_freshness_report,
    write_resource_accounting_report,
)
from omo.omo_task_schema import validate_task_file


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_session_bootstrap_reads_live_phase_and_active_packet(tmp_path: Path):
    root = tmp_path
    _write_yaml(
        root / ".omo" / "state" / "system.yaml",
        {
            "current_phase": 7,
            "phase_status": "in_progress",
            "current_wave": 1,
            "next_milestone": "Phase 7 Wave 1 user journey enablement",
            "divergence_flags": ["orphaned_tasks:1"],
        },
    )
    _write_yaml(
        root / ".omo" / "goals" / "current.yaml",
        {
            "phase": 7,
            "status": "in_progress",
            "current_wave": 1,
            "goals": [{"id": "G7.1", "status": "in_progress", "tasks": ["P7-W1-USER-JOURNEY-ENABLEMENT"]}],
        },
    )
    _write_yaml(
        root / ".omo" / "tasks" / "active" / "wave1.yaml",
        {
            "id": "P7-W1-USER-JOURNEY-ENABLEMENT",
            "title": "Land the Phase 7 Wave 1 user journey enablement packet",
            "status": "pending",
        },
    )
    _write_text(root / ".omo" / "summaries" / "phase7-planning-ratification.md", "# ratified\n")

    bootstrap = build_session_bootstrap(root)

    assert bootstrap["phase"] == 7
    assert bootstrap["wave"] == 1
    assert bootstrap["active_task_ids"] == ["P7-W1-USER-JOURNEY-ENABLEMENT"]
    assert bootstrap["divergence_flags"] == ["orphaned_tasks:1"]
    assert bootstrap["latest_summary_ref"] == ".omo/summaries/phase7/phase7-planning-ratification.md"


def test_bridge_request_to_task_creates_governed_blocked_packet(tmp_path: Path):
    root = tmp_path
    _write_yaml(root / ".omo" / "goals" / "current.yaml", {"phase": 7, "current_wave": 1})

    result = bridge_request_to_task(
        root,
        task_id="P7-W1-COMPLEX-REQUEST",
        title="Bridge a complex Wave 1 request",
        request_text="Please推进phase7 wave1并完成一次治理整改。",
        source_docs=[".omo/plans/phase7-starter-packet-spec.md"],
    )

    task_path = root / result["task_ref"]
    task = _load_yaml(task_path)
    assert result["classification"] == "complex_task"
    assert task["phase"] == 7
    assert task["milestone"] == "W1"
    assert task["status"] == "blocked"
    assert task["source_docs"] == [".omo/plans/phase7-starter-packet-spec.md"]
    assert validate_task_file(task_path) == []


def test_record_confirmation_evidence_attaches_delivery_ref_to_task(tmp_path: Path):
    root = tmp_path
    task_path = root / ".omo" / "tasks" / "active" / "wave1.yaml"
    _write_yaml(
        task_path,
        {
            "id": "P7-W1-USER-JOURNEY-ENABLEMENT",
            "title": "Land Wave 1",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/phase7-starter-packet-spec.md"],
            "deliverables": [],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["user confirmation captured"],
            "test_plan": ["pytest -q"],
        },
    )

    result = record_confirmation_evidence(
        root,
        task_id="P7-W1-USER-JOURNEY-ENABLEMENT",
        message="可以，继续推进吧",
        now="2026-05-31T09:30:00Z",
    )

    evidence_path = root / result["evidence_ref"]
    evidence = _load_yaml(evidence_path)
    task = _load_yaml(task_path)
    assert evidence["task_id"] == "P7-W1-USER-JOURNEY-ENABLEMENT"
    assert evidence["classification"] == "positive_confirmation"
    assert evidence["message"] == "可以，继续推进吧"
    assert result["evidence_ref"] in task["handoff_refs"]


def test_write_resource_accounting_report_persists_truth_and_summary(tmp_path: Path, monkeypatch):
    root = tmp_path
    _write_yaml(
        root / ".omo" / "state" / "system.yaml",
        {"current_phase": 7, "current_wave": 2, "active_tasks": 1, "blocked_tasks": 0, "completed_tasks": 2},
    )
    _write_yaml(
        root / ".omo" / "workers" / "runs" / "dispatch-one-dispatch.yaml",
        {
            "task_id": "P7-W1-USER-JOURNEY-ENABLEMENT",
            "worker_id": "mockworker",
            "dispatch_state": "completed",
            "launched_at": "2026-05-31T09:00:00Z",
        },
    )

    monkeypatch.setattr(
        "scripts.omo_experience.cost_summary_by_org",
        lambda days=7: [{"org": "starlink-core", "calls": 3, "cost": 1.25, "tokens": 2048}],
    )

    result = write_resource_accounting_report(root, now="2026-05-31T09:45:00Z")

    registry = _load_yaml(root / result["registry_ref"])
    summary_text = (root / result["summary_ref"]).read_text(encoding="utf-8")
    assert registry["current_phase"] == 7
    assert registry["dispatches"]["total"] == 1
    assert registry["cost_by_org"][0]["org"] == "starlink-core"
    assert "starlink-core" in summary_text
    assert "$1.25" in summary_text


def test_write_freshness_report_scores_staleness_and_refs(tmp_path: Path):
    root = tmp_path
    _write_yaml(
        root / ".omo" / "state" / "system.yaml",
        {
            "current_phase": 7,
            "current_wave": 3,
            "divergence_flags": ["orphaned_tasks:1"],
            "updated_at": "2026-05-31T08:00:00Z",
        },
    )
    _write_yaml(root / ".omo" / "goals" / "current.yaml", {"phase": 7, "current_wave": 3})
    _write_yaml(
        root / ".omo" / "tasks" / "active" / "wave3.yaml",
        {
            "id": "P7-W3-FRESHNESS-ENTROPY-AUTOMATION",
            "title": "Land freshness automation",
            "status": "pending",
        },
    )
    _write_text(root / ".omo" / "summaries" / "phase7-planning-ratification.md", "# ratified\n")

    result = write_freshness_report(root, now="2026-05-31T10:00:00Z")

    report = _load_yaml(root / result["report_ref"])
    summary_text = (root / result["summary_ref"]).read_text(encoding="utf-8")
    assert report["current_phase"] == 7
    assert report["stale_items"] == ["state_update_stale", "orphaned_tasks:1"]
    assert report["freshness_score"] < 100
    assert "state_update_stale" in summary_text
    assert "orphaned_tasks:1" in summary_text


def test_cost_summary_by_org_migrates_existing_usage_db_without_org(tmp_path: Path, monkeypatch):
    usage_db = tmp_path / "usage.db"
    conn = sqlite3.connect(usage_db)
    conn.execute(
        """
        CREATE TABLE resource_usage (
            call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT NOT NULL,
            service TEXT NOT NULL,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO resource_usage (caller, service, tokens_input, tokens_output, cost_usd, timestamp)
        VALUES ('copilot-cli', 'bridge', 100, 0, 1.25, datetime('now'))
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("scripts.cost_track_org.USAGE_DB", usage_db)

    summary = cost_summary_by_org(days=7)

    assert summary == [{"org": "starlink-core", "calls": 1, "cost": 1.25, "tokens": 100}]


def test_control_gate_blocks_when_budget_is_exceeded(tmp_path: Path) -> None:
    root = tmp_path
    _write_yaml(
        root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml",
        {
            "cost_by_org": [{"org": "starlink-core", "cost": 5.0, "calls": 10, "tokens": 3000}],
            "dispatches": {"total": 2, "workers": {"mockworker": 2}},
        },
    )
    _write_yaml(
        root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml",
        {
            "freshness_score": 92,
            "stale_items": [],
        },
    )

    decision = evaluate_control_gate(root, budget_limit_usd=2.5)

    assert decision["decision"] == "block"
    assert "budget_limit_exceeded" in decision["reasons"]


def test_control_gate_degrades_on_warning_freshness(tmp_path: Path) -> None:
    root = tmp_path
    _write_yaml(
        root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml",
        {
            "cost_by_org": [{"org": "starlink-core", "cost": 1.0, "calls": 2, "tokens": 512}],
            "dispatches": {"total": 1, "workers": {"mockworker": 1}},
        },
    )
    _write_yaml(
        root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml",
        {
            "freshness_score": 72,
            "stale_items": ["state_update_stale"],
        },
    )

    decision = evaluate_control_gate(root, budget_limit_usd=2.5, warning_score=80, critical_score=50)

    assert decision["decision"] == "degrade"
    assert "freshness_warning" in decision["reasons"]


def test_route_request_with_control_gate_writes_decision_and_routes_task(tmp_path: Path) -> None:
    root = tmp_path
    _write_yaml(root / ".omo" / "goals" / "current.yaml", {"phase": 8, "current_wave": 1})
    _write_yaml(
        root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml",
        {
            "cost_by_org": [{"org": "starlink-core", "cost": 0.9, "calls": 1, "tokens": 256}],
            "dispatches": {"total": 1, "workers": {"mockworker": 1}},
        },
    )
    _write_yaml(
        root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml",
        {
            "freshness_score": 95,
            "stale_items": [],
        },
    )

    result = route_request_with_control_gate(
        root,
        task_id="P8-W1-CONTROLLED-REQUEST",
        title="Control-routed request",
        request_text="Please execute a complex controlled request",
        source_docs=[".omo/plans/phase8-starter-packet-spec.md"],
        budget_limit_usd=2.5,
    )

    assert result["decision"] == "allow"
    assert (root / result["decision_ref"]).exists()
    assert (root / result["task_ref"]).exists()
