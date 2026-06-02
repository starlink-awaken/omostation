from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

import yaml


def test_debt_refresh_writes_dashboard_review_queue_and_action_packet(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    future_item = tmp_path / ".omo" / "debt" / "items" / "SB_UNTESTED_PKGS.yaml"
    future_payload = yaml.safe_load(future_item.read_text(encoding="utf-8"))
    future_payload["next_review_at"] = "2026-06-11T00:00:00Z"
    future_item.write_text(yaml.safe_dump(future_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    unscheduled_item = tmp_path / ".omo" / "debt" / "items" / "SB_ROOT_CLEANUP.yaml"
    unscheduled_payload = yaml.safe_load(unscheduled_item.read_text(encoding="utf-8"))
    unscheduled_payload["next_review_at"] = None
    unscheduled_item.write_text(yaml.safe_dump(unscheduled_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "refresh",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    dashboard = yaml.safe_load((tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml").read_text(encoding="utf-8"))
    queue = yaml.safe_load((tmp_path / ".omo" / "debt" / "review-queue" / "current.yaml").read_text(encoding="utf-8"))
    review = (tmp_path / ".omo" / "debt" / "reviews" / "current.md").read_text(encoding="utf-8")
    action_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "action-packet" / "current.yaml").read_text(encoding="utf-8"))
    action_md = (tmp_path / ".omo" / "debt" / "action-packet" / "current.md").read_text(encoding="utf-8")
    owner_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "owner-routing" / "current.yaml").read_text(encoding="utf-8"))
    owner_md = (tmp_path / ".omo" / "debt" / "owner-routing" / "current.md").read_text(encoding="utf-8")
    assert dashboard["debt_metrics"]["debt_health"] < 100
    assert dashboard["overdue_review_count"] == 7
    assert dashboard["overdue_review_item_ids"] == [
        "SB_DECOMPOSITION",
        "D2_CI_E2E",
        "D3_EU_PRICING",
        "SB_BRIDGE_FIX",
        "SB_ORPHANED_TASKS",
        "SB_PROJECTS_YAML",
        "SB_PHASE17_PLAN",
    ]
    assert dashboard["next_review_queue"] == [
        {
            "id": "SB_UNTESTED_PKGS",
            "next_review_at": "2026-06-11T00:00:00Z",
        }
    ]
    assert queue["summary"]["due_now_count"] == 7
    assert queue["summary"]["upcoming_count"] == 1
    assert queue["summary"]["unscheduled_count"] == 1
    assert [entry["id"] for entry in queue["upcoming"]] == ["SB_UNTESTED_PKGS"]
    assert [entry["id"] for entry in queue["unscheduled"]] == ["SB_ROOT_CLEANUP"]
    assert "SB_DECOMPOSITION" in [entry["id"] for entry in queue["escalation_candidates"]]
    assert "## Watchlist" in review
    assert "## Gate Debts" in review
    assert "## Due Now" in review
    assert "## Escalation Candidates" in review
    assert "## Upcoming Window" in review
    assert "## Unscheduled Debts" in review
    assert "## Newly Registered" in review
    assert "## Closed Debts" in review
    assert "## Reopened Debts" in review
    assert [entry["id"] for entry in action_yaml["lanes"]["schedule_now"]] == ["SB_ROOT_CLEANUP"]
    assert "SB_DECOMPOSITION" in [entry["id"] for entry in action_yaml["lanes"]["revalidate_now"]]
    assert [entry["id"] for entry in action_yaml["lanes"]["watch_only"]] == ["SB_UNTESTED_PKGS"]
    assert "## Revalidate Now" in action_md
    assert "## Schedule Now" in action_md
    assert "## Watch Only" in action_md
    assert [owner["owner"] for owner in owner_yaml["owners"]] == [
        "sharedbrain-governance",
        "commerce-governance",
        "platform-governance",
        "omo-governance",
    ]
    omo_owner = next(owner for owner in owner_yaml["owners"] if owner["owner"] == "omo-governance")
    assert "initial_review_required" in {
        flag
        for entry in omo_owner["entries"]
        for flag in entry["priority_flags"]
    }
    assert "# Debt Owner Routing Packet" in owner_md
    assert "Owners: 4" in owner_md
    assert "Total routed items: 9" in owner_md
    assert "Lane counts: revalidate_now=7, schedule_now=1, escalate_now=0, continue_mitigation=0, watch_only=1" in owner_md
    assert "## Owner: sharedbrain-governance" in owner_md
    assert "## Owner: omo-governance" in owner_md
    assert "### Revalidate Now" in owner_md
    assert "### Schedule Now" in owner_md
    assert "### Watch Only" in owner_md


def test_debt_dispatch_writes_current_and_immutable_run_artifacts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")
    shutil.rmtree(tmp_path / ".omo" / "debt" / "dispatch", ignore_errors=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    current_yaml_path = tmp_path / ".omo" / "debt" / "dispatch" / "current.yaml"
    current_md_path = tmp_path / ".omo" / "debt" / "dispatch" / "current.md"
    run_yaml_path = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml"
    run_md_path = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.md"

    current_yaml = yaml.safe_load(current_yaml_path.read_text(encoding="utf-8"))
    run_yaml = yaml.safe_load(run_yaml_path.read_text(encoding="utf-8"))
    current_md = current_md_path.read_text(encoding="utf-8")
    run_md = run_md_path.read_text(encoding="utf-8")

    assert current_yaml == run_yaml
    assert current_yaml["dispatched_at"] == "2026-06-10T00:00:00Z"
    assert current_yaml["latest_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert current_yaml["summary"]["owner_count"] == 4
    assert current_yaml["summary"]["total_dispatched_items"] == 9
    first_entry = current_yaml["owners"][0]["entries"][0]
    assert first_entry["command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION "
        "--reviewed-at 2026-06-10T00:00:00Z "
        "--dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    )
    assert "command_template" not in first_entry
    assert "shell_command" not in first_entry
    assert current_md == run_md
    assert "# Debt Dispatch Packet" in current_md
    assert "Dispatch timestamp: 2026-06-10T00:00:00Z" in current_md
    assert "Owner count: 4" in current_md
    assert "Total dispatched items: 9" in current_md
    assert "## Owner: sharedbrain-governance" in current_md
    assert "## Owner: omo-governance" in current_md
    assert "### Frozen Commands" in current_md
    assert (
        "- `SB_DECOMPOSITION` — `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id "
        "SB_DECOMPOSITION --reviewed-at 2026-06-10T00:00:00Z "
        "--dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml`"
    ) in current_md
