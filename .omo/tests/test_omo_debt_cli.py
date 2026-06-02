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
        "version: 1\nitems_dir: .omo/debt/items\ndashboard_ref: .omo/debt/dashboard/current.yaml\nreview_pack_ref: .omo/debt/reviews/current.md\nreview_queue_ref: .omo/debt/review-queue/current.yaml\naction_packet_ref: .omo/debt/action-packet/current.yaml\nowner_routing_ref: .omo/debt/owner-routing/current.yaml\ndispatch_ref: .omo/debt/dispatch/current.yaml\nseed_items: []\n",
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
