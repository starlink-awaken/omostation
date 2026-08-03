from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from omo.omo_lint import (
    cmd_lint_all_task_policies,
    cmd_lint_direct_omo_io,
    cmd_lint_mutation_ledger,
    cmd_lint_mutation_surfaces,
    cmd_lint_self_evolution_approval,
    cmd_lint_sensitive_governed_writes,
    cmd_lint_task_policy,
)
from omo.omo_paths import PROJECTS_DIR


def _run_gatekeeper(target: Path) -> subprocess.CompletedProcess[str]:
    gatekeeper = PROJECTS_DIR / "ecos" / "scripts" / "contract_gatekeeper.py"
    return subprocess.run(
        [sys.executable, str(gatekeeper), str(target)],
        capture_output=True,
        text=True,
        cwd=str(PROJECTS_DIR.parent),
    )


def test_gatekeeper_blocks_direct_omo_write_text(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from pathlib import Path\n"
        "path = Path('.omo/state/system.yaml')\n"
        "path.write_text('boom', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(bad)

    assert result.returncode == 1
    assert "forbidden direct mutation" in result.stdout


def test_gatekeeper_allows_read_only_omo_access(tmp_path: Path) -> None:
    ok = tmp_path / "ok.py"
    ok.write_text(
        "from pathlib import Path\n"
        "content = Path('.omo/state/system.yaml').read_text(encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(ok)

    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_cmd_lint_direct_omo_io_runs_gatekeeper(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "with open('.omo/state/system.yaml', 'w', encoding='utf-8') as handle:\n"
        "    handle.write('boom')\n",
        encoding="utf-8",
    )

    rc = cmd_lint_direct_omo_io([str(bad)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "forbidden direct mutation" in captured.out


def test_cmd_lint_direct_omo_io_fails_when_baseline_not_empty(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    fake_workspace = tmp_path / "workspace"
    baseline_dir = fake_workspace / ".omo" / "_truth" / "registry"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "direct-io-baseline.yaml").write_text(
        "entries:\n  - path: scripts/legacy.py\n    lines: [12]\n",
        encoding="utf-8",
    )
    ok = tmp_path / "ok.py"
    ok.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("omo.omo_lint.WORKSPACE_ROOT", fake_workspace)
    rc = cmd_lint_direct_omo_io([str(ok)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "baseline must be empty" in captured.out
    assert "scripts/legacy.py" in captured.out


def test_cmd_lint_direct_omo_io_passes_when_baseline_empty(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    fake_workspace = tmp_path / "workspace"
    baseline_dir = fake_workspace / ".omo" / "_truth" / "registry"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "direct-io-baseline.yaml").write_text(
        "entries: []\n",
        encoding="utf-8",
    )
    ok = tmp_path / "ok.py"
    ok.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("omo.omo_lint.WORKSPACE_ROOT", fake_workspace)
    rc = cmd_lint_direct_omo_io([str(ok)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "PASS" in captured.out


def test_cmd_lint_direct_omo_io_accepts_multi_document_baseline(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    fake_workspace = tmp_path / "workspace"
    baseline_dir = fake_workspace / ".omo" / "_truth" / "registry"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "direct-io-baseline.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\nentries: []\n",
        encoding="utf-8",
    )
    ok = tmp_path / "ok.py"
    ok.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("omo.omo_lint.WORKSPACE_ROOT", fake_workspace)
    rc = cmd_lint_direct_omo_io([str(ok)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "PASS" in captured.out


def test_cmd_lint_sensitive_governed_writes_blocks_system_yaml_write(
    tmp_path: Path, capsys
) -> None:
    bad = tmp_path / "bad_system.py"
    bad.write_text(
        "from pathlib import Path\n"
        "omo_dir = Path('.omo')\n"
        "state_file = omo_dir / 'state' / 'system.yaml'\n"
        "state_file.write_text('boom', encoding='utf-8')\n",
        encoding="utf-8",
    )

    rc = cmd_lint_sensitive_governed_writes([str(bad)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "direct sensitive write" in captured.out
    assert "system.yaml" in captured.out


def test_cmd_lint_sensitive_governed_writes_blocks_goal_write_yaml_atomic(
    tmp_path: Path, capsys
) -> None:
    bad = tmp_path / "bad_goal.py"
    bad.write_text(
        "from pathlib import Path\n"
        "from omo.omo_io import write_yaml_atomic\n"
        "omo_dir = Path('.omo')\n"
        "goal_file = omo_dir / 'goals' / 'current.yaml'\n"
        "write_yaml_atomic(goal_file, {'goals': []})\n",
        encoding="utf-8",
    )

    rc = cmd_lint_sensitive_governed_writes([str(bad)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "current goal" in captured.out


def test_cmd_lint_sensitive_governed_writes_allows_broker_usage(
    tmp_path: Path, capsys
) -> None:
    ok = tmp_path / "ok_broker.py"
    ok.write_text(
        "from pathlib import Path\n"
        "from omo.omo_ingress import write_system_projection_fields\n"
        "omo_dir = Path('.omo')\n"
        "write_system_projection_fields(omo_dir, updates={'completed_tasks': 1}, actor='test')\n",
        encoding="utf-8",
    )

    rc = cmd_lint_sensitive_governed_writes([str(ok)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "direct_writes=0" in captured.out


def test_cmd_lint_mutation_ledger_passes_with_committed_entry(
    tmp_path: Path, capsys
) -> None:
    artifact_path = (
        tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "tasks" / "TASK-1.yaml"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("kind: planned_task_created\n", encoding="utf-8")
    ledger_path = tmp_path / "runtime" / "omo" / "change-log" / "mutations.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        '{"created_at":"2026-06-23T10:00:00Z","actor":"projects/c2g","action":"create_planned_task","target":".omo/tasks/planned/TASK-1.yaml","artifact_ref":"runtime/omo/_delivery/ingress/tasks/TASK-1.yaml","source_ref":"c2g:task:TASK-1","broker_ref":"projects/omo/src/omo/omo_ingress.py","result":"committed"}\n',
        encoding="utf-8",
    )

    rc = cmd_lint_mutation_ledger(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint mutation-ledger pass" in captured.out


def test_cmd_lint_mutation_ledger_fails_when_artifact_missing(
    tmp_path: Path, capsys
) -> None:
    ledger_path = tmp_path / "runtime" / "omo" / "change-log" / "mutations.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        '{"created_at":"2026-06-23T10:00:00Z","actor":"projects/c2g","action":"create_planned_task","target":".omo/tasks/planned/TASK-1.yaml","artifact_ref":"runtime/omo/_delivery/ingress/tasks/TASK-1.yaml","source_ref":"c2g:task:TASK-1","broker_ref":"projects/omo/src/omo/omo_ingress.py","result":"committed"}\n',
        encoding="utf-8",
    )

    rc = cmd_lint_mutation_ledger(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 1
    assert "artifact_ref missing on disk" in captured.out


def test_gatekeeper_blocks_dynamic_workspace_join_to_omo(tmp_path: Path) -> None:
    bad = tmp_path / "bad_dynamic.py"
    bad.write_text(
        "from pathlib import Path\n"
        "ws_root = Path('/tmp/ws')\n"
        "debt_path = ws_root / '.omo' / 'debt' / 'items' / 'X.yaml'\n"
        "debt_path.write_text('boom', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(bad)

    assert result.returncode == 1
    assert "forbidden direct mutation" in result.stdout


def test_gatekeeper_blocks_helper_atomic_write_to_omo(tmp_path: Path) -> None:
    bad = tmp_path / "bad_helper.py"
    bad.write_text(
        "from pathlib import Path\n"
        "from omo.omo_io import write_yaml_atomic\n"
        "target = Path('.omo/tasks/planned/TASK-X.yaml')\n"
        "write_yaml_atomic(target, {'id': 'TASK-X'})\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(bad)

    assert result.returncode == 1
    assert "forbidden direct mutation via write_yaml_atomic" in result.stdout


def test_gatekeeper_baseline_suppresses_known_violation(tmp_path: Path) -> None:
    bad = tmp_path / "bad_helper.py"
    bad.write_text(
        "from pathlib import Path\n"
        "from omo.omo_io import write_yaml_atomic\n"
        "target = Path('.omo/tasks/planned/TASK-X.yaml')\n"
        "write_yaml_atomic(target, {'id': 'TASK-X'})\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text(
        f"entries:\n  - path: {bad.name}\n    lines: [4]\n",
        encoding="utf-8",
    )

    gatekeeper = PROJECTS_DIR / "ecos" / "scripts" / "contract_gatekeeper.py"
    result = subprocess.run(
        [sys.executable, str(gatekeeper), str(bad), "--baseline-file", str(baseline)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert "baseline_suppressed=1" in result.stdout


def test_cmd_lint_self_evolution_approval_passes_for_planned_only(
    tmp_path: Path, capsys
) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    workers_runs = tmp_path / ".omo" / "workers" / "runs"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    workers_runs.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-sample\n"
        "status: candidate\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n"
        "approval_ref: .omo/workers/runs/OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml\n",
        encoding="utf-8",
    )
    (
        workers_runs
        / "OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml"
    ).write_text(
        "approval_status: requested\n",
        encoding="utf-8",
    )

    rc = cmd_lint_self_evolution_approval(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint self-evolution-approval pass" in captured.out


def test_cmd_lint_task_policy_matches_self_evolution_alias(
    tmp_path: Path, capsys
) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    workers_runs = tmp_path / ".omo" / "workers" / "runs"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    workers_runs.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-sample\n"
        "status: candidate\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n"
        "approval_ref: .omo/workers/runs/OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml\n",
        encoding="utf-8",
    )
    (
        workers_runs
        / "OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml"
    ).write_text(
        "approval_status: requested\n",
        encoding="utf-8",
    )

    rc = cmd_lint_task_policy("self-evolution-approval", str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint self-evolution-approval pass" in captured.out
    assert "matches=1" in captured.out


def test_cmd_lint_all_task_policies_runs_registered_rules(
    tmp_path: Path, capsys
) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    remediation_dir = tmp_path / ".omo" / "tasks" / "remediation"
    workers_runs = tmp_path / ".omo" / "workers" / "runs"
    review_notes = tmp_path / ".omo" / "tasks" / "remediation-notes"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    remediation_dir.mkdir(parents=True)
    workers_runs.mkdir(parents=True)
    review_notes.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-sample\n"
        "status: candidate\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n"
        "approval_ref: .omo/workers/runs/OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml\n",
        encoding="utf-8",
    )
    (
        workers_runs
        / "OPC-P6-SELF-EVOLUTION-sample-promotion-approval-2026-06-19T00-00-00Z.yaml"
    ).write_text(
        "approval_status: requested\n",
        encoding="utf-8",
    )
    (remediation_dir / "TASK-R.yaml").write_text(
        "id: TASK-R\n"
        "status: review\n"
        "human_approval_required: true\n"
        "approval_ref: .omo/workers/runs/TASK-R-promotion-approval-2026-06-19T00-00-00Z.yaml\n"
        "review_note: .omo/tasks/remediation-notes/TASK-R-review.md\n",
        encoding="utf-8",
    )
    (workers_runs / "TASK-R-promotion-approval-2026-06-19T00-00-00Z.yaml").write_text(
        "approval_status: requested\n",
        encoding="utf-8",
    )
    (review_notes / "TASK-R-review.md").write_text(
        "# review\n",
        encoding="utf-8",
    )

    rc = cmd_lint_all_task_policies(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint active-execution-links pass" in captured.out
    assert "omo lint human-approval-ref pass" in captured.out
    assert "omo lint remediation-review-note pass" in captured.out
    assert "omo lint self-evolution-approval pass" in captured.out


def test_cmd_lint_mutation_surfaces_passes_for_aligned_registry(capsys) -> None:
    rc = cmd_lint_mutation_surfaces(str(PROJECTS_DIR.parent))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint mutation-surfaces pass" in captured.out


def test_cmd_lint_self_evolution_approval_blocks_missing_fields_and_active_leak(
    tmp_path: Path, capsys
) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-bad.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-bad\n"
        "status: review\n"
        "approval_required: false\n"
        "human_approval_required: false\n"
        "approval_state: auto\n",
        encoding="utf-8",
    )
    (active_dir / "OPC-P6-SELF-EVOLUTION-leaked.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-leaked\nstatus: active\n",
        encoding="utf-8",
    )

    rc = cmd_lint_self_evolution_approval(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 1
    assert "approval_required must be True" in captured.out
    assert "human_approval_required must be True" in captured.out
    assert "approval_state must be 'awaiting_human'" in captured.out
    assert "leaked into active/" in captured.out
