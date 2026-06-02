from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

import yaml


def test_debt_schedule_updates_item_state(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "schedule",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D2_CI_E2E",
            "--next-review-at",
            "2026-06-15T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "D2_CI_E2E.yaml").read_text(encoding="utf-8"))
    assert payload["lifecycle_state"] == "scheduled"
    assert payload["next_review_at"] == "2026-06-15T00:00:00Z"
    assert payload["history"][-1]["action"] == "schedule"


def test_debt_register_creates_new_item(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    (debt_dir / "items").mkdir(parents=True, exist_ok=True)
    (debt_dir / "dashboard").mkdir(parents=True, exist_ok=True)
    (debt_dir / "reviews").mkdir(parents=True, exist_ok=True)
    (debt_dir / "registry.yaml").write_text(
        "version: 1\nitems_dir: .omo/debt/items\ndashboard_ref: .omo/debt/dashboard/current.yaml\nreview_pack_ref: .omo/debt/reviews/current.md\nreview_queue_ref: .omo/debt/review-queue/current.yaml\naction_packet_ref: .omo/debt/action-packet/current.yaml\nowner_routing_ref: .omo/debt/owner-routing/current.yaml\ndispatch_ref: .omo/debt/dispatch/current.yaml\ncampaign_ref: .omo/debt/campaign/current.yaml\nreporting_ref: .omo/debt/reporting/current.yaml\nseed_items: []\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "register",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "NEW_GATE",
            "--title",
            "New gate debt",
            "--dimension",
            "governance_process",
            "--subdimension",
            "gate_rule",
            "--severity",
            "medium",
            "--owner",
            "omo-governance",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((debt_dir / "items" / "NEW_GATE.yaml").read_text(encoding="utf-8"))
    registry = yaml.safe_load((debt_dir / "registry.yaml").read_text(encoding="utf-8"))
    assert payload["lifecycle_state"] == "identified"
    assert payload["history"][-1]["action"] == "register"
    assert ".omo/debt/items/NEW_GATE.yaml" in registry["seed_items"]


def test_debt_reclassify_updates_dimension_fields(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "reclassify",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_ORPHANED_TASKS",
            "--dimension",
            "governance_process",
            "--subdimension",
            "pointer_hygiene",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "SB_ORPHANED_TASKS.yaml").read_text(encoding="utf-8"))
    assert payload["dimension"] == "governance_process"
    assert payload["subdimension"] == "pointer_hygiene"
    assert payload["history"][-1]["action"] == "reclassify"


def test_debt_escalate_and_revalidate_update_gate_and_review_state(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    escalate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "escalate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D2_CI_E2E",
            "--gate-level",
            "gate",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    shutil.rmtree(tmp_path / ".omo" / "debt" / "dispatch", ignore_errors=True)
    revalidate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D2_CI_E2E",
            "--reviewed-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert escalate.returncode == 0, escalate.stderr
    assert revalidate.returncode == 0, revalidate.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "D2_CI_E2E.yaml").read_text(encoding="utf-8"))
    assert payload["gate_level"] == "gate"
    assert payload["last_reviewed_at"] == "2026-06-11T00:00:00Z"
    assert payload["history"][-2]["action"] == "escalate"
    assert payload["history"][-1]["action"] == "revalidate"


def test_debt_close_and_reopen_update_lifecycle_state(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    close = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "close",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D3_EU_PRICING",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    reopen = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "reopen",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D3_EU_PRICING",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert close.returncode == 0, close.stderr
    assert reopen.returncode == 0, reopen.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "D3_EU_PRICING.yaml").read_text(encoding="utf-8"))
    assert payload["lifecycle_state"] == "identified"
    assert payload["history"][-2]["action"] == "close"
    assert payload["history"][-1]["action"] == "reopen"


def test_debt_refresh_fails_on_invalid_next_review_timestamp(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    broken_item = tmp_path / ".omo" / "debt" / "items" / "SB_UNTESTED_PKGS.yaml"
    payload = yaml.safe_load(broken_item.read_text(encoding="utf-8"))
    payload["next_review_at"] = "not-a-timestamp"
    broken_item.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

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

    assert result.returncode != 0
    assert "not-a-timestamp" in result.stderr


def test_debt_dispatch_requires_owner_routing_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    (debt_dir / "owner-routing").mkdir(parents=True, exist_ok=True)

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

    assert result.returncode != 0
    assert "owner-routing/current.yaml" in result.stderr


def test_debt_dispatch_fails_on_duplicate_timestamp_run(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    dispatch_dir = tmp_path / ".omo" / "debt" / "dispatch"
    run_slug = "2026-06-10T00-00-00Z"
    run_yaml = dispatch_dir / "runs" / f"{run_slug}.yaml"
    run_md = dispatch_dir / "runs" / f"{run_slug}.md"
    run_yaml.parent.mkdir(parents=True, exist_ok=True)
    run_yaml.write_text("existing: true\n", encoding="utf-8")
    run_md.write_text("existing markdown\n", encoding="utf-8")

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

    assert result.returncode != 0
    assert run_yaml.read_text(encoding="utf-8") == "existing: true\n"
    assert run_md.read_text(encoding="utf-8") == "existing markdown\n"
    assert run_slug in result.stderr


def test_debt_approve_requires_dispatch_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/current.yaml" in result.stderr


def test_debt_approve_writes_current_and_record_files_for_gate_item(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    approved_at = "2026-06-11T00:00:00Z"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            approved_at,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "approved SB_DECOMPOSITION"

    current_path = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION" / "current.yaml"
    record_path = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION" / "records" / "2026-06-11T00-00-00Z.yaml"
    current = yaml.safe_load(current_path.read_text(encoding="utf-8"))
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))

    assert current == record
    assert current == {
        "item_id": "SB_DECOMPOSITION",
        "approved_by": "omo-governance",
        "approved_at": approved_at,
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "approval_scope": "execute_revalidate",
    }


def test_debt_approve_rejects_non_gate_item_and_duplicate_record(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    non_gate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert non_gate.returncode != 0
    assert "gate" in non_gate.stderr

    record_path = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION" / "records" / "2026-06-11T00-00-00Z.yaml"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text("existing: true\n", encoding="utf-8")

    duplicate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert duplicate.returncode != 0
    assert record_path.read_text(encoding="utf-8") == "existing: true\n"
    assert "2026-06-11T00-00-00Z" in duplicate.stderr


def test_debt_revalidate_gate_item_requires_matching_approval(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    item_path = tmp_path / ".omo" / "debt" / "items" / "SB_DECOMPOSITION.yaml"
    before = yaml.safe_load(item_path.read_text(encoding="utf-8"))
    run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-11T00:00:00Z",
            "--dispatch-run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    after = yaml.safe_load(item_path.read_text(encoding="utf-8"))
    assert result.returncode != 0
    assert "approvals/SB_DECOMPOSITION/current.yaml" in result.stderr
    assert after == before


def test_debt_revalidate_dispatched_item_requires_dispatch_run_ref(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    item_path = tmp_path / ".omo" / "debt" / "items" / "SB_UNTESTED_PKGS.yaml"
    before = yaml.safe_load(item_path.read_text(encoding="utf-8"))

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    after = yaml.safe_load(item_path.read_text(encoding="utf-8"))
    assert result.returncode != 0
    assert "--dispatch-run-ref" in result.stderr
    assert after == before


def test_debt_revalidate_rejects_stale_dispatch_run_ref(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T00:00:00Z",
            "--dispatch-run-ref",
            ".omo/debt/dispatch/runs/2026-06-09T00-00-00Z.yaml",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "latest dispatch run" in result.stderr


def test_debt_revalidate_writes_execution_record_for_dispatched_item(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T12:00:00Z",
            "--dispatch-run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    record_path = (
        tmp_path / ".omo" / "debt" / "dispatch" / "executions" / "2026-06-10T00-00-00Z" / "SB_UNTESTED_PKGS.yaml"
    )
    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    assert payload == {
        "item_id": "SB_UNTESTED_PKGS",
        "dispatch_run_ref": run_ref,
        "action": "revalidate",
        "reviewed_at": "2026-06-11T12:00:00Z",
    }


def test_debt_revalidate_gate_item_succeeds_after_matching_approval(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    revalidate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-11T12:00:00Z",
            "--dispatch-run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert approve.returncode == 0, approve.stderr
    assert revalidate.returncode == 0, revalidate.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "SB_DECOMPOSITION.yaml").read_text(encoding="utf-8"))
    assert payload["last_reviewed_at"] == "2026-06-11T12:00:00Z"
    assert payload["history"][-1]["action"] == "revalidate"
    execution_record = yaml.safe_load(
        (
            tmp_path / ".omo" / "debt" / "dispatch" / "executions" / "2026-06-10T00-00-00Z" / "SB_DECOMPOSITION.yaml"
        ).read_text(encoding="utf-8")
    )
    assert execution_record == {
        "item_id": "SB_DECOMPOSITION",
        "dispatch_run_ref": run_ref,
        "action": "revalidate",
        "reviewed_at": "2026-06-11T12:00:00Z",
    }


def test_debt_revalidate_rejects_stale_approval_after_new_dispatch(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    item_path = tmp_path / ".omo" / "debt" / "items" / "SB_DECOMPOSITION.yaml"
    before = yaml.safe_load(item_path.read_text(encoding="utf-8"))
    run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"

    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    dispatch = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-11T12:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    revalidate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-11T13:00:00Z",
            "--dispatch-run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    after = yaml.safe_load(item_path.read_text(encoding="utf-8"))
    assert approve.returncode == 0, approve.stderr
    assert dispatch.returncode == 0, dispatch.stderr
    assert revalidate.returncode != 0
    assert "dispatch run" in revalidate.stderr
    assert after == before


def test_debt_campaign_requires_dispatch_packet_when_run_ref_missing(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "campaign",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/current.yaml" in result.stderr


def test_debt_campaign_writes_latest_run_outputs(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "campaign",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    current_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "campaign" / "current.yaml").read_text(encoding="utf-8"))
    run_yaml = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "campaign" / "runs" / "2026-06-10T00-00-00Z" / "current.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result.returncode == 0, result.stderr
    assert current_yaml == run_yaml
    assert current_yaml["dispatch_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert current_yaml["summary"]["state_counts"] == {
        "pending_approval": 1,
        "ready_to_execute": 8,
        "executed": 0,
    }


def test_debt_campaign_reflects_approval_and_execution_facts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    execute = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T12:00:00Z",
            "--dispatch-run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    campaign = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "campaign",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--run-ref",
            run_ref,
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "campaign" / "current.yaml").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for owner in packet["owners"] for entry in owner["entries"]}

    assert approve.returncode == 0, approve.stderr
    assert execute.returncode == 0, execute.stderr
    assert campaign.returncode == 0, campaign.stderr
    assert entries["SB_DECOMPOSITION"]["campaign_state"] == "ready_to_execute"
    assert entries["SB_UNTESTED_PKGS"]["campaign_state"] == "executed"
    assert entries["SB_UNTESTED_PKGS"]["execution_record_ref"] == (
        ".omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_UNTESTED_PKGS.yaml"
    )


def test_debt_report_requires_dispatch_packet_when_run_ref_missing(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/current.yaml" in result.stderr


def test_debt_report_writes_latest_run_outputs(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    current_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "current.yaml").read_text(encoding="utf-8"))
    run_yaml = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "runs" / "2026-06-10T00-00-00Z" / "current.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result.returncode == 0, result.stderr
    assert current_yaml == run_yaml
    assert current_yaml["summary"]["approval_coverage_rate"] == 0.0
    assert current_yaml["summary"]["execution_completion_rate"] == 0.0


def test_debt_report_reflects_approval_and_execution_facts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    execute = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T12:00:00Z",
            "--dispatch-run-ref",
            ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    report = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "current.yaml").read_text(encoding="utf-8"))

    assert approve.returncode == 0, approve.stderr
    assert execute.returncode == 0, execute.stderr
    assert report.returncode == 0, report.stderr
    assert packet["summary"]["approval_coverage_rate"] == 1.0
    assert packet["summary"]["execution_completion_rate"] == 1 / 9


def test_debt_report_history_requires_dispatch_runs(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/runs" in result.stderr


def test_debt_report_history_writes_latest_and_prior_run_metadata(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_reporting = tmp_path / ".omo" / "debt" / "reporting" / "runs" / "2026-06-01T00-00-00Z" / "current.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text("dispatched_at: '2026-06-01T00:00:00Z'\n", encoding="utf-8")
    older_reporting.parent.mkdir(parents=True, exist_ok=True)
    older_reporting.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-01T02:00:00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "run_stamp": "2026-06-01T00-00-00Z",
                "summary": {
                    "owner_count": 4,
                    "total_items": 9,
                    "state_counts": {"pending_approval": 1, "ready_to_execute": 8, "executed": 0},
                    "gate_item_count": 1,
                    "approved_gate_item_count": 0,
                    "approval_coverage_rate": 0.0,
                    "executed_item_count": 0,
                    "execution_completion_rate": 0.0,
                },
                "owners": [],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml").read_text(encoding="utf-8")
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting history packet"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-10T00-00-00Z",
        "2026-06-01T00-00-00Z",
    ]


def test_debt_report_history_keeps_run_when_reporting_artifact_is_missing(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text("dispatched_at: '2026-06-01T00:00:00Z'\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml").read_text(encoding="utf-8")
    )

    assert result.returncode == 0, result.stderr
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["runs"][1]["reporting_exists"] is False
    assert packet["runs"][1]["reporting_ref"] is None


def test_debt_report_diff_requires_history_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "reporting/history/current.yaml" in result.stderr


def test_debt_report_diff_writes_no_prior_run_packet_for_single_history_run(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "diff" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting diff packet"
    assert packet["diff_status"] == "no_prior_run"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] is None
    assert packet["owners"] is None
    assert packet["summary_diff"]["total_items"]["latest"] == 9
    assert packet["summary_diff"]["total_items"]["prior"] is None


def test_debt_report_diff_rederives_metrics_from_facts_not_history_metadata(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text(
        (tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    approval_dir = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION"
    approval_dir.mkdir(parents=True, exist_ok=True)
    approval_dir.joinpath("current.yaml").write_text(
        yaml.safe_dump(
            {
                "item_id": "SB_DECOMPOSITION",
                "approved_by": "omo-governance",
                "approved_at": "2026-06-01T01:00:00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "approval_scope": "execute_revalidate",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    execution_dir = tmp_path / ".omo" / "debt" / "dispatch" / "executions" / "2026-06-01T00-00-00Z"
    execution_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.joinpath("SB_UNTESTED_PKGS.yaml").write_text(
        yaml.safe_dump(
            {
                "item_id": "SB_UNTESTED_PKGS",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "executed_at": "2026-06-01T02:00:00Z",
                "reviewed_at": "2026-06-01T02:00:00Z",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    history_path = tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 2,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-02T10:52:31Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T02:00:00Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "diff" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["diff_status"] == "diff_available"
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": 9, "delta": 0}
    assert packet["summary_diff"]["approval_coverage_rate"] == {"latest": 0.0, "prior": 1.0, "delta": -1.0}
    assert packet["summary_diff"]["executed_item_count"] == {"latest": 0, "prior": 1, "delta": -1}


def test_debt_report_diff_writes_owner_diff_from_rederived_run_facts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    latest_run = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml"
    prior_run = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    prior_payload = yaml.safe_load(latest_run.read_text(encoding="utf-8"))
    prior_payload["dispatched_at"] = "2026-06-01T00:00:00Z"
    prior_payload["latest_run_ref"] = ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml"
    removed_owner = prior_payload["owners"][3]
    removed_owner["owner"] = "retired-governance"
    for entry in removed_owner["entries"]:
        entry["owner"] = "retired-governance"
    prior_payload["owners"] = [
        removed_owner,
        prior_payload["owners"][1],
        prior_payload["owners"][0],
    ]
    prior_payload["owners"][0]["entries"] = prior_payload["owners"][0]["entries"][:2]
    prior_payload["owners"][1]["entries"] = prior_payload["owners"][1]["entries"][:1]
    prior_payload["owners"][2]["entries"] = prior_payload["owners"][2]["entries"][:3]
    prior_run.parent.mkdir(parents=True, exist_ok=True)
    prior_run.write_text(yaml.safe_dump(prior_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    history_path = tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 2,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "diff" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "sharedbrain-governance",
    ]
    assert packet["owners"]["compared"][0]["item_count"]["delta"] == 0
    assert packet["owners"]["compared"][1]["item_count"]["delta"] == 1
    assert packet["owners"]["added"] == [
        {"owner": "omo-governance"},
        {"owner": "platform-governance"},
    ]
    assert packet["owners"]["removed"] == [{"owner": "retired-governance"}]


def test_debt_report_trend_requires_history_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "reporting/history/current.yaml" in result.stderr


def test_debt_report_trend_writes_insufficient_history_packet_for_single_history_run(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting trend packet"
    assert packet["trend_status"] == "insufficient_history"
    assert packet["window_run_count"] == 1
    assert packet["oldest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == ["2026-06-10T00-00-00Z"]
    assert packet["intervals"] == []


def test_debt_report_trend_reads_history_summary_metadata_not_raw_facts(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    history_path = debt_dir / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 3,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 1,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 1 / 9,
                    },
                    {
                        "run_stamp": "2026-05-20T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-20T00:00:00Z",
                        "total_items": 10,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]
    assert packet["intervals"] == [
        {
            "from_run_stamp": "2026-05-20T00-00-00Z",
            "to_run_stamp": "2026-06-01T00-00-00Z",
            "total_items_delta": -1,
            "executed_item_count_delta": 1,
            "approval_coverage_rate_delta": 1.0,
            "execution_completion_rate_delta": 1 / 9,
        },
        {
            "from_run_stamp": "2026-06-01T00-00-00Z",
            "to_run_stamp": "2026-06-10T00-00-00Z",
            "total_items_delta": 0,
            "executed_item_count_delta": -1,
            "approval_coverage_rate_delta": -1.0,
            "execution_completion_rate_delta": -(1 / 9),
        },
    ]


def test_debt_report_trend_fails_closed_on_missing_history_reporting_metadata(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    history_path = debt_dir / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 2,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": None,
                        "reporting_exists": False,
                        "report_generated_at": None,
                        "total_items": None,
                        "executed_item_count": None,
                        "approval_coverage_rate": None,
                        "execution_completion_rate": None,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "missing reporting trend metadata for run: 2026-06-01T00-00-00Z" in result.stderr


def test_debt_report_trend_accepts_last_window_override(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    history_path = debt_dir / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 3,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 1,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 1 / 9,
                    },
                    {
                        "run_stamp": "2026-05-20T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-20T00:00:00Z",
                        "total_items": 10,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--last",
            "2",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["window_requested"] == 2
    assert packet["window_run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_debt_report_trend_rejects_non_positive_last_window(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--last",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "value must be >= 1" in result.stderr


def test_debt_report_trend_accepts_inclusive_run_range(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    history_path = debt_dir / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 4,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 1,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 1 / 9,
                    },
                    {
                        "run_stamp": "2026-05-20T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-20T00:00:00Z",
                        "total_items": 10,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-05-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-10T00:00:00Z",
                        "total_items": 11,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--from-run-stamp",
            "2026-05-20T00-00-00Z",
            "--to-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["from_run_stamp_requested"] == "2026-05-20T00-00-00Z"
    assert packet["to_run_stamp_requested"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_debt_report_trend_rejects_partial_run_range(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--from-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "range mode requires both from-run-stamp and to-run-stamp" in result.stderr


def test_debt_report_trend_rejects_last_with_run_range(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--last",
            "2",
            "--from-run-stamp",
            "2026-06-01T00-00-00Z",
            "--to-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "--last cannot be combined with --from-run-stamp or --to-run-stamp" in result.stderr
