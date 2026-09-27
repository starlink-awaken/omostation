"""BET-Y2Q4-T10-208 — root-level contract tests for the delivery-state anchor.

Contract surface from the root consumer's perspective: public API shape, the
pure-fallback anchor resolution order, the three byte-identical no-op gates,
production-layout-only trigger discipline, and read/write funnel consistency.
Merge/conflict internals, symlink self-heal and the #4435
``git worktree remove --force`` regression live in the kernel suite
(``projects/omo/tests/test_delivery_anchor.py``) and are deliberately not
repeated here.

H1: every test builds FAKE canonical/worktree trees under ``tmp_path`` and
patches ``HOME`` / ``OMOSTATION_ROOT`` / ``OMOSTATION_STATE_ROOT``. An autouse
guard fingerprints the real worktree's ``.omo/_delivery/agent-workflows``
entry (real directory vs. symlink + ``runs/`` listing and bytes) so no test
here can silently bridge — or even touch — the live governance run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin" / "lib"))
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

import repo_root  # noqa: E402
from omo.workflow import core as core_mod  # noqa: E402
from omo.workflow import delivery_anchor  # noqa: E402
from omo.workflow.delivery_anchor import (  # noqa: E402
    DELIVERY_RELATIVE,
    ensure_delivery_anchor,
    is_worktree_of,
    locate_anchor,
)

REAL_DELIVERY = ROOT / DELIVERY_RELATIVE


def _load_chain_bind():
    """Load ``bin/plan/chain_bind.py`` under a private module name (repo convention)."""
    path = ROOT / "bin" / "plan" / "chain_bind.py"
    name = "_delivery_anchor_contract_chain_bind"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


chain_bind = _load_chain_bind()


# ── H1 guard: the real worktree's delivery state is read-only for this file ──


def _tree_hash(root: Path) -> str:
    """Recursive content hash of a tree (dirs, file bytes, symlink targets)."""
    digest = hashlib.sha256()
    if not root.exists() and not root.is_symlink():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            digest.update(f"{rel}\0link\0{os.readlink(path)}\n".encode())
        elif path.is_dir():
            digest.update(f"{rel}\0dir\n".encode())
        else:
            digest.update(f"{rel}\0file\0".encode())
            digest.update(path.read_bytes())
            digest.update(b"\n")
    return digest.hexdigest()


def _real_delivery_state() -> tuple[str | None, tuple[str, ...], str]:
    """H1 fingerprint: (symlink target or None, runs/ listing, runs/ content hash).

    Locks/events are deliberately excluded so concurrent governance activity in
    the shared checkout cannot make this guard flaky; the run records (the #4435
    casualty) are what must stay byte-identical.
    """
    link = os.readlink(REAL_DELIVERY) if REAL_DELIVERY.is_symlink() else None
    runs = REAL_DELIVERY / "runs"
    if not runs.is_dir():
        return link, (), hashlib.sha256(b"").hexdigest()
    names = tuple(sorted(path.name for path in runs.iterdir()))
    digest = hashlib.sha256()
    for name in names:
        path = runs / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return link, names, digest.hexdigest()


@pytest.fixture(autouse=True)
def _guard_real_delivery_state():
    """Pin the real worktree's delivery entry across each test in this file."""
    before = _real_delivery_state()
    yield
    assert _real_delivery_state() == before, (
        "real worktree .omo/_delivery/agent-workflows was modified by a contract test"
    )


# ── fakes (never the real checkout) ──────────────────────────────────────────


def _fake_canonical(root: Path) -> Path:
    canonical = root / "canonical"
    (canonical / "docs").mkdir(parents=True, exist_ok=True)
    (canonical / repo_root.MARKER).write_text("schema: project-registry/v1\n", encoding="utf-8")
    (canonical / ".git" / "worktrees" / "wt").mkdir(parents=True, exist_ok=True)
    return canonical


def _fake_worktree(root: Path, gitdir: Path | None = None, name: str = "wt") -> Path:
    ws = root / f"ws-{name}"
    ws.mkdir(parents=True, exist_ok=True)
    target = gitdir if gitdir is not None else root / "canonical" / ".git" / "worktrees" / name
    (ws / ".git").write_text(f"gitdir: {target}\n", encoding="utf-8")
    return ws


def _anchor_env(monkeypatch, canonical: Path) -> None:
    monkeypatch.setenv("OMOSTATION_ROOT", str(canonical))
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(canonical.parent / "fake-home"))


# ── 1. public API contract ───────────────────────────────────────────────────


def test_public_api_exports_documented_callables_with_signatures() -> None:
    for name in ("locate_anchor", "is_worktree_of", "ensure_delivery_anchor"):
        assert callable(getattr(delivery_anchor, name)), name

    locate_sig = inspect.signature(delivery_anchor.locate_anchor)
    assert list(locate_sig.parameters) == []
    assert locate_sig.return_annotation == "Path | None"

    worktree_sig = inspect.signature(delivery_anchor.is_worktree_of)
    assert list(worktree_sig.parameters) == ["ws", "anchor"]
    assert worktree_sig.return_annotation == "bool"

    ensure_sig = inspect.signature(delivery_anchor.ensure_delivery_anchor)
    assert list(ensure_sig.parameters) == ["ws"]
    assert ensure_sig.return_annotation == "Path | None"

    assert DELIVERY_RELATIVE == Path(".omo") / "_delivery" / "agent-workflows"


def test_env_names_and_marker_are_pinned_across_anchor_and_repo_root() -> None:
    """Cross-boundary contract: the anchor reads the same env names / marker as
    ``bin/lib/repo_root.py`` (source-string pin, spec §Test strategy 2)."""
    assert delivery_anchor.STATE_ROOT_ENV == repo_root.STATE_ROOT_ENV == "OMOSTATION_STATE_ROOT"
    assert delivery_anchor.CANONICAL_ROOT_ENV == "OMOSTATION_ROOT"
    assert delivery_anchor.MARKER == repo_root.MARKER == Path("docs") / "project-registry.yaml"

    source = inspect.getsource(delivery_anchor)
    for literal in ("OMOSTATION_STATE_ROOT", "OMOSTATION_ROOT"):
        assert literal in source, f"resolver must read {literal} literally"


# ── 2. pure-fallback anchor resolution order ─────────────────────────────────


def test_anchor_resolution_order_is_pure_fallback(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    state_root = tmp_path / "state-root"
    state_root.mkdir()
    home = tmp_path / "home"
    (home / "Workspace" / "docs").mkdir(parents=True, exist_ok=True)
    (home / "Workspace" / repo_root.MARKER).write_text("schema: project-registry/v1\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    # ① declared profile env wins, marker not required
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state_root))
    monkeypatch.setenv("OMOSTATION_ROOT", str(canonical))
    assert locate_anchor() == state_root

    # ② no declared state root → OMOSTATION_ROOT + marker
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    assert locate_anchor() == canonical

    # ②b an OMOSTATION_ROOT without the marker is rejected, not trusted
    unmarked = tmp_path / "unmarked-root"
    unmarked.mkdir()
    monkeypatch.setenv("OMOSTATION_ROOT", str(unmarked))
    assert locate_anchor() == home / "Workspace"

    # ③ ~/Workspace + marker
    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)
    assert locate_anchor() == home / "Workspace"

    # ④ nothing locatable → None (CI-safe no-op, never __file__ fallback)
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    assert locate_anchor() is None

    # ④b a declared-but-missing state root is a hard None, not a silent fallthrough
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path / "missing-state-root"))
    assert locate_anchor() is None


def test_anchor_resolution_matches_repo_root_cross_boundary(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)

    monkeypatch.setenv("OMOSTATION_ROOT", str(canonical))
    assert locate_anchor() == repo_root.canonical_root() == canonical

    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)
    assert locate_anchor() is None
    with pytest.raises(RuntimeError):
        repo_root.canonical_root()

    state_root = tmp_path / "state-root"
    state_root.mkdir()
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state_root))
    assert locate_anchor() == Path(state_root)
    assert repo_root.state_root() == state_root


def test_state_root_env_beats_canonical_root(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    state_root = tmp_path / "state-root"
    state_root.mkdir()
    _anchor_env(monkeypatch, canonical)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state_root))

    assert locate_anchor() == state_root
    assert locate_anchor() != canonical


# ── 3. the three no-op gates are byte-identical contracts ────────────────────


def test_noop_gate_non_worktree_leaves_target_byte_identical(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    _anchor_env(monkeypatch, canonical)
    ws = tmp_path / "ws-clone"
    (ws / ".git").mkdir(parents=True)  # ordinary clone: .git is a directory
    delivery = ws / DELIVERY_RELATIVE
    (delivery / "runs").mkdir(parents=True)
    (delivery / "runs" / "run.yaml").write_text("run_id: run\n", encoding="utf-8")

    before_ws, before_canonical = _tree_hash(ws), _tree_hash(canonical)
    assert ensure_delivery_anchor(ws) is None
    assert not delivery.is_symlink()
    assert _tree_hash(ws) == before_ws
    assert _tree_hash(canonical) == before_canonical


def test_noop_gate_foreign_worktree_leaves_target_byte_identical(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    _anchor_env(monkeypatch, canonical)
    elsewhere = tmp_path / "elsewhere" / ".git" / "worktrees" / "other"
    elsewhere.mkdir(parents=True)
    ws = _fake_worktree(tmp_path, gitdir=elsewhere, name="foreign")
    delivery = ws / DELIVERY_RELATIVE
    (delivery / "runs").mkdir(parents=True)
    (delivery / "runs" / "run.yaml").write_text("run_id: run\n", encoding="utf-8")

    before_ws, before_canonical = _tree_hash(ws), _tree_hash(canonical)
    assert is_worktree_of(ws, canonical) is False
    assert ensure_delivery_anchor(ws) is None
    assert not delivery.is_symlink()
    assert _tree_hash(ws) == before_ws
    assert _tree_hash(canonical) == before_canonical


def test_noop_gate_missing_anchor_leaves_target_byte_identical(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    ws = _fake_worktree(tmp_path)  # a worktree *of* canonical, but no anchor locatable
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    delivery = ws / DELIVERY_RELATIVE
    (delivery / "runs").mkdir(parents=True)
    (delivery / "runs" / "run.yaml").write_text("run_id: run\n", encoding="utf-8")

    assert locate_anchor() is None
    before_ws, before_canonical = _tree_hash(ws), _tree_hash(canonical)
    assert ensure_delivery_anchor(ws) is None
    assert not delivery.is_symlink()
    assert _tree_hash(ws) == before_ws
    assert _tree_hash(canonical) == before_canonical


# ── 4. production layout is the only trigger ─────────────────────────────────


def test_only_production_layout_fires_the_anchor_hook(tmp_path: Path, monkeypatch) -> None:
    canonical = _fake_canonical(tmp_path)
    ws = _fake_worktree(tmp_path)
    _anchor_env(monkeypatch, canonical)

    calls: list[Path] = []

    def _spy(workspace: Path) -> Path | None:
        calls.append(workspace)
        return None

    monkeypatch.setattr(core_mod, "ensure_delivery_anchor", _spy)

    # production layout (registry defaults) → the hook fires on every funnel call
    production = {"runner": {"workspace_root": str(ws)}}
    core_mod.run_state_dir(production)
    core_mod.lock_state_dir(production)
    core_mod.ledger_path(production)
    assert calls == [ws.resolve(), ws.resolve(), ws.resolve()]

    # custom non-default relative runner config → never fires
    calls.clear()
    custom_relative = {
        "runner": {
            "workspace_root": str(ws),
            "run_state_dir": "runs",
            "lock_state_dir": "locks",
            "ledger_path": "events.jsonl",
        }
    }
    core_mod.run_state_dir(custom_relative)
    core_mod.lock_state_dir(custom_relative)
    core_mod.ledger_path(custom_relative)
    assert calls == []

    # absolute runner config → never fires
    calls.clear()
    absolute = {
        "runner": {
            "workspace_root": str(ws),
            "run_state_dir": str(tmp_path / "custom" / "runs"),
            "lock_state_dir": str(tmp_path / "custom" / "locks"),
            "ledger_path": str(tmp_path / "custom" / "events.jsonl"),
        }
    }
    core_mod.run_state_dir(absolute)
    core_mod.lock_state_dir(absolute)
    core_mod.ledger_path(absolute)
    assert calls == []
    assert not (ws / DELIVERY_RELATIVE).exists()
    assert not (ws / DELIVERY_RELATIVE).is_symlink()

    # and the production layout, once the real hook is restored, really bridges
    monkeypatch.setattr(core_mod, "ensure_delivery_anchor", delivery_anchor.ensure_delivery_anchor)
    core_mod.run_state_dir(production)
    link = ws / DELIVERY_RELATIVE
    assert link.is_symlink()
    assert Path(os.readlink(link)) == canonical / DELIVERY_RELATIVE


# ── 5. read/write funnel consistency ─────────────────────────────────────────


def test_run_lock_ledger_funnel_share_one_anchor_and_display_path_stays_dict(
    tmp_path: Path, monkeypatch
) -> None:
    canonical = _fake_canonical(tmp_path)
    ws = _fake_worktree(tmp_path)
    _anchor_env(monkeypatch, canonical)
    registry = {"runner": {"workspace_root": str(ws)}}

    run_dir = core_mod.run_state_dir(registry)
    lock_dir = core_mod.lock_state_dir(registry)
    ledger = core_mod.ledger_path(registry)

    # dict (workspace-relative) paths are unchanged — records never leak canonical paths
    assert run_dir == ws.resolve() / DELIVERY_RELATIVE / "runs"
    assert lock_dir == ws.resolve() / DELIVERY_RELATIVE / "locks"
    assert ledger == ws.resolve() / DELIVERY_RELATIVE / "events.jsonl"

    # ...while all three resolve through the same physical canonical anchor
    anchor = (canonical / DELIVERY_RELATIVE).resolve()
    for path in (run_dir, lock_dir, ledger):
        assert path.resolve().parent == anchor, path
    link = ws / DELIVERY_RELATIVE
    assert link.is_symlink()
    assert Path(os.readlink(link)) == canonical / DELIVERY_RELATIVE

    # writes through each funnel member land in canonical
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run-1.yaml").write_text("run_id: run-1\n", encoding="utf-8")
    (lock_dir / "scope.lock.yaml").write_text("run_id: run-1\n", encoding="utf-8")
    ledger.write_text('{"event":"agent_workflow_start","run_id":"run-1"}\n', encoding="utf-8")
    assert (anchor / "runs" / "run-1.yaml").is_file()
    assert (anchor / "locks" / "scope.lock.yaml").is_file()
    assert (anchor / "events.jsonl").is_file()

    # display_path is pinned to the dict path (untouched by the bridge)
    monkeypatch.setattr(core_mod, "WORKSPACE", ws.resolve())
    assert core_mod.display_path(run_dir) == (DELIVERY_RELATIVE / "runs").as_posix()
    assert core_mod.display_path(lock_dir) == (DELIVERY_RELATIVE / "locks").as_posix()
    assert core_mod.display_path(ledger) == (DELIVERY_RELATIVE / "events.jsonl").as_posix()
    assert str(anchor) not in core_mod.display_path(run_dir)

    # root read path (chain_bind) sees what the kernel wrote through the anchor
    runs = chain_bind.iter_run_records(ws)
    assert [record["run_id"] for record in runs] == ["run-1"]
    assert Path(runs[0]["_path"]).resolve() == (anchor / "runs" / "run-1.yaml").resolve()
