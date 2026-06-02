from __future__ import annotations

import os
import shutil
import sys
import subprocess
from pathlib import Path

import yaml
import pytest

from scripts.omo_governance import approve_truth_mutation, apply_truth_mutation
from scripts.omo_handoff_index import write_handoff_index
from scripts.omo_metrics import write_worker_utilization_summary
from scripts.omo_io import write_text_atomic, write_yaml_atomic
from scripts.omo_provider_plane import write_provider_plane_snapshot
from scripts.omo_redaction import redact_sensitive_text
from scripts.omo_worker import (
    _build_launch_argv,
    collect_worker_status,
    dispatch_task,
    main as omo_worker_main,
    reclaim_task,
    scan_runtime_watchdog,
    update_dispatch_checkpoint,
)
from scripts.omo_task_schema import validate_task_file
from scripts.sync_omo_state import sync_state


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_debt_registry_fixture(omo: Path, items: list[dict]) -> None:
    debt_dir = omo / "debt"
    (debt_dir / "items").mkdir(parents=True, exist_ok=True)
    (debt_dir / "dashboard").mkdir(parents=True, exist_ok=True)
    (debt_dir / "reviews").mkdir(parents=True, exist_ok=True)
    seed_items: list[str] = []
    for item in items:
        item_path = debt_dir / "items" / f"{item['id']}.yaml"
        _write_yaml(item_path, item)
        seed_items.append(f".omo/debt/items/{item['id']}.yaml")
    _write_yaml(
        debt_dir / "registry.yaml",
        {
            "version": 1,
            "items_dir": ".omo/debt/items",
            "dashboard_ref": ".omo/debt/dashboard/current.yaml",
            "review_pack_ref": ".omo/debt/reviews/current.md",
            "review_queue_ref": ".omo/debt/review-queue/current.yaml",
            "action_packet_ref": ".omo/debt/action-packet/current.yaml",
            "owner_routing_ref": ".omo/debt/owner-routing/current.yaml",
            "dispatch_ref": ".omo/debt/dispatch/current.yaml",
            "campaign_ref": ".omo/debt/campaign/current.yaml",
            "reporting_ref": ".omo/debt/reporting/current.yaml",
            "seed_items": seed_items,
        },
    )


def test_sync_state_ignores_gated_future_phase_tasks_in_goal_divergence(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 6,
            "goals": [
                {"id": "G6.1", "status": "in_progress", "tasks": ["TASK-ACTIVE"]},
                {"id": "G6.2", "status": "gated", "tasks": ["TASK-GATED"]},
            ],
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "TASK-ACTIVE",
            "phase": 6,
            "status": "pending",
        },
    )

    state = sync_state(omo, test_output="1 passed")

    assert state["divergence_flags"] == []


def test_sync_state_ignores_orphaned_tasks_from_other_phases(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 6,
            "goals": [
                {"id": "G6.1", "status": "in_progress", "tasks": ["TASK-P6"]},
            ],
        },
    )
    _write_yaml(omo / "tasks" / "active" / "task.yaml", {"id": "TASK-P6", "phase": 6, "status": "pending"})
    _write_yaml(omo / "tasks" / "done" / "legacy.yaml", {"id": "TASK-P4", "phase": 4, "status": "done"})

    state = sync_state(omo, test_output="1 passed")

    assert state["divergence_flags"] == []


def test_sync_state_ignores_unphased_historical_done_tasks(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 6,
            "goals": [
                {"id": "G6.1", "status": "completed", "tasks": ["TASK-P6"]},
            ],
        },
    )
    _write_yaml(omo / "tasks" / "done" / "current.yaml", {"id": "TASK-P6", "phase": 6, "status": "done"})
    _write_yaml(omo / "tasks" / "done" / "legacy.yaml", {"id": "TASK-LEGACY", "status": "done"})

    state = sync_state(omo, test_output="1 passed")

    assert state["divergence_flags"] == []


def test_sync_state_derives_current_wave_and_phase_status_from_goals(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "current_phase": 11,
            "current_wave": 1,
            "phase_status": "active",
            "phase11_status": "wave1_active",
            "next_milestone": "Phase 11 Wave 2 gate",
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 11,
            "status": "active",
            "current_wave": 2,
            "next_milestone": "Phase 11 Wave 2 exit gate",
            "goals": [
                {"id": "G11.1", "status": "completed", "tasks": ["P11-W1-SSOT-BASELINE"]},
                {"id": "G11.2", "status": "active", "tasks": ["P11-W2-CORE-DEBT"]},
            ],
        },
    )
    _write_yaml(omo / "tasks" / "done" / "w1.yaml", {"id": "P11-W1-SSOT-BASELINE", "phase": 11, "status": "done"})
    _write_yaml(
        omo / "tasks" / "active" / "w2.yaml",
        {
            "id": "P11-W2-CORE-DEBT",
            "phase": 11,
            "status": "in_progress",
            "dispatch_id": "dispatch-2",
            "run_ref": ".omo/workers/runs/dispatch-2.yaml",
            "review_ref": ".omo/workers/runs/review-2.md",
            "assigned_to": "worker-1",
            "knowledge_refs": [],
            "handoff_refs": [],
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-2.yaml",
        {
            "task_id": "P11-W2-CORE-DEBT",
            "dispatch_state": "active",
            "launched_at": "2026-06-01T00:00:00Z",
            "lease": {
                "lease_expired_after_seconds": 1200,
                "last_checkpoint_at": "2026-06-01T00:00:00Z",
                "last_material_write_at": "2026-06-01T00:00:00Z",
            },
        },
    )
    (omo / "workers" / "runs" / "review-2.md").parent.mkdir(parents=True, exist_ok=True)
    (omo / "workers" / "runs" / "review-2.md").write_text("# review\n", encoding="utf-8")

    state = sync_state(omo, test_output="1 passed", now="2026-06-01T00:00:00Z")

    assert state["current_phase"] == 11
    assert state["current_wave"] == 2
    assert state["phase_status"] == "active"
    assert state["phase11_status"] == "wave2_active"
    assert state["next_milestone"] == "Phase 11 Wave 2 exit gate"


def test_sync_state_derives_debt_summary_from_registry(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(
        omo,
        [
            {
                "id": "LEDGER_ALPHA",
                "title": "Ledger alpha title",
                "dimension": "architecture",
                "subdimension": "boundaries",
                "domain": "workspace",
                "scope": "cross_project",
                "severity": "high",
                "weight": 0.4,
                "entropy_class": "coupling",
                "lifecycle_state": "identified",
                "owner": "platform-governance",
                "affected_roots": ["projects/demo"],
                "evidence_refs": [".omo/_knowledge/design/demo.md"],
                "mitigation_refs": [".omo/_knowledge/design/demo.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "watchlist",
                "history": [],
            },
            {
                "id": "LEDGER_BETA",
                "title": "Ledger beta title",
                "dimension": "governance_process",
                "subdimension": "ssot",
                "domain": ".omo",
                "scope": "governance_kernel",
                "severity": "medium",
                "weight": 0.6,
                "entropy_class": "pointer",
                "lifecycle_state": "classified",
                "owner": "omo-governance",
                "affected_roots": [".omo/state"],
                "evidence_refs": [".omo/state/system.yaml"],
                "mitigation_refs": [".omo/tasks/registry/INDEX.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "none",
                "history": [],
            },
        ],
    )
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["debt_registry_ref"] == ".omo/debt/registry.yaml"
    assert state["debt_dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert state["debt_review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert state["debt_metrics"]["debt_health"] < 100
    assert state["debt_metrics"]["pointer_entropy"] > 0
    assert state["resolved_debt_items"] == []
    assert list(state["debt_weight_items"]) == [
        "LEDGER_ALPHA",
        "LEDGER_BETA",
    ]
    assert state["debt_weight_items"]["LEDGER_ALPHA"]["desc"] == "Ledger alpha title"
    assert state["debt_weight_items"]["LEDGER_BETA"]["weight"] == 0.6
    assert state["debt_weight"] == 0.3


def test_sync_state_promotes_debt_reporting_ref_but_not_campaign_ref(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(
        omo,
        [
            {
                "id": "LEDGER_ALPHA",
                "title": "Ledger alpha title",
                "dimension": "architecture",
                "subdimension": "boundaries",
                "domain": "workspace",
                "scope": "cross_project",
                "severity": "high",
                "weight": 0.4,
                "entropy_class": "coupling",
                "lifecycle_state": "identified",
                "owner": "platform-governance",
                "affected_roots": ["projects/demo"],
                "evidence_refs": [".omo/_knowledge/design/demo.md"],
                "mitigation_refs": [".omo/_knowledge/design/demo.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "watchlist",
                "history": [],
            }
        ],
    )
    for rel_path in (
        "debt/dashboard/current.yaml",
        "debt/reviews/current.md",
        "debt/review-queue/current.yaml",
        "debt/action-packet/current.yaml",
        "debt/owner-routing/current.yaml",
        "debt/dispatch/current.yaml",
        "debt/campaign/current.yaml",
        "debt/reporting/current.yaml",
    ):
        path = omo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n", encoding="utf-8")
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["debt_reporting_ref"] == ".omo/debt/reporting/current.yaml"
    assert "debt_campaign_ref" not in state


def test_sync_state_flags_missing_debt_generated_refs(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(omo, [])
    (omo / "debt" / "dashboard").mkdir(parents=True, exist_ok=True)
    (omo / "debt" / "dashboard" / "current.yaml").write_text("generated\n", encoding="utf-8")
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert any(flag.startswith("missing_debt_generated_ref:") for flag in state["divergence_flags"])
    assert "debt_generated_refs" in state["divergence_detail_refs"]


def test_sync_state_uses_fixture_root_when_registry_refs_are_current(
    tmp_path: Path,
) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(
        omo,
        [
            {
                "id": "LEDGER_CURRENT",
                "title": "Ledger current title",
                "dimension": "architecture",
                "subdimension": "boundaries",
                "domain": "workspace",
                "scope": "cross_project",
                "severity": "high",
                "weight": 0.4,
                "entropy_class": "coupling",
                "lifecycle_state": "classified",
                "owner": "platform-governance",
                "affected_roots": ["projects/demo"],
                "evidence_refs": [".omo/_knowledge/design/demo.md"],
                "mitigation_refs": [".omo/tasks/registry/INDEX.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": "2026-06-10T00:00:00Z",
                "next_review_at": "2026-06-20T00:00:00Z",
                "gate_level": "none",
                "history": [],
            }
        ],
    )
    (omo / "_knowledge" / "design").mkdir(parents=True, exist_ok=True)
    (omo / "_knowledge" / "design" / "demo.md").write_text("updated evidence\n", encoding="utf-8")
    (omo / "tasks" / "registry").mkdir(parents=True, exist_ok=True)
    (omo / "tasks" / "registry" / "INDEX.md").write_text("mitigation\n", encoding="utf-8")
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["debt_metrics"]["pointer_entropy"] == 0.0
    assert state["debt_metrics"]["time_entropy"] == 0.0


def test_sync_state_uses_registry_items_for_debt_weight(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(
        omo,
        [
            {
                "id": "LEDGER_ALPHA",
                "title": "Ledger alpha title",
                "dimension": "architecture",
                "subdimension": "boundaries",
                "domain": "workspace",
                "scope": "cross_project",
                "severity": "high",
                "weight": 0.4,
                "entropy_class": "coupling",
                "lifecycle_state": "closed",
                "owner": "platform-governance",
                "affected_roots": ["projects/demo"],
                "evidence_refs": [".omo/_knowledge/design/demo.md"],
                "mitigation_refs": [".omo/_knowledge/design/demo.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "watchlist",
                "history": [],
            },
            {
                "id": "LEDGER_BETA",
                "title": "Ledger beta title",
                "dimension": "governance_process",
                "subdimension": "ssot",
                "domain": ".omo",
                "scope": "governance_kernel",
                "severity": "medium",
                "weight": 0.6,
                "entropy_class": "pointer",
                "lifecycle_state": "classified",
                "owner": "omo-governance",
                "affected_roots": [".omo/state"],
                "evidence_refs": [".omo/state/system.yaml"],
                "mitigation_refs": [".omo/tasks/registry/INDEX.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "none",
                "history": [],
            },
        ],
    )
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "health_score": 0.0,
            "resolved_debt_items": ["D2_CI_E2E", "D3_EU_PRICING"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["resolved_debt_items"] == ["LEDGER_ALPHA"]
    assert state["debt_weight"] == 0.4


def test_sync_state_falls_back_to_legacy_debt_items_without_registry(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "health_score": 0.0,
            "resolved_debt_items": ["D2_CI_E2E"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert "debt_registry_ref" not in state
    assert "debt_metrics" not in state
    assert list(state["debt_weight_items"]) == [
        "D2_CI_E2E",
        "D3_EU_PRICING",
        "SB_DECOMPOSITION",
        "SB_UNTESTED_PKGS",
        "SB_ORPHANED_TASKS",
        "SB_ROOT_CLEANUP",
        "SB_BRIDGE_FIX",
        "SB_PROJECTS_YAML",
        "SB_PHASE17_PLAN",
    ]
    assert state["debt_weight_items"]["D2_CI_E2E"]["resolved"] is True


def test_write_yaml_atomic_persists_payload_without_leaking_tmp_files(tmp_path: Path):
    target = tmp_path / ".omo" / "state" / "system.yaml"

    write_yaml_atomic(target, {"phase_status": "planning", "active_tasks": 0})

    assert yaml.safe_load(target.read_text(encoding="utf-8")) == {
        "phase_status": "planning",
        "active_tasks": 0,
    }
    assert list(target.parent.glob("*.tmp")) == []


def test_write_text_atomic_replaces_file_in_single_final_path(tmp_path: Path):
    target = tmp_path / ".omo" / "workers" / "runs" / "sample-review.md"

    write_text_atomic(target, "# Review Note\n\nOK\n")

    assert target.read_text(encoding="utf-8") == "# Review Note\n\nOK\n"
    assert list(target.parent.glob("*.tmp")) == []


def test_sync_omo_state_script_runs_from_repo_root(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": []})
    for group in ("active", "blocked", "done"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, "scripts/sync_omo_state.py", "--omo-dir", str(omo)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_redact_sensitive_text_masks_token_secret_and_password_pairs():
    text = "token=abc123\nsecret: topsecret\npassword=hunter2\napi_key=xyz"

    masked = redact_sensitive_text(text)

    assert "abc123" not in masked
    assert "topsecret" not in masked
    assert "hunter2" not in masked
    assert "xyz" not in masked
    assert masked.count("***REDACTED***") == 4


def test_build_launch_argv_rejects_shell_control_sequences():
    registry = {
        "workers": [
            {
                "id": "unsafe",
                "transports": {
                    "cli_prompt": {"command": 'python worker.py "{prompt}"; rm -rf /'}
                },
            }
        ]
    }

    with pytest.raises(ValueError, match="unsafe worker command template"):
        _build_launch_argv(registry, "unsafe", "cli_prompt", "hello")


def test_dispatch_task_launch_redacts_stdout_log(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "redact.yaml",
        {
            "id": "TASK-REDACT",
            "title": "Redact launch output",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["stdout redacted"],
            "test_plan": ["inspect stdout log"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {
                            "command": 'python3 -c "print(\'token=abc123\\npassword=hunter2\')" "{prompt}"'
                        }
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-REDACT",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=True,
    )

    stdout_text = (root / ".omo" / "workers" / "runs" / f"{result['dispatch_id']}-stdout.log").read_text(encoding="utf-8")
    assert "abc123" not in stdout_text
    assert "hunter2" not in stdout_text
    assert stdout_text.count("***REDACTED***") == 2


def test_write_provider_plane_snapshot_redacts_sensitive_strings(tmp_path: Path):
    snapshot_path = tmp_path / ".omo" / "state" / "provider-plane.yaml"

    write_provider_plane_snapshot(
        snapshot_path,
        selected_provider={
            "name": "primary",
            "notes": "token=abc123 secret=topsecret password=hunter2 api_key=xyz",
            "api_key": "should-not-be-written",
        },
        quota_summary={"provider_count": 1},
        litellm_health={"healthy_count": 1, "unhealthy_count": 0},
    )

    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    assert "abc123" not in snapshot_text
    assert "topsecret" not in snapshot_text
    assert "hunter2" not in snapshot_text
    assert "xyz" not in snapshot_text


def test_sync_state_updates_counts_health_and_divergence_flags(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(omo / "tasks" / "active" / "a.yaml", {"id": "TASK-A", "phase": 6, "status": "in_progress"})
    _write_yaml(omo / "tasks" / "blocked" / "b.yaml", {"id": "TASK-B", "phase": 6})
    _write_yaml(omo / "tasks" / "done" / "c.yaml", {"id": "TASK-C"})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 6,
            "goals": [
                {"id": "G1", "tasks": ["TASK-A", "TASK-C", "TASK-MISSING"]},
            ]
        },
    )

    sync_state(omo, test_output="3 passed, 1 failed")

    state = _load_yaml(omo / "state" / "system.yaml")
    assert state["active_tasks"] == 1
    assert state["blocked_tasks"] == 1
    assert state["completed_tasks"] == 1
    assert state["total_tasks"] == 3
    assert state["health_score_raw"] == 75.0
    assert state["debt_weight"] == 0.3
    assert state["health_score"] == 22.5
    assert state["divergence_flags"] == [
        "missing_goal_tasks:1",
        "orphaned_tasks:1",
        "active_task_missing_run_ref:TASK-A",
        "active_task_missing_review_ref:TASK-A",
    ]
    missing_goal_detail = state["divergence_detail_refs"]["missing_goal_tasks"]
    orphaned_detail = state["divergence_detail_refs"]["orphaned_tasks"]
    assert missing_goal_detail["count"] == 1
    assert orphaned_detail["count"] == 1
    assert _load_yaml(tmp_path / missing_goal_detail["ref"])["task_ids"] == ["TASK-MISSING"]
    assert _load_yaml(tmp_path / orphaned_detail["ref"])["task_ids"] == ["TASK-B"]
    assert state["next_active_tasks"][0] == "Current active queue from .omo/tasks/active/ (1 task)"


def test_sync_state_uses_custom_omo_root_for_divergence_artifacts_and_headers(tmp_path: Path):
    omo = tmp_path / ".kos"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(omo / "tasks" / "active" / "a.yaml", {"id": "TASK-A", "phase": 8, "status": "pending"})
    _write_yaml(omo / "tasks" / "blocked" / "b.yaml", {"id": "TASK-B", "phase": 8})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 8,
            "goals": [{"id": "G8.2", "status": "in_progress", "tasks": ["TASK-A", "TASK-MISSING"]}],
        },
    )

    state = sync_state(omo, test_output="1 passed")

    assert state["next_active_tasks"][0] == "Current active queue from .kos/tasks/active/ (1 task)"
    assert state["divergence_detail_refs"]["missing_goal_tasks"]["ref"] == ".kos/evidence/divergence/missing_goal_tasks.yaml"
    assert state["divergence_detail_refs"]["orphaned_tasks"]["ref"] == ".kos/evidence/divergence/orphaned_tasks.yaml"
    assert (tmp_path / ".kos" / "evidence" / "divergence" / "missing_goal_tasks.yaml").exists()


def test_sync_state_removes_stale_orphaned_task_artifact_when_divergence_is_resolved(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(
        omo / "goals" / "current.yaml",
        {
            "phase": 11,
            "goals": [{"id": "G11.2", "status": "active", "tasks": ["P11-W2-CORE-DEBT"]}],
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "P11-W2-CORE-DEBT",
            "phase": 11,
            "status": "pending",
        },
    )
    stale_artifact = omo / "evidence" / "divergence" / "orphaned_tasks.yaml"
    _write_yaml(stale_artifact, {"count": 1, "task_ids": ["P8-W1-CONTROLLED-REQUEST"]})

    state = sync_state(omo, test_output="1 passed")

    assert "orphaned_tasks" not in state["divergence_detail_refs"]
    assert stale_artifact.exists() is False


def test_dispatch_task_and_worker_status_use_custom_omo_root(tmp_path: Path):
    root = tmp_path
    omo = root / ".kos"

    _write_yaml(
        omo / "tasks" / "active" / "custom.yaml",
        {
            "id": "TASK-CUSTOM-OMO",
            "title": "Custom OMO root task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".kos/plans/source.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["custom storage root respected"],
            "test_plan": ["inspect dispatch artifacts"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-CUSTOM-OMO",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=False,
        omo_dir=".kos",
    )

    task = _load_yaml(omo / "tasks" / "active" / "custom.yaml")
    status = collect_worker_status(root, omo_dir=".kos")

    assert result["dispatch_path"].startswith(".kos/workers/runs/")
    assert result["review_path"].startswith(".kos/workers/runs/")
    assert task["run_ref"].startswith(".kos/workers/runs/")
    assert task["review_ref"].startswith(".kos/workers/runs/")
    assert status["active_dispatches"] == 1
    assert status["runs"][0]["task_id"] == "TASK-CUSTOM-OMO"


def test_dispatch_task_uses_supplied_now_for_dispatch_identity_and_start_time(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "timed.yaml",
        {
            "id": "TASK-TIMED",
            "title": "Deterministic dispatch timestamp",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/source.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["dispatch timestamp deterministic"],
            "test_plan": ["inspect dispatch artifacts"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}},
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        "TASK-TIMED",
        "mockworker",
        ["src/app.py"],
        launch=False,
        now="2026-06-03T07:05:00Z",
    )

    task = _load_yaml(omo / "tasks" / "active" / "timed.yaml")
    dispatch = _load_yaml(root / result["dispatch_path"])

    assert result["dispatch_id"].endswith("20260603-070500")
    assert dispatch["launched_at"] == "2026-06-03T07:05:00Z"
    assert task["started_at"] == "2026-06-03T07:05:00Z"


def test_install_all_bridges_defaults_to_wrapper_only_without_running_legacy_installers(tmp_path: Path):
    home = tmp_path / "home"
    workspace = home / "Workspace" / "demo" / "scripts"
    workspace.mkdir(parents=True, exist_ok=True)
    installer = workspace / "install-hermes-bridge.sh"
    installer.write_text(
        "#!/bin/bash\nset -euo pipefail\ntouch \"$HOME/legacy-installer-ran\"\n",
        encoding="utf-8",
    )
    installer.chmod(0o755)

    result = subprocess.run(
        ["bash", "scripts/install-all-bridges.sh"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert not (home / "legacy-installer-ran").exists()
    assert "wrapper-only" in result.stdout


def test_install_all_bridges_can_opt_into_legacy_installers(tmp_path: Path):
    home = tmp_path / "home"
    workspace = home / "Workspace" / "demo" / "scripts"
    workspace.mkdir(parents=True, exist_ok=True)
    installer = workspace / "install-hermes-bridge.sh"
    installer.write_text(
        "#!/bin/bash\nset -euo pipefail\ntouch \"$HOME/legacy-installer-ran\"\n",
        encoding="utf-8",
    )
    installer.chmod(0o755)

    result = subprocess.run(
        ["bash", "scripts/install-all-bridges.sh", "--legacy-installers"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (home / "legacy-installer-ran").exists()


def test_sync_state_flags_stale_dispatch_and_writes_detail_artifact(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-STALE"]}]})
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "TASK-STALE",
            "status": "in_progress",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/dispatch-1-dispatch.yaml",
            "review_ref": ".omo/workers/runs/dispatch-1-review.md",
            "assigned_to": "mockworker",
            "knowledge_refs": [],
            "handoff_refs": [],
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-1-dispatch.yaml",
        {
            "task_id": "TASK-STALE",
            "dispatch_state": "dispatched",
            "launched_at": "2026-05-31T00:00:00Z",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "last_checkpoint_at": "2026-05-31T00:00:00Z",
                "last_material_write_at": "2026-05-31T00:00:00Z",
            },
        },
    )

    state = sync_state(omo, test_output="1 passed", now="2026-05-31T00:05:00Z")

    assert "stale_dispatch:TASK-STALE" in state["divergence_flags"]
    detail = state["divergence_detail_refs"]["stale_dispatches"]
    assert detail["count"] == 1
    assert _load_yaml(tmp_path / detail["ref"])["task_ids"] == ["TASK-STALE"]


def test_sync_state_records_dangling_refs_for_missing_run_review_and_handoff_files(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-1"]}]})
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "TASK-1",
            "status": "review",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/missing-dispatch.yaml",
            "review_ref": ".omo/workers/runs/missing-review.md",
            "assigned_to": "mockworker",
            "knowledge_refs": [".omo/_knowledge/design/missing.md"],
            "handoff_refs": [".omo/workers/runs/missing-review.md"],
        },
    )

    state = sync_state(omo, test_output="1 passed")

    assert "dangling_refs:TASK-1" in state["divergence_flags"]
    detail = state["divergence_detail_refs"]["dangling_refs"]
    payload = _load_yaml(tmp_path / detail["ref"])
    assert payload["task_ids"] == ["TASK-1"]
    assert "missing-review.md" in "\n".join(payload["missing_refs"])


def test_sync_state_clears_stale_active_queue_when_no_active_tasks(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 4,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 4,
            "health_score": 0.0,
            "next_active_tasks": [
                "Current active queue from .omo/tasks/active/ (4 tasks)",
                "P4-W2-DIVERGENCE-TRIAGE",
                "P4-W2-HANDOFF-INDEX",
            ],
        },
    )
    _write_yaml(omo / "tasks" / "done" / "done.yaml", {"id": "TASK-DONE", "status": "done"})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-DONE"]}]})

    sync_state(omo, test_output="1 passed")

    state = _load_yaml(omo / "state" / "system.yaml")
    assert state["active_tasks"] == 0
    assert state["next_active_tasks"] == ["(No active tasks)"]


def test_sync_state_drops_stale_task_lines_from_next_active_queue(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "health_score": 0.0,
            "next_active_tasks": [
                "Current active queue from .omo/tasks/active/ (1 task)",
                "P11-W2-CORE-DEBT",
                "P11-W1-SSOT-BASELINE",
                "Phase 11 debt burn in progress",
            ],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 11, "goals": [{"id": "G11.2", "tasks": ["P11-W2-CORE-DEBT"]}]})
    _write_yaml(
        omo / "tasks" / "active" / "w2.yaml",
        {"id": "P11-W2-CORE-DEBT", "phase": 11, "status": "in_progress", "run_ref": "run.yaml", "review_ref": "review.md"},
    )

    state = sync_state(omo, test_output="1 passed")

    assert state["next_active_tasks"] == [
        "Current active queue from .omo/tasks/active/ (1 task)",
        "P11-W2-CORE-DEBT",
        "Phase 11 debt burn in progress",
    ]


def test_sync_state_tracks_planned_tasks_and_preview(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 16, "status": "completed", "goals": []})
    _write_yaml(
        omo / "tasks" / "active" / "gate.yaml",
        {"id": "P17-DEBT-GOVERNANCE-GATE-RULES", "phase": 17, "status": "in_progress", "run_ref": "run.yaml", "review_ref": "review.md"},
    )
    _write_yaml(omo / "tasks" / "planned" / "p18.yaml", {"id": "P18-W1-NEURAL-CENTER", "phase": 18, "status": "pending"})
    _write_yaml(
        omo / "tasks" / "planned" / "p19.yaml",
        {"id": "P19-W1-AGENT-RUNTIME-ENHANCE", "phase": 19, "status": "pending"},
    )
    _write_yaml(omo / "tasks" / "blocked" / "blocked.yaml", {"id": "TASK-BLOCKED", "phase": 16})
    _write_yaml(omo / "tasks" / "done" / "done.yaml", {"id": "TASK-DONE", "phase": 16, "status": "done"})

    state = sync_state(omo, test_output="5 passed")

    assert state["active_tasks"] == 1
    assert state["planned_tasks"] == 2
    assert state["blocked_tasks"] == 1
    assert state["completed_tasks"] == 1
    assert state["total_tasks"] == 5
    assert state["next_active_tasks"] == [
        "Current active queue from .omo/tasks/active/ (1 task)",
        "P17-DEBT-GOVERNANCE-GATE-RULES",
    ]
    assert state["next_planned_tasks"] == [
        "Current planned queue from .omo/tasks/planned/ (2 tasks)",
        "P18-W1-NEURAL-CENTER",
        "P19-W1-AGENT-RUNTIME-ENHANCE",
    ]


def test_sync_state_drops_stale_active_headers_when_count_changes(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "health_score": 0.0,
            "next_active_tasks": [
                "Current active queue from .omo/tasks/active/ (32 tasks)",
                "Current active queue from .omo/tasks/active/ (5 tasks)",
                "Phase 17 gate in progress",
            ],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 16, "status": "completed", "goals": []})
    _write_yaml(
        omo / "tasks" / "active" / "gate.yaml",
        {"id": "P17-DEBT-GOVERNANCE-GATE-RULES", "phase": 17, "status": "in_progress", "run_ref": "run.yaml", "review_ref": "review.md"},
    )

    state = sync_state(omo, test_output="1 passed")

    assert state["next_active_tasks"] == [
        "Current active queue from .omo/tasks/active/ (1 task)",
        "P17-DEBT-GOVERNANCE-GATE-RULES",
        "Phase 17 gate in progress",
    ]


def test_dispatch_task_creates_packet_and_preclaims_task(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "sample.yaml",
        {
            "id": "TASK-1",
            "title": "Sample task",
            "status": "pending",
            "assigned_to": None,
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "source_docs": [".omo/README.md"],
            "entry_gate": [],
            "evidence_required": ["dispatch packet generated"],
            "test_plan": [".omo/tests/test_omo_automation.py"],
            "knowledge_refs": [],
            "handoff_refs": [],
            "approval_ref": None,
            "review_ref": None,
            "dispatch_id": None,
            "run_ref": None,
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-1",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=False,
    )

    task = _load_yaml(omo / "tasks" / "active" / "sample.yaml")
    dispatch = _load_yaml(root / result["dispatch_path"])
    envelope = _load_yaml(root / result["envelope_path"])

    assert task["status"] == "in_progress"
    assert task["assigned_to"] == "mockworker"
    assert task["dispatch_id"] == result["dispatch_id"]
    assert task["run_ref"] == result["dispatch_path"]
    assert Path(root / result["prompt_path"]).exists()
    assert dispatch["task_id"] == "TASK-1"
    assert dispatch["dispatch_state"] == "dispatched"
    assert envelope["scope"]["allowed_write_paths"] == ["src/app.py"]


def test_validate_task_file_rejects_l2_task_without_approval_reference(tmp_path: Path):
    task_path = tmp_path / ".omo" / "tasks" / "active" / "l2.yaml"
    _write_yaml(
        task_path,
        {
            "id": "TASK-L2",
            "title": "L2 task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "entry_gate": ["approval required"],
            "evidence_required": ["approval record"],
            "test_plan": [".omo/tests/example.md"],
        },
    )

    errors = validate_task_file(task_path)

    assert "approval_ref is required for L2/L3 tasks" in errors


def test_validate_task_file_allows_planned_packet_without_approval_ref(tmp_path: Path):
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "planned.yaml"
    _write_yaml(
        task_path,
        {
            "id": "TASK-PLANNED",
            "title": "Planned task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L3",
            "allowed_operation_level": "L3",
            "human_approval_required": True,
            "entry_gate": ["approval required before activation"],
            "evidence_required": ["planned packet reviewed"],
            "test_plan": ["python3 -m pytest .omo/tests/test_omo_automation.py -q"],
        },
    )

    assert validate_task_file(task_path) == []


def test_validate_task_file_rejects_planned_packet_with_live_dispatch_chain(tmp_path: Path):
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "planned.yaml"
    _write_yaml(
        task_path,
        {
            "id": "TASK-PLANNED-LIVE",
            "title": "Planned task with live fields",
            "status": "in_progress",
            "assigned_to": "mockworker",
            "dispatch_id": "dispatch-123",
            "run_ref": ".omo/workers/runs/dispatch-123.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/dispatch-123-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "entry_gate": ["approval required before activation"],
            "evidence_required": ["planned packet reviewed"],
            "test_plan": ["python3 -m pytest .omo/tests/test_omo_automation.py -q"],
            "started_at": "2026-06-02T00:00:00Z",
        },
    )

    assert validate_task_file(task_path) == [
        "planned tasks must use candidate or pending status",
        "planned tasks must not set assigned_to",
        "planned tasks must not set dispatch_id",
        "planned tasks must not set run_ref",
        "planned tasks must not set review_ref",
        "planned tasks must not set started_at",
    ]


def test_worker_validate_command_reports_all_planned_errors(tmp_path: Path, monkeypatch, capsys):
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "planned.yaml"
    _write_yaml(
        task_path,
        {
            "id": "TASK-PLANNED-LIVE",
            "title": "Planned task with live fields",
            "status": "review",
            "assigned_to": "mockworker",
            "dispatch_id": "dispatch-123",
            "run_ref": ".omo/workers/runs/dispatch-123.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/dispatch-123-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["planned packet reviewed"],
            "test_plan": ["python3 -m pytest .omo/tests/test_omo_automation.py -q"],
            "started_at": "2026-06-02T00:00:00Z",
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "task", "validate", "--all-planned"])

    assert omo_worker_main() == 1
    output = capsys.readouterr().out

    assert str(task_path) in output
    assert "planned tasks must use candidate or pending status" in output


def test_task_promote_eval_rejects_phase_beyond_next_wave(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P18-W1-TOO-FAR.yaml",
        {
            "id": "P18-W1-TOO-FAR",
            "phase": 18,
            "milestone": "M18.1",
            "priority": "P1",
            "title": "Too far ahead",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "task", "promote-eval", "P18-W1-TOO-FAR", "--omo-dir", ".omo"])

    assert omo_worker_main() == 1
    output = capsys.readouterr().out

    assert "eligible=false" in output
    assert "phase_mismatch" in output


def test_task_promote_eval_rejects_missing_required_approval_ref(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promote-eval", "P17-W1-NEEDS-APPROVAL", "--omo-dir", ".omo"],
    )

    assert omo_worker_main() == 1
    output = capsys.readouterr().out

    assert "eligible=false" in output
    assert "approval_missing" in output


def test_task_promote_eval_rejects_shared_backlog_presence_ref_for_human_approval_task(tmp_path: Path, monkeypatch, capsys):
    approval_note = tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md"
    approval_note.parent.mkdir(parents=True, exist_ok=True)
    approval_note.write_text("# planning backlog presence only\n", encoding="utf-8")
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 18})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "task", "promote-eval", "P19-W3-ARCHIVE-TS", "--omo-dir", ".omo"])

    assert omo_worker_main() == 1
    output = capsys.readouterr().out

    assert "eligible=false" in output
    assert "approval_invalid" in output


def test_task_promote_apply_moves_task_and_writes_envelope(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "scripts.omo_worker.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promote-apply",
            "P17-W1-READY",
            "--promoted-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    active_task = _load_yaml(tmp_path / ".omo" / "tasks" / "active" / "P17-W1-READY.yaml")

    assert "promotion_ref=.omo/workers/runs/P17-W1-READY-promotion-2026-06-03T00-00-00Z.yaml" in output
    assert active_task["status"] == "pending"
    assert active_task["handoff_refs"] == [
        ".omo/workers/runs/P17-W1-READY-promotion-2026-06-03T00-00-00Z.yaml"
    ]
    assert (tmp_path / ".omo" / "workers" / "runs" / "P17-W1-READY-promotion-2026-06-03T00-00-00Z.yaml").exists()
    assert not (tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml").exists()


def test_task_promote_apply_rolls_back_when_sync_fails(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-ROLLBACK.yaml",
        {
            "id": "P17-W1-ROLLBACK",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Rollback packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)

    def _fail_sync(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr("scripts.omo_worker.subprocess.run", _fail_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promote-apply",
            "P17-W1-ROLLBACK",
            "--promoted-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 1
    assert (tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-ROLLBACK.yaml").exists()
    assert not (tmp_path / ".omo" / "tasks" / "active" / "P17-W1-ROLLBACK.yaml").exists()
    assert not (
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-ROLLBACK-promotion-2026-06-03T00-00-00Z.yaml"
    ).exists()


def test_task_promotion_history_command_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "task", "promotion-history", "--omo-dir", ".omo"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "promotion_count=1" in output
    assert (tmp_path / ".omo" / "workers" / "promotion" / "current.yaml").exists()
    assert (tmp_path / ".omo" / "workers" / "promotion" / "current.md").exists()


def test_task_promotion_history_command_accepts_deterministic_now(tmp_path: Path, monkeypatch):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-history",
            "--omo-dir",
            ".omo",
            "--now",
            "2026-06-03T00:00:00Z",
        ],
    )

    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "current.yaml")
    assert packet["generated_at"] == "2026-06-03T00:00:00Z"


def test_task_promotion_readiness_command_writes_readiness_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P18-W1-BLOCKED.yaml",
        {
            "id": "P18-W1-BLOCKED",
            "phase": 18,
            "milestone": "M18.1",
            "priority": "P1",
            "title": "Blocked packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase17_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-readiness",
            "--omo-dir",
            ".omo",
            "--now",
            "2026-06-03T00:00:00Z",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert "ready_count=1" in output
    assert packet["generated_at"] == "2026-06-03T00:00:00Z"
    assert packet["current_phase"] == 16
    assert packet["target_phase"] == 17
    assert packet["ready_count"] == 1
    assert packet["blocked_count"] == 1
    assert [entry["task_id"] for entry in packet["tasks"]] == ["P17-W1-READY", "P18-W1-BLOCKED"]
    assert (tmp_path / ".omo" / "workers" / "promotion" / "readiness.md").exists()


def test_task_promotion_readiness_reports_approval_invalid_for_future_human_approval_packets(tmp_path: Path, monkeypatch):
    approval_note = tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md"
    approval_note.parent.mkdir(parents=True, exist_ok=True)
    approval_note.write_text("# planning backlog presence only\n", encoding="utf-8")
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )

    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert packet["tasks"][0]["blockers"] == ["phase_mismatch", "approval_invalid"]


def test_task_promotion_request_approval_rejects_non_human_approval_task(tmp_path: Path, monkeypatch):
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P17-W1-READY",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    with pytest.raises(ValueError, match="task does not require human approval"):
        omo_worker_main()


def test_task_promotion_request_approval_writes_requested_record_and_governance_proposal(
    tmp_path: Path, monkeypatch, capsys
):
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P19-W3-ARCHIVE-TS",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    task_packet = _load_yaml(tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml")
    approval_ref = ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml"
    proposal_ref = ".omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml"

    assert f"approval_ref={approval_ref}" in output
    assert f"proposal_ref={proposal_ref}" in output
    assert task_packet["approval_ref"] == approval_ref
    assert (tmp_path / approval_ref).exists()
    assert (tmp_path / proposal_ref).exists()


def test_task_promotion_request_approval_keeps_readiness_blocked_until_granted(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P17-W1-NEEDS-APPROVAL",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )
    assert omo_worker_main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )
    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert packet["tasks"][0]["approval_ref"] == (
        ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml"
    )
    assert packet["tasks"][0]["blockers"] == ["approval_invalid"]


def test_task_promotion_request_approval_rejects_duplicate_task_specific_request(tmp_path: Path, monkeypatch):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P19-W3-ARCHIVE-TS",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P19-W3-ARCHIVE-TS",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-04T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    with pytest.raises(ValueError, match="task already points to a task-specific promotion approval"):
        omo_worker_main()


def test_task_promotion_approval_status_rejects_task_without_task_specific_request(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-status", "--task-id", "P17-W1-READY", "--omo-dir", ".omo"],
    )

    with pytest.raises(ValueError, match="task does not point to a task-specific promotion approval"):
        omo_worker_main()


def test_task_promotion_approval_status_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P17-W1-NEEDS-APPROVAL",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P17-W1-NEEDS-APPROVAL.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "proposals"
        / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
            "status": "proposed",
            "target": {
                "ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml"
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-status", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml")

    assert "approval_task_count=1" in output
    assert packet["requested_count"] == 1
    assert packet["tasks"][0]["proposal_status"] == "proposed"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.md").exists()


def test_governance_apply_clears_promotion_approval_invalid_blocker(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P17-W1-NEEDS-APPROVAL",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P17-W1-NEEDS-APPROVAL.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "proposals"
        / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
            "title": "Grant promotion approval for P17-W1-NEEDS-APPROVAL",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml"
            },
            "changes": {"set": {"approval_status": "granted"}},
            "change_summary": "Grant promotion approval",
            "impact": "Releases a planned task into the promotion approval chain.",
            "verification_plan": [
                "python3 scripts/omo_worker.py task promote-eval P17-W1-NEEDS-APPROVAL --omo-dir .omo"
            ],
            "rollback_plan": ["restore requested state"],
            "secret_refs": [],
            "trace_id": "trace-demo",
            "status": "proposed",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "applied_at": None,
            "verified_at": None,
        },
    )

    approve_truth_mutation(
        tmp_path,
        "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
        approver="copilot-cli",
        now="2026-06-03T00:10:00Z",
    )
    apply_truth_mutation(
        tmp_path,
        "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
        now="2026-06-03T00:15:00Z",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:15:00Z"],
    )
    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert packet["tasks"][0]["blockers"] == []


def test_task_promotion_approval_history_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {"id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal", "status": "proposed"},
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-history", "--omo-dir", ".omo", "--now", "2026-06-03T00:15:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml")

    assert "approval_count=1" in output
    assert packet["latest_approval_id"] == "TASK-A-promotion-approval-2026-06-03T00-00-00Z"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.md").exists()


def test_task_promotion_approval_analytics_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_task_count": 1,
            "requested_count": 1,
            "approved_pending_apply_count": 0,
            "granted_count": 0,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T05-00-00Z.yaml",
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_count": 1,
            "approvals": [
                {
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "task_id": "TASK-A",
                    "requested_at": "2026-06-03T05:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "blocked_count": 1,
            "ready_count": 0,
            "tasks": [{"task_id": "TASK-A", "blockers": ["approval_invalid"]}],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-analytics", "--omo-dir", ".omo", "--now", "2026-06-03T06:00:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "analytics" / "current.yaml")

    assert "approval_task_count=1" in output
    assert packet["action_queues"]["approve_now"][0]["task_id"] == "TASK-A"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "analytics" / "current.md").exists()


def test_task_governance_overlay_status_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": "GOV-M2",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-ROADMAP-E2E",
                    "type": "task-bundle",
                    "title": "E2E and pricing debt closure",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml"],
                    "success_criteria": ["D2 promoted and closed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D2-CI-E2E-TEST-ENV.yaml", {"id": "D2-CI-E2E-TEST-ENV"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-status", "--omo-dir", ".omo", "--now", "2026-06-03T06:35:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "governance-overlay" / "current.yaml")

    assert "eligible_count=1" in output
    assert packet["next_action"] == "advance:GOV-M1-ROADMAP-E2E"
    assert (tmp_path / ".omo" / "workers" / "governance-overlay" / "current.md").exists()


def test_task_governance_overlay_run_next_writes_run_artifact(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["TASK-A advanced"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "phase": 17,
            "milestone": "GOV-M1",
            "priority": "P0",
            "title": "Task A",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["overlay active"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["promotion path triggered"],
            "test_plan": [".omo/tests/test_omo_governance_overlay_loop.py"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16, "status": "completed", "goals": []})
    _write_yaml(tmp_path / ".omo" / "state" / "system.yaml", {"current_phase": 16, "health_score": 0.0})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("scripts.omo_worker._sync_omo_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T06:40:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T06-40-00Z.yaml")
    roadmap = _load_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml")

    assert "summary=advanced" in output
    assert run_packet["roadmap_item_id"] == "GOV-M1-EXECUTION-HARDENING"
    assert run_packet["target_results"][0]["result"] == "promoted"
    assert roadmap["items"][0]["status"] == "in_progress"
    assert (tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml").exists()


def test_task_governance_overlay_run_next_closes_done_active_item_and_advances_control(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                },
                {
                    "id": "GOV-M2-SHAREDBRAIN-DEBT",
                    "type": "debt-bundle",
                    "title": "SharedBrain debt",
                    "priority": "P1",
                    "status": "pending",
                    "depends_on": ["GOV-M1-EXECUTION-HARDENING"],
                    "source_refs": [".omo/debt/registry.yaml"],
                    "target_refs": [".omo/debt/dashboard/current.yaml"],
                    "success_criteria": ["debt closed"],
                },
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-A.yaml", {"id": "TASK-A", "status": "done"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T06:50:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    control = _load_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml")
    roadmap = _load_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml")
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T06-50-00Z.yaml")

    assert "summary=closed" in output
    assert control["current_milestone"] == "GOV-M2-SHAREDBRAIN-DEBT"
    assert control["next_milestone"] is None
    assert roadmap["items"][0]["status"] == "done"
    assert run_packet["mode"] == "continue_active"


def test_task_governance_overlay_run_next_dispatches_first_active_pending_target(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_dispatch_when_safe": True,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml", ".omo/tasks/planned/TASK-B.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "phase": 17,
            "milestone": "GOV-M1",
            "priority": "P0",
            "title": "Task A",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "deliverables": [".omo/evidence/task-a/output.md"],
            "depends_on": [],
            "entry_gate": ["overlay active"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["dispatch packet created"],
            "test_plan": [".omo/tests/test_omo_automation.py"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-B.yaml",
        {
            "id": "TASK-B",
            "phase": 17,
            "milestone": "GOV-M1",
            "priority": "P0",
            "title": "Task B",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["overlay active"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["dispatch packet created"],
            "test_plan": [".omo/tests/test_omo_automation.py"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "enabled": True,
                    "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}},
                }
            ]
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T06:58:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    task_a = _load_yaml(tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml")
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T06-58-00Z.yaml")

    assert "summary=dispatched" in output
    assert task_a["status"] == "in_progress"
    assert task_a["assigned_to"] == "mockworker"
    assert run_packet["target_results"][0]["result"] == "dispatched"


def test_task_governance_overlay_run_next_marks_verify_ready_for_active_review_target(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "phase": 17,
            "milestone": "GOV-M1",
            "priority": "P0",
            "title": "Task A",
            "status": "review",
            "assigned_to": "mockworker",
            "dispatch_id": "task-a-mockworker-123",
            "run_ref": ".omo/workers/runs/task-a-mockworker-123-dispatch.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/task-a-mockworker-123-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["overlay active"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["review ready"],
            "test_plan": [".omo/tests/test_omo_automation.py"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T07:01:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T07-01-00Z.yaml")

    assert "summary=verify_ready" in output
    assert run_packet["target_results"][0]["state"] == "active_review"


def test_dispatch_task_rejects_invalid_task_schema_before_preclaim(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "bad.yaml",
        {
            "id": "TASK-BAD",
            "title": "Broken task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "entry_gate": ["approval required"],
            "evidence_required": ["approval record"],
            "test_plan": [".omo/tests/example.md"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="approval_ref is required for L2/L3 tasks"):
        dispatch_task(
            root,
            task_id="TASK-BAD",
            worker_id="mockworker",
            allowed_write_paths=["src/app.py"],
            launch=False,
        )


def test_dispatch_task_launch_handles_quoted_prompt_without_shell_breakage(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    captured = root / "captured.txt"

    _write_yaml(
        omo / "tasks" / "active" / "quoted.yaml",
        {
            "id": "TASK-QUOTED",
            "title": 'Worker "quoted" task',
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["captured prompt"],
            "test_plan": ["launch worker safely"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {
                            "command": f'python3 -c "import pathlib,sys; pathlib.Path(r\'{captured}\').write_text(sys.argv[1])" "{{prompt}}"'
                        }
                    },
                }
            ]
        },
    )

    dispatch_task(
        root,
        task_id="TASK-QUOTED",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=True,
    )

    assert captured.exists()
    assert 'Worker "quoted" task' in captured.read_text(encoding="utf-8")


def test_dispatch_prompt_includes_required_deliverables_when_task_declares_them(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "deliverable.yaml",
        {
            "id": "TASK-DELIVERABLE",
            "title": "Write roadmap",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/source.md"],
            "deliverables": [".omo/plans/output.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["roadmap written"],
            "test_plan": ["verify output file exists"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-DELIVERABLE",
        worker_id="mockworker",
        allowed_write_paths=[".omo/plans/"],
        launch=False,
    )

    prompt_text = (root / result["prompt_path"]).read_text(encoding="utf-8")
    envelope = yaml.safe_load((root / result["envelope_path"]).read_text(encoding="utf-8"))

    assert "- Required deliverable: `.omo/plans/output.md`" in prompt_text
    assert "Updating only the review note is not sufficient" in prompt_text
    assert envelope["outputs"]["required_deliverables"] == [".omo/plans/output.md"]


def test_dispatch_task_creates_checkpoint_and_reclaim_artifacts(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "checkpoint.yaml",
        {
            "id": "TASK-CHECKPOINT",
            "title": "Checkpoint task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint stub created"],
            "test_plan": ["inspect dispatch artifacts"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    result = dispatch_task(
        root,
        task_id="TASK-CHECKPOINT",
        worker_id="mockworker",
        allowed_write_paths=["src/app.py"],
        launch=False,
    )

    dispatch = _load_yaml(root / result["dispatch_path"])
    task = _load_yaml(omo / "tasks" / "active" / "checkpoint.yaml")
    checkpoint_text = (root / result["checkpoint_path"]).read_text(encoding="utf-8")
    reclaim_text = (root / result["reclaim_path"]).read_text(encoding="utf-8")
    status = collect_worker_status(root)

    assert dispatch["execution"]["checkpoint_refs"] == [result["checkpoint_path"]]
    assert task["handoff_refs"][-2:] == [result["prompt_path"], result["checkpoint_path"]]
    assert "## Last completed step" in checkpoint_text
    assert "## Reclaim reason" in reclaim_text
    assert status["active_dispatches"] == 1
    assert status["runs"][0]["checkpoint_refs"] == [result["checkpoint_path"]]
    assert status["runs"][0]["reclaim_ref"] == result["reclaim_path"]
    assert status["runs"][0]["lease"]["warning_after_seconds"] == 900


def test_sync_state_flags_in_progress_tasks_missing_run_and_review_refs(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "run_ref": None,
            "review_ref": None,
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-A"]}]})

    sync_state(omo)

    state = _load_yaml(omo / "state" / "system.yaml")
    assert "active_task_missing_run_ref:TASK-A" in state["divergence_flags"]
    assert "active_task_missing_review_ref:TASK-A" in state["divergence_flags"]


def test_sync_state_derives_gate_facts_and_promotion_blockers(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "gate.yaml",
        {
            "id": "TASK-GATE",
            "title": "Gate task",
            "status": "in_progress",
            "assigned_to": "worker-a",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/dispatch-1-dispatch.yaml",
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["review note"],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-GATE"]}]})
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-1-dispatch.yaml",
        {
            "task_id": "TASK-GATE",
            "worker_id": "worker-a",
            "dispatch_state": "reclaimed",
            "reclaim": {
                "required": True,
                "reason": "lease expired",
                "reclaimed_at": "2026-05-31T00:00:00Z",
                "successor_worker_id": "worker-b",
                "successor_dispatch_id": "dispatch-2",
                "note_ref": ".omo/workers/runs/dispatch-1-reclaim.md",
            },
        },
    )

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-GATE"]
    assert gate["canonical_status"] == "in_progress"
    assert gate["gate_facts"] == ["dispatched", "reclaimed"]
    assert state["promotion_blockers"]["TASK-GATE"] == ["missing_review_ref"]


def test_sync_state_dispatched_gate_requires_dispatch_id(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "dispatch.yaml",
        {
            "id": "TASK-DISPATCH",
            "title": "Dispatch task",
            "status": "in_progress",
            "assigned_to": "worker-a",
            "dispatch_id": None,
            "run_ref": ".omo/workers/runs/dispatch-dispatch.yaml",
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": [],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-DISPATCH"]}]})

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-DISPATCH"]
    assert "dispatched" not in gate["gate_facts"]


def test_sync_state_done_task_requires_completion_summary_before_acceptance(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "done.yaml",
        {
            "id": "TASK-DONE",
            "title": "Done task",
            "status": "done",
            "assigned_to": "worker-a",
            "dispatch_id": "dispatch-done",
            "run_ref": ".omo/workers/runs/dispatch-done-dispatch.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/dispatch-done-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["review note"],
            "test_plan": ["sync state"],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-DONE"]}]})
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-done-dispatch.yaml",
        {
            "task_id": "TASK-DONE",
            "worker_id": "worker-a",
            "dispatch_state": "completed",
        },
    )
    (omo / "workers" / "runs" / "dispatch-done-review.md").parent.mkdir(parents=True, exist_ok=True)
    (omo / "workers" / "runs" / "dispatch-done-review.md").write_text(
        "# Review Note\n\ncompleted\n",
        encoding="utf-8",
    )

    state = sync_state(omo)

    gate = state["task_gate_summary"]["TASK-DONE"]
    assert "accepted" not in gate["gate_facts"]
    assert state["promotion_blockers"]["TASK-DONE"] == ["missing_completion_summary"]


def test_sync_state_joins_divergence_snapshot_with_triage_registry(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "active_tasks": 0,
            "blocked_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "health_score": 0.0,
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {"id": "TASK-A", "phase": 6, "status": "in_progress", "run_ref": None, "review_ref": None},
    )
    _write_yaml(omo / "tasks" / "blocked" / "b.yaml", {"id": "TASK-B", "phase": 6})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 6, "goals": [{"id": "G1", "tasks": ["TASK-A"]}]})
    _write_yaml(
        omo / "standards" / "divergence-triage.yaml",
        {
            "rules": {
                "orphaned_tasks": {"severity": "medium", "owner": "truth", "disposition": "must_fix"},
                "active_task_missing_review_ref": {"severity": "high", "owner": "delivery", "disposition": "must_fix"},
            }
        },
    )

    state = sync_state(omo)

    triage = state["divergence_triage_summary"]
    assert triage["orphaned_tasks:1"]["severity"] == "medium"
    assert triage["active_task_missing_review_ref:TASK-A"]["owner"] == "delivery"
    assert triage["active_task_missing_run_ref:TASK-A"]["disposition"] == "monitor"


def test_worker_status_command_prints_checkpoint_summary(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "status.yaml",
        {
            "id": "TASK-STATUS",
            "title": "Status task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["status visible"],
            "test_plan": ["run worker status"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "mockworker",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                }
            ]
        },
    )

    dispatch_task(root, "TASK-STATUS", "mockworker", ["src/app.py"], launch=False)

    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "status"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    assert "TASK-STATUS" in output
    assert "mockworker" in output
    assert "checkpoints=1" in output


def test_update_dispatch_checkpoint_records_step_and_refreshes_lease(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "checkpoint.yaml",
        {
            "id": "TASK-CHECKPOINT",
            "title": "Checkpoint task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint stub created"],
            "test_plan": ["inspect dispatch artifacts"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {"workers": [{"id": "mockworker", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}}]},
    )

    dispatch = dispatch_task(root, "TASK-CHECKPOINT", "mockworker", ["src/app.py"], launch=False)

    result = update_dispatch_checkpoint(
        root,
        dispatch["dispatch_id"],
        completed_step="Implemented durable checkpoint refresh",
        changed_files=["scripts/omo_worker.py", ".omo/tests/test_omo_automation.py"],
        note="Checkpoint updated after writing runtime evidence.",
        now="2026-05-31T08:00:00Z",
    )

    dispatch_payload = _load_yaml(root / dispatch["dispatch_path"])
    checkpoint_text = (root / dispatch["checkpoint_path"]).read_text(encoding="utf-8")
    assert result["dispatch_state"] == "checkpointed"
    assert dispatch_payload["dispatch_state"] == "checkpointed"
    assert dispatch_payload["lease"]["last_checkpoint_at"] == "2026-05-31T08:00:00Z"
    assert dispatch_payload["lease"]["last_material_write_at"] == "2026-05-31T08:00:00Z"
    assert "Implemented durable checkpoint refresh" in checkpoint_text
    assert "- `scripts/omo_worker.py`" in checkpoint_text
    assert "Checkpoint updated after writing runtime evidence." in checkpoint_text


def test_scan_runtime_watchdog_classifies_warning_stale_and_reclaim_due(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "a.yaml",
        {"id": "TASK-A", "title": "A", "status": "in_progress", "run_ref": ".omo/workers/runs/a-dispatch.yaml"},
    )
    _write_yaml(
        omo / "tasks" / "active" / "b.yaml",
        {"id": "TASK-B", "title": "B", "status": "in_progress", "run_ref": ".omo/workers/runs/b-dispatch.yaml"},
    )
    _write_yaml(
        omo / "tasks" / "active" / "c.yaml",
        {"id": "TASK-C", "title": "C", "status": "in_progress", "run_ref": ".omo/workers/runs/c-dispatch.yaml"},
    )
    _write_yaml(
        omo / "workers" / "runs" / "a-dispatch.yaml",
        {
            "task_id": "TASK-A",
            "worker_id": "worker-a",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:58:30Z",
                "last_material_write_at": "2026-05-31T07:58:30Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/a-checkpoint.md"]},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "b-dispatch.yaml",
        {
            "task_id": "TASK-B",
            "worker_id": "worker-b",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:57:30Z",
                "last_material_write_at": "2026-05-31T07:57:30Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/b-checkpoint.md"]},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "c-dispatch.yaml",
        {
            "task_id": "TASK-C",
            "worker_id": "worker-c",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:54:00Z",
                "last_material_write_at": "2026-05-31T07:54:00Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/c-checkpoint.md"]},
        },
    )

    watchdog = scan_runtime_watchdog(root, now="2026-05-31T08:00:00Z")

    assert watchdog["counts"] == {"healthy": 0, "warning": 1, "stale": 1, "reclaim_due": 1}
    assert watchdog["runs"][0]["task_id"] == "TASK-A"
    assert watchdog["runs"][0]["health"] == "warning"
    assert watchdog["runs"][1]["task_id"] == "TASK-B"
    assert watchdog["runs"][1]["health"] == "stale"
    assert watchdog["runs"][2]["task_id"] == "TASK-C"
    assert watchdog["runs"][2]["health"] == "reclaim_due"


def test_worker_watchdog_command_prints_runtime_health(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "watch.yaml",
        {"id": "TASK-WATCH", "title": "Watch task", "status": "in_progress", "run_ref": ".omo/workers/runs/watch-dispatch.yaml"},
    )
    _write_yaml(
        omo / "workers" / "runs" / "watch-dispatch.yaml",
        {
            "task_id": "TASK-WATCH",
            "worker_id": "worker-a",
            "dispatch_state": "dispatched",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "reclaim_after_seconds": 180,
                "last_checkpoint_at": "2026-05-31T07:54:00Z",
                "last_material_write_at": "2026-05-31T07:54:00Z",
            },
            "reclaim": {"required": False},
            "execution": {"checkpoint_refs": [".omo/workers/runs/watch-checkpoint.md"]},
        },
    )

    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "watchdog", "--now", "2026-05-31T08:00:00Z"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    assert "reclaim_due=1" in output
    assert "TASK-WATCH" in output
    assert "health=reclaim_due" in output


def test_worker_admission_eval_command_prints_decision(monkeypatch, capsys):
    root = Path(__file__).resolve().parents[2]

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "admission-eval",
            ".omo/workers/runs/phase9-wave3-identity-admission-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "membership=system-governor-membership" in output
    assert "decision=conditional_approval" in output


def test_worker_admission_request_approval_command_writes_governance_artifacts(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "contract.yaml",
        {
            "admission_matrix_ref": "spaces/matrix.yaml",
            "memberships": [
                {
                    "id": "governor-membership",
                    "actor_ref": "demo-actor",
                    "space_ref": "spaces/system-space.yaml",
                    "roles": ["governor"],
                }
            ],
            "capability_bindings": [
                {
                    "id": "governor-binding",
                    "membership_ref": "governor-membership",
                    "capabilities": ["project.dispatch"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "matrix.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_capabilities": ["project.dispatch"],
                    "decision": "conditional_approval",
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "run_ref": ".omo/workers/runs/example-dispatch.yaml",
            "task_yaml": ".omo/tasks/active/TASK-1.yaml",
            "handoff_refs": [".omo/workers/runs/example-review.md"],
            "gates": {"approval_ref": None},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "governor-membership",
                "action": "project.dispatch",
                "admission_contract_ref": "spaces/contract.yaml",
                "required_capabilities": ["project.dispatch"],
                "decision_mode": "conditional_approval",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "admission-request-approval",
            ".omo/workers/runs/example-envelope.yaml",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-05-31T12:31:00Z",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "proposal=example-approval-proposal" in output
    assert "approval_ref=.omo/workers/runs/example-approval.yaml" in output
    assert (tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml").exists()
    assert (
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "example-approval-proposal.yaml"
    ).exists()


def test_worker_rollout_eval_command_prints_allow_for_granted_approval(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "rollout-policy.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_approval_status": "granted",
                    "required_evidence_refs": [
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                    ],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "runtime" / "runtime-boundary.yaml",
        {
            "allowed_runtime_roots": ["runtime/run-continuation", "runtime/logs"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml",
        {
            "approval_status": "granted",
            "release_scope": {"exact_action": "project.dispatch"},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "apply.yaml",
        {"status": "applied"},
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "verify.yaml",
        {"status": "verified"},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {"approval_ref": ".omo/workers/runs/example-approval.yaml"},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rollout_context": {
                "rollout_policy_ref": "spaces/rollout-policy.yaml",
                "runtime_boundary_ref": "runtime/runtime-boundary.yaml",
                "acceptance_evidence_refs": [
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                ],
                "runtime_residue_paths": [
                    "runtime/run-continuation/session-1",
                    "runtime/logs/dispatch.log",
                ],
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rollout-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "approval=granted" in output
    assert "decision=allow" in output


def test_worker_rollout_accept_command_writes_acceptance_record(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / "spaces" / "rollout-policy.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_approval_status": "granted",
                    "required_evidence_refs": [
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                        ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                    ],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "runtime" / "runtime-boundary.yaml",
        {
            "allowed_runtime_roots": ["runtime/run-continuation", "runtime/logs"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-approval.yaml",
        {
            "approval_status": "granted",
            "release_scope": {"exact_action": "project.dispatch"},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "apply.yaml",
        {"status": "applied"},
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "proposals" / "example-approval-proposal" / "verify.yaml",
        {"status": "verified"},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "run_ref": ".omo/workers/runs/example-dispatch.yaml",
            "task_yaml": ".omo/tasks/active/TASK-1.yaml",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": None,
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rollout_context": {
                "rollout_policy_ref": "spaces/rollout-policy.yaml",
                "runtime_boundary_ref": "runtime/runtime-boundary.yaml",
                "acceptance_evidence_refs": [
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/apply.yaml",
                    ".omo/_delivery/task-center/proposals/example-approval-proposal/verify.yaml",
                ],
                "runtime_residue_paths": [
                    "runtime/run-continuation/session-1",
                    "runtime/logs/dispatch.log",
                ],
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rollout-accept",
            ".omo/workers/runs/example-envelope.yaml",
            "--accepted-by",
            "copilot-cli",
            "--now",
            "2026-05-31T20:45:00Z",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "acceptance_ref=.omo/workers/runs/example-acceptance.yaml" in output
    assert (tmp_path / ".omo" / "workers" / "runs" / "example-acceptance.yaml").exists()
    envelope = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml")
    assert envelope["gates"]["acceptance_ref"] == ".omo/workers/runs/example-acceptance.yaml"


def test_worker_rules_eval_command_prints_normalized_bundle_refs(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
                    "governance": {
                        "admission_contract_ref": "spaces/identity.yaml",
                        "rollout_policy_ref": "spaces/rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {"rules": [{"action": "project.dispatch", "allowed_roots": ["data"]}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W2-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-boundary.yaml" in output


def test_worker_rules_eval_command_prints_normalized_bundle_refs_for_wave3_packets(
    tmp_path: Path, monkeypatch, capsys
):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
                    "governance": {
                        "admission_contract_ref": "spaces/identity.yaml",
                        "rollout_policy_ref": "spaces/rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {"rules": [{"action": "project.dispatch", "allowed_roots": ["data"]}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W3-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=project.dispatch" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-boundary.yaml" in output


def test_worker_rules_eval_command_prints_normalized_bundle_refs_for_cross_space_packets(
    tmp_path: Path, monkeypatch, capsys
):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/runtime-space.yaml",
                    "action": "runtime.observe",
                    "governance": {
                        "admission_contract_ref": "spaces/runtime-identity.yaml",
                        "rollout_policy_ref": "spaces/runtime-rollout-policy.yaml",
                    },
                    "data": {"policy_ref": "data/runtime-data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-space-boundary.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "runtime-data-policy.yaml",
        {"rules": [{"action": "runtime.observe", "allowed_roots": []}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W4-TASK-1",
            "worker_id": "copilot-cli",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/runtime-space.yaml",
                "membership_ref": "runtime-space-observer-membership",
                "action": "runtime.observe",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "worker",
            "rules-eval",
            ".omo/workers/runs/example-envelope.yaml",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=runtime.observe" in output
    assert "registry=spaces/cross-root-rules.yaml" in output
    assert "data_policy=data/runtime-data-policy.yaml" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-space-boundary.yaml" in output


def test_write_worker_utilization_summary_aggregates_runs(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "workers" / "runs" / "one-dispatch.yaml",
        {
            "task_id": "TASK-1",
            "worker_id": "worker-a",
            "dispatch_state": "completed",
            "launched_at": "2026-05-30T10:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/one-review.md"},
            "reclaim": {"successor_dispatch_id": "two", "successor_worker_id": "worker-b"},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "two-dispatch.yaml",
        {
            "task_id": "TASK-2",
            "worker_id": "worker-a",
            "dispatch_state": "reclaimed",
            "launched_at": "2026-05-31T10:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/two-review.md"},
            "reclaim": {"successor_dispatch_id": None, "successor_worker_id": None},
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "three-dispatch.yaml",
        {
            "task_id": "TASK-3",
            "worker_id": "worker-b",
            "dispatch_state": "completed",
            "launched_at": "2026-05-31T12:00:00Z",
            "handoff": {"output_summary_ref": ".omo/workers/runs/three-review.md"},
            "reclaim": {"successor_dispatch_id": None, "successor_worker_id": None},
        },
    )

    summary_path = write_worker_utilization_summary(root)
    text = (root / summary_path).read_text(encoding="utf-8")

    assert "period_start: 2026-05-30T10:00:00Z" in text
    assert "period_end: 2026-05-31T12:00:00Z" in text
    assert "worker-a" in text
    assert "dispatches: 2" in text
    assert "reclaims: 1" in text
    assert "review_notes: 2" in text
    assert "handoffs_out: 1" in text
    assert "average_handoffs_per_dispatch: 0.5" in text


def test_reclaim_task_reassigns_from_checkpoint_context(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"

    _write_yaml(
        omo / "tasks" / "active" / "reclaim.yaml",
        {
            "id": "TASK-RECLAIM",
            "title": "Reclaim task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint reclaim drill completed"],
            "test_plan": ["run reclaim flow"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {
                    "id": "worker-a",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                },
                {
                    "id": "worker-b",
                    "transports": {
                        "cli_prompt": {"command": 'mockworker "{prompt}"'}
                    },
                },
            ]
        },
    )

    first = dispatch_task(root, "TASK-RECLAIM", "worker-a", ["src/app.py"], launch=False)
    (root / first["checkpoint_path"]).write_text(
        "# Checkpoint Note\n\n## Last completed step\n\nImplemented the parser.\n",
        encoding="utf-8",
    )

    second = reclaim_task(
        root,
        task_id="TASK-RECLAIM",
        successor_worker_id="worker-b",
        allowed_write_paths=["src/app.py"],
        reason="lease expired",
        launch=False,
    )

    first_dispatch = _load_yaml(root / first["dispatch_path"])
    second_dispatch = _load_yaml(root / second["dispatch_path"])
    second_envelope = _load_yaml(root / second["envelope_path"])
    second_prompt = (root / second["prompt_path"]).read_text(encoding="utf-8")
    reclaim_note = (root / first["reclaim_path"]).read_text(encoding="utf-8")
    task = _load_yaml(omo / "tasks" / "active" / "reclaim.yaml")

    assert first_dispatch["dispatch_state"] == "reclaimed"
    assert first_dispatch["reclaim"]["required"] is True
    assert first_dispatch["reclaim"]["reason"] == "lease expired"
    assert first_dispatch["reclaim"]["successor_worker_id"] == "worker-b"
    assert first_dispatch["reclaim"]["successor_dispatch_id"] == second["dispatch_id"]
    assert task["assigned_to"] == "worker-b"
    assert task["run_ref"] == second["dispatch_path"]
    assert first["checkpoint_path"] in second_prompt
    assert first["reclaim_path"] in second_prompt
    assert second_envelope["inputs"]["prior_evidence"] == [first["checkpoint_path"], first["reclaim_path"]]
    assert "lease expired" in reclaim_note
    assert second_dispatch["task_id"] == "TASK-RECLAIM"


def test_write_handoff_index_links_dispatch_checkpoint_reclaim_and_review(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "tasks" / "active" / "reclaim.yaml",
        {
            "id": "TASK-RECLAIM",
            "title": "Reclaim task",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/plans/example.md"],
            "risk_level": "L0",
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "entry_gate": [],
            "evidence_required": ["checkpoint reclaim drill completed"],
            "test_plan": ["run reclaim flow"],
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "workers": [
                {"id": "worker-a", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}},
                {"id": "worker-b", "transports": {"cli_prompt": {"command": 'mockworker "{prompt}"'}}},
            ]
        },
    )

    dispatch = dispatch_task(root, "TASK-RECLAIM", "worker-a", ["src/app.py"], launch=False)
    reclaim = reclaim_task(root, "TASK-RECLAIM", "worker-b", ["src/app.py"], reason="lease expired", launch=False)

    task = _load_yaml(omo / "tasks" / "active" / "reclaim.yaml")
    task["review_ref"] = dispatch["review_path"]
    task["completion_summary"] = "Recovered via reclaim and closed with a successor worker."
    _write_yaml(omo / "tasks" / "active" / "reclaim.yaml", task)

    index_path = write_handoff_index(root, "TASK-RECLAIM")
    text = (root / index_path).read_text(encoding="utf-8")

    assert dispatch["dispatch_path"] in text
    assert dispatch["checkpoint_path"] in text
    assert dispatch["reclaim_path"] in text
    assert dispatch["review_path"] in text
    assert reclaim["dispatch_path"] in text
    assert "Recovered via reclaim and closed with a successor worker." in text
