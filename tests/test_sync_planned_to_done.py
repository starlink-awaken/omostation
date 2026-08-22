"""Tests for bin/plan/sync-planned-to-done.py

All integration tests run against a synthetic workspace built in tmp_path,
copying the script under test and a small set of fixtures. No test touches
the real `.omo/tasks/` tree.

Covers:
  - load_done_bets: parses the multi-doc ledger
  - scan_stale_candidates: detects status=candidate whose id is in done set
  - stamp_close: mutates the YAML in place with the documented contract
  - main --apply: produces the documented move + status change
  - main dry-run: emits summary without touching files
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REAL_SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "plan" / "sync-planned-to-done.py"
_MODULE_NAME = "_sync_planned_to_done"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, REAL_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_load_done_bets_includes_known_done(mod, tmp_path: Path):
    """Build a synthetic multi-doc ledger with two done bets + verify."""
    ledger = tmp_path / "3y-bet-ledger.yaml"
    ledger.write_text(
        "---\nstatus: legacy\n---\nbets:\n"
        "  - id: BET-Y1Q1-T1-00\n    status: done\n"
        "  - id: BET-Y3H1-T7-01\n    status: done\n"
        "  - id: BET-FUTURE-T9-99\n    status: blocked\n",
        encoding="utf-8",
    )
    done = mod.load_done_bets(ledger)
    assert "BET-Y1Q1-T1-00" in done
    assert "BET-Y3H1-T7-01" in done
    assert "BET-FUTURE-T9-99" not in done


def test_scan_stale_candidates_skips_already_done_in_done_dir(mod, tmp_path: Path):
    planned = tmp_path / "planned"
    planned.mkdir()
    (planned / "a.yaml").write_text(
        "id: BET-Y1Q1-T1-00\nstatus: candidate\npriority: P0\n", encoding="utf-8"
    )
    (planned / "b.yaml").write_text(
        "id: BET-FUTURE-T9-99\nstatus: candidate\npriority: P0\n", encoding="utf-8"
    )
    stale = mod.scan_stale_candidates({"BET-Y1Q1-T1-00"}, planned)
    assert [p.name for p in stale] == ["a.yaml"]


def test_scan_stale_skips_non_candidate_status(mod, tmp_path: Path):
    planned = tmp_path / "planned"
    planned.mkdir()
    (planned / "a.yaml").write_text(
        "id: BET-Y1Q1-T1-00\nstatus: candidate\npriority: P0\n", encoding="utf-8"
    )
    (planned / "b.yaml").write_text(
        "id: BET-Y1Q1-T1-00\nstatus: active\npriority: P0\n", encoding="utf-8"
    )
    stale = mod.scan_stale_candidates({"BET-Y1Q1-T1-00"}, planned)
    assert [p.name for p in stale] == ["a.yaml"]


def test_stamp_close_sets_status_done_and_marks_source(mod, tmp_path: Path):
    src = tmp_path / "x.yaml"
    src.write_text(
        "id: BET-Y1Q1-T1-00\nstatus: candidate\npriority: P0\nsource: 3y-bet-ledger\n",
        encoding="utf-8",
    )
    mod.stamp_close(src, "2026-08-22T00:00:00Z")

    after = yaml.safe_load(src.read_text(encoding="utf-8"))
    assert after["status"] == "done"
    assert after["closed_reason"] == "parent-bet-done"
    assert after["done_at"] == "2026-08-22T00:00:00Z"
    assert "planned-to-done-sync" in after["source"]


@pytest.fixture
def synth_workspace(tmp_path: Path) -> Path:
    """Build an isolated workspace with the script + a known ledger + planned/.

    Layout:
      tmp/
        bin/plan/sync-planned-to-done.py   (copy of real script)
        docs/plans/3y-bet-ledger.yaml     (two done bets)
        .omo/tasks/planned/*.yaml         (two stale candidates + one future)
        .omo/tasks/archived/done/         (cold tree destination)
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "bin" / "plan").mkdir(parents=True)
    (ws / "docs" / "plans").mkdir(parents=True)
    (ws / ".omo" / "tasks" / "planned").mkdir(parents=True)
    (ws / ".omo" / "tasks" / "archived" / "done").mkdir(parents=True)

    shutil.copy(REAL_SCRIPT, ws / "bin" / "plan" / "sync-planned-to-done.py")

    (ws / "docs" / "plans" / "3y-bet-ledger.yaml").write_text(
        "---\nbets:\n  - id: BET-SYN-001\n    status: done\n"
        "  - id: BET-SYN-002\n    status: done\n"
        "  - id: BET-SYN-099\n    status: blocked\n",
        encoding="utf-8",
    )
    planned = ws / ".omo" / "tasks" / "planned"
    (planned / "bet-syn-001.yaml").write_text(
        "id: BET-SYN-001\nstatus: candidate\npriority: P0\nsource: 3y-bet-ledger\n",
        encoding="utf-8",
    )
    (planned / "bet-syn-002.yaml").write_text(
        "id: BET-SYN-002\nstatus: candidate\npriority: P1\nsource: 3y-bet-ledger\n",
        encoding="utf-8",
    )
    (planned / "bet-syn-099.yaml").write_text(
        "id: BET-SYN-099\nstatus: candidate\npriority: P0\nsource: 3y-bet-ledger\n",
        encoding="utf-8",
    )
    return ws


def test_synth_dry_run_no_mutation(synth_workspace: Path):
    proc = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(synth_workspace / "bin" / "plan" / "sync-planned-to-done.py")],
        cwd=synth_workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["apply"] is False
    assert summary["stale_candidate_count"] == 2
    assert sorted(summary["stale_ids"]) == ["bet-syn-001", "bet-syn-002"]

    # planned/ still has all 3 files
    assert len(list((synth_workspace / ".omo" / "tasks" / "planned").glob("*.yaml"))) == 3
    # archived/done/ still empty
    assert len(list((synth_workspace / ".omo" / "tasks" / "archived" / "done").glob("*.yaml"))) == 0


def test_synth_apply_moves_two_files(synth_workspace: Path):
    proc = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(synth_workspace / "bin" / "plan" / "sync-planned-to-done.py"),
         "--apply", "--no-json"],
        cwd=synth_workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

    planned = synth_workspace / ".omo" / "tasks" / "planned"
    cold = synth_workspace / ".omo" / "tasks" / "archived" / "done"

    moved = sorted(p.name for p in cold.glob("*.yaml"))
    assert moved == ["bet-syn-001.yaml", "bet-syn-002.yaml"]
    assert sorted(p.name for p in planned.glob("*.yaml")) == ["bet-syn-099.yaml"]

    # Verify each moved file is stamped done
    for f in cold.glob("bet-syn-*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert data["status"] == "done"
        assert data["closed_reason"] == "parent-bet-done"
        assert "planned-to-done-sync" in data["source"]


def test_synth_apply_is_idempotent(synth_workspace: Path):
    apply = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(synth_workspace / "bin" / "plan" / "sync-planned-to-done.py"),
         "--apply", "--no-json"],
        cwd=synth_workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert apply.returncode == 0, apply.stderr

    second = subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python",
         str(synth_workspace / "bin" / "plan" / "sync-planned-to-done.py")],
        cwd=synth_workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    summary = json.loads(second.stdout)
    assert summary["stale_candidate_count"] == 0