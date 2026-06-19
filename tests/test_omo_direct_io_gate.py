from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from omo.omo_lint import (
    cmd_lint_direct_omo_io,
    cmd_lint_self_evolution_approval,
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


def test_cmd_lint_self_evolution_approval_passes_for_planned_only(tmp_path: Path, capsys) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-sample\n"
        "status: planned\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n",
        encoding="utf-8",
    )

    rc = cmd_lint_self_evolution_approval(str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint self-evolution-approval pass" in captured.out


def test_cmd_lint_task_policy_matches_self_evolution_alias(tmp_path: Path, capsys) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-sample\n"
        "status: planned\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n",
        encoding="utf-8",
    )

    rc = cmd_lint_task_policy("self-evolution-approval", str(tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "omo lint self-evolution-approval pass" in captured.out


def test_cmd_lint_self_evolution_approval_blocks_missing_fields_and_active_leak(tmp_path: Path, capsys) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-bad.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-bad\n"
        "status: planned\n"
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
