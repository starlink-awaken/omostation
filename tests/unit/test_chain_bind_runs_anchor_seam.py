"""The runs plane is machine-wide shared state reached through a lazy symlink bridge.

``chain_bind`` read ``workspace / ".omo/_delivery/agent-workflows/runs"`` directly, while
that directory is only a symlink to the canonical checkout once *this* checkout has itself
run a workflow state operation (``ensure_delivery_anchor()`` is called from ``core._runner_path``
and nowhere else). A checkout that never did — the normal shape of a closeout worktree — saw
zero runs and every chain verdict came back ``missing_bet_binding`` for a run that existed and
was bound. Measured 2026-10-19 on 10 local checkouts: 5 bridged, 4 without the directory, 1 the
canonical one. (BET-Y2Q4-T10-257, spec
``docs/superpowers/specs/2026-10-19-chain-bind-runs-anchor-seam.md``.)

C2 pins the other half: when no anchor is locatable the read must be byte-identical to the
pre-seam behaviour, so CI clean checkouts and fresh clones keep their current readings.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHAIN_MOD = ROOT / "bin/plan/chain_bind.py"

FIXTURE_BET_ID = "BET-Y9Q9-T0-001"
FIXTURE_RUN_ID = "20261019T000000Z-bet-execution-deadbeef"
ANCHOR_ENV_STATE = "OMOSTATION_STATE_ROOT"
ANCHOR_ENV_ROOT = "OMOSTATION_ROOT"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BIND = _load(CHAIN_MOD, "chain_bind_runs_anchor_seam")

SEAM_SOURCE = ROOT / "projects/omo/src/omo/workflow/delivery_anchor.py"


def _install_seam(monkeypatch) -> None:
    """Make ``from omo.workflow.delivery_anchor import …`` resolvable in any device.

    The seam is a pure function of the workspace handed to it, but the import binds to
    whatever copy of ``omo`` the interpreter happens to see — and a minimal-dependency run
    (``uv run --no-project``) sees none, which is C2's degrade-to-local path, not a verdict
    about the seam. Loading the copy that lives in the checkout under test and registering it
    for the duration of one test keeps ISC-1 measuring the seam instead of the venv layout.
    """
    assert SEAM_SOURCE.is_file(), f"seam source absent from this checkout: {SEAM_SOURCE}"
    package = types.ModuleType("omo")
    package.__path__ = []  # type: ignore[attr-defined]
    workflow = types.ModuleType("omo.workflow")
    workflow.__path__ = []  # type: ignore[attr-defined]
    delivery = _load(SEAM_SOURCE, "omo.workflow.delivery_anchor")
    workflow.delivery_anchor = delivery
    monkeypatch.setitem(sys.modules, "omo", package)
    monkeypatch.setitem(sys.modules, "omo.workflow", workflow)
    monkeypatch.setitem(sys.modules, "omo.workflow.delivery_anchor", delivery)


def _writes_checkout_plane(source: str) -> list[int]:
    """Lines where ``chain_bind`` would touch the bridge itself (contract C4)."""
    tree = ast.parse(source)
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in {"ensure_delivery_anchor", "_merge_migrate"}:
                hits.append(node.lineno)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in {"ensure_delivery_anchor", "_merge_migrate"}:
                    hits.append(node.lineno)
    return sorted(set(hits))


def _git(cwd: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _write_runs_dir(root: Path, run_id: str, bet_id: str) -> Path:
    runs = root / BIND.RUNS_REL
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run_id}.yaml").write_text(
        yaml.safe_dump(
            {"run_id": run_id, "bet_id": bet_id, "workflow_id": "bet-execution", "status": "active"},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return runs


@pytest.fixture
def bridged_pair(tmp_path, monkeypatch):
    """Canonical checkout with a bound run + a linked worktree of it with no bridge."""
    for name in (ANCHOR_ENV_STATE, ANCHOR_ENV_ROOT):
        monkeypatch.delenv(name, raising=False)
    _install_seam(monkeypatch)
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    docs = canonical / "docs"
    docs.mkdir()
    (docs / "project-registry.yaml").write_text("projects: []\n", encoding="utf-8")
    (docs / "STRATEGY-3YEAR-PLAN-2026H2-2029.md").write_text(
        f"# north star\n\n{BIND.NORTH_STAR_SENTENCE}\n", encoding="utf-8"
    )
    (docs / "plans").mkdir()
    bet = {"id": FIXTURE_BET_ID, "retro": "required", "status": "in_progress"}
    (docs / "plans" / "3y-bet-ledger.yaml").write_text(
        yaml.safe_dump({"bets": [bet]}, allow_unicode=True), encoding="utf-8"
    )
    retros = canonical / BIND.RETRO_REL
    retros.mkdir(parents=True)
    (retros / f"{FIXTURE_BET_ID}.md").write_text(f"bet_id: {FIXTURE_BET_ID}\n", encoding="utf-8")
    (canonical / ".gitignore").write_text(".omo/_delivery/\n", encoding="utf-8")
    _git(canonical, "init", "-q", "-b", "main", ".")
    _git(canonical, "add", "-A")
    _git(
        canonical,
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        "fixture",
    )
    worktree = tmp_path / "wt"
    _git(canonical, "worktree", "add", "--detach", "-q", str(worktree), "HEAD")
    _write_runs_dir(canonical, FIXTURE_RUN_ID, FIXTURE_BET_ID)
    return canonical, worktree, bet


def _direct_run_read_lines(source: str) -> list[int]:
    """Line numbers where ``<name> / RUNS_REL`` is evaluated *outside* ``runs_dir_for``.

    One scan serves both sides of ISC-4: the same function reports the pre-fix count and the
    post-fix zero, so "fixed" cannot be an artefact of a detector that never fires.
    """
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        right = node.right
        if not (isinstance(right, ast.Name) and right.id == "RUNS_REL"):
            continue
        if not isinstance(node.left, ast.Name):
            continue
        holder = _enclosing_function(tree, node)
        if holder == "runs_dir_for":
            continue
        lines.append(node.lineno)
    return sorted(lines)


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node.name
    return None


def test_no_bridge_worktree_reads_canonical_runs(bridged_pair):
    """ISC-1 — the seam is what makes the run visible, not the fixture."""
    canonical, worktree, bet = bridged_pair
    assert (worktree / BIND.LEDGER_REL).is_file()
    assert not (worktree / BIND.RUNS_REL).exists()
    assert BIND.runs_dir_for(worktree) == canonical / BIND.RUNS_REL
    records = BIND.iter_run_records(worktree)
    assert [r["run_id"] for r in records] == [FIXTURE_RUN_ID]
    verdict = BIND.evaluate_complete(bet, worktree)
    assert "missing_bet_binding" not in verdict.reasons
    assert verdict.ok is True


def test_seam_removed_gives_the_pre_change_reading(bridged_pair, monkeypatch):
    """ISC-2 — same fixture, seam disabled ⇒ identical to the old behaviour."""
    _canonical, worktree, bet = bridged_pair
    monkeypatch.setattr(BIND, "runs_dir_for", lambda ws: ws / BIND.RUNS_REL)
    assert BIND.iter_run_records(worktree) == []
    verdict = BIND.evaluate_complete(bet, worktree)
    assert not verdict.ok
    assert verdict.reasons == ["missing_bet_binding"]


def test_reader_never_creates_the_bridge(bridged_pair):
    """C4 — resolving the shared plane must not write the checkout."""
    _canonical, worktree, _bet = bridged_pair
    BIND.iter_run_records(worktree)
    assert not (worktree / ".omo/_delivery").exists()
    assert _writes_checkout_plane(CHAIN_MOD.read_text(encoding="utf-8")) == []


def test_scan_counts_direct_reads_before_and_after(bridged_pair):
    """ISC-4 — one scan yields both the non-zero pre-fix count and the post-fix zero."""
    source = CHAIN_MOD.read_text(encoding="utf-8")
    unfixed = source.replace(
        "runs_dir = runs_dir_for(workspace)",
        "runs_dir = workspace / RUNS_REL",
        1,
    )
    assert unfixed != source, "reconstruction of the pre-fix line must find its target"
    assert len(_direct_run_read_lines(unfixed)) == 1
    assert _direct_run_read_lines(source) == []
    assert _direct_run_read_lines(
        "runs_dir = workspace / RUNS_REL\n"
    ) == [1], "detector must fire on a synthetic violation"


def test_worktree_of_an_unrelated_declared_root_is_not_followed(tmp_path, monkeypatch):
    """C2 — a declared env root that is not this checkout's owner must not leak its runs."""
    other = tmp_path / "declared"
    other.mkdir()
    _write_runs_dir(other, FIXTURE_RUN_ID, FIXTURE_BET_ID)
    workspace = tmp_path / "plain-checkout"
    workspace.mkdir()
    monkeypatch.setenv(ANCHOR_ENV_STATE, str(other))
    assert BIND.runs_dir_for(workspace) == workspace / BIND.RUNS_REL
    assert BIND.iter_run_records(workspace) == []


def test_clean_checkout_without_anchor_reads_its_own_plane(bridged_pair):
    """C2 / CI shape — a real repo that is not a linked worktree keeps the old reading."""
    canonical, _worktree, _bet = bridged_pair
    fresh = canonical.parent / "fresh-clone"
    _git(canonical.parent, "clone", "-q", "--no-hardlinks", str(canonical), str(fresh))
    (fresh / BIND.RUNS_REL).parent.mkdir(parents=True, exist_ok=True)
    assert BIND.runs_dir_for(fresh) == fresh / BIND.RUNS_REL
    assert BIND.iter_run_records(fresh) == []
    _write_runs_dir(fresh, "20261019T000001Z-bet-execution-cafe1234", FIXTURE_BET_ID)
    assert [r["run_id"] for r in BIND.iter_run_records(fresh)] == [
        "20261019T000001Z-bet-execution-cafe1234"
    ]
