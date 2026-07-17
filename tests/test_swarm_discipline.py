"""G-CONV.7 / ADR-0220: unit tests drive real swarm_discipline helpers."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "bin/gac/swarm_discipline.py"
    spec = importlib.util.spec_from_file_location("swarm_discipline", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_registry_present_and_has_four_gates():
    reg_path = ROOT / ".omo/_truth/registry/swarm-coordination.yaml"
    assert reg_path.is_file()
    text = reg_path.read_text(encoding="utf-8")
    for key in (
        "d1_adr_atomic_claim",
        "d2_branch_occupancy",
        "d3_shared_worktree_claim",
        "d4_escape_hatch",
    ):
        assert key in text
    assert "escape_hatch_exemptions" in text


def test_d1_adr_claim_atomic_and_second_session_blocked(tmp_path):
    m = _load()
    # minimal registry for delivery paths (use defaults under tmp root)
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\ndelivery: {}\nescape_hatch_exemptions: []\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_knowledge/decisions").mkdir(parents=True)
    # seed existing ADR so next is predictable
    (tmp_path / ".omo/_knowledge/decisions/0001-seed.md").write_text("# x\n", encoding="utf-8")

    ok1, r1 = m.acquire_adr_claim(tmp_path, "agent-a")
    assert ok1, r1
    n = r1["number"]
    ok2, r2 = m.acquire_adr_claim(tmp_path, "agent-b", number=n)
    assert not ok2, r2
    assert "claimed" in str(r2.get("error", "")).lower() or "session" in str(r2)


def test_d1_adr_write_requires_claim(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\n", encoding="utf-8"
    )
    (tmp_path / ".omo/_knowledge/decisions").mkdir(parents=True)
    ok, reason = m.check_adr_write_authorized(
        tmp_path, ".omo/_knowledge/decisions/0099-new.md", "s1"
    )
    assert not ok
    assert "claim" in reason.lower()


def test_d2_branch_occupancy_blocks_second_session(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\n", encoding="utf-8"
    )
    ok1, r1 = m.acquire_branch_lock(tmp_path, "sess-a", "work/sess-a")
    assert ok1, r1
    ok2, r2 = m.acquire_branch_lock(tmp_path, "sess-b", "work/sess-a")
    assert not ok2, r2
    assert "occupied" in str(r2.get("error", "")).lower() or "sess-a" in str(r2)


def test_d3_shared_worktree_unclaimed_fails_isolated_ok(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\nshared_worktree_allow_path_globs: ['runtime/**']\n",
        encoding="utf-8",
    )
    ok, viol = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="main",
        claimed_paths=[],
    )
    assert not ok
    assert viol

    ok2, viol2 = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="work/gconv7",
        claimed_paths=[],
    )
    assert ok2
    assert not viol2

    ok3, _ = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="main",
        claimed_paths=["docs/"],
    )
    assert ok3


def test_d4_escape_requires_allowlisted_id(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        """
version: 1
escape_hatch_exemptions:
  - id: submodule-reachability-partial-worktree
    allow: [ci_local_skip, no_verify_push]
    active: true
    reason: test
""",
        encoding="utf-8",
    )
    ok, reason = m.check_escape_hatch(tmp_path, flag="ci_local_skip", escape_id=None)
    assert not ok
    ok2, _ = m.check_escape_hatch(
        tmp_path,
        flag="ci_local_skip",
        escape_id="submodule-reachability-partial-worktree",
    )
    assert ok2
    ok3, _ = m.check_escape_hatch(
        tmp_path, flag="ci_local_skip", escape_id="not-a-real-id"
    )
    assert not ok3


def test_conflict_window_status_open_until_72h(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\nobservation:\n  window_hours: 72\n",
        encoding="utf-8",
    )
    meta = m.start_conflict_window(tmp_path)
    assert "window_start" in meta
    status = m.conflict_window_status(tmp_path)
    assert status["m1_conflict_zero_verdict"] == "window_open"
    assert status["conflict_count"] == 0
    m.emit_conflict_event(tmp_path, "branch_hijack", {"branch": "work/x"})
    status2 = m.conflict_window_status(tmp_path)
    assert status2["conflict_count"] == 1
    assert status2["m1_conflict_zero_verdict"] == "window_open"


def test_wired_entrypoints_reference_gates():
    """Structural: real entrypoints call into swarm discipline (no orphan registry)."""
    wt = (ROOT / "bin/gac/gac-worktree.sh").read_text(encoding="utf-8")
    assert "branch-claim" in wt
    assert "swarm-discipline-cli" in wt
    pre = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "swarm-claim-check" in pre
    push = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "escape-check" in push or "swarm-d4" in push
    adr = (ROOT / "bin/adr/next-adr-id.py").read_text(encoding="utf-8")
    assert "acquire_adr_claim" in adr or "swarm_discipline" in adr
