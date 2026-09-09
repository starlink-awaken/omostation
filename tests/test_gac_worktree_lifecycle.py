import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"
PRUNER_SCRIPT = ROOT / "bin" / "gac" / "prune-zombie-worktrees.py"


def _load_pruner():
    spec = importlib.util.spec_from_file_location("test_prune_zombie_worktrees", PRUNER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PRUNER = _load_pruner()


def test_claim_creates_and_cleans_initialization_marker() -> None:
    source = CLAIM_SCRIPT.read_text()

    marker_assignment = 'claim_in_progress="$WS_PARENT/.ws-$session.claiming"'
    guard_assignment = 'lifecycle_guard="$WS_PARENT/.ws-$session.lifecycle-lock"'
    marker_creation = ': > "$claim_in_progress"'
    marker_cleanup = "cleanup_claim_marker"

    assert marker_assignment in source
    assert guard_assignment in source
    assert marker_creation in source
    assert source.index(marker_assignment) < source.index(guard_assignment) < source.index(marker_creation)
    assert 'mkdir -m 700 "$lifecycle_guard"' in source
    assert 'rmdir "$lifecycle_guard"' in source
    assert source.count(marker_cleanup) >= 3
    assert "trap cleanup_claim_marker EXIT INT TERM" in source
    assert "trap - EXIT INT TERM" in source


def test_pruner_skips_worktree_during_claim_initialization(tmp_path: Path) -> None:
    worktree = tmp_path / "ws-half-init"
    marker = tmp_path / ".ws-half-init.claiming"
    worktree.mkdir()
    marker.touch()

    zombies = PRUNER.scan_zombies(tmp_path, ttl_days=0)

    assert zombies == [
        {
            "path": str(worktree),
            "reasons": ["claim-in-progress"],
            "session": "half-init",
            "skip": True,
        }
    ]


def test_failed_worktree_removal_does_not_release_claim_or_report_success(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    orphan = tmp_path / "ws-orphan"
    orphan.mkdir()
    (orphan / ".git").touch()
    released: list[str] = []
    remove_calls: list[list[str]] = []

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, {str(workspace)}))
    monkeypatch.setattr(PRUNER, "_claim_release", released.append)
    monkeypatch.setattr(PRUNER, "_cleanup_guard", lambda _branch: None)
    monkeypatch.setattr(
        PRUNER,
        "scan_zombies",
        lambda _parent, _ttl: [
            {
                "path": str(orphan),
                "reasons": ["idle-8.0d"],
                "session": "orphan",
                "branch": "agent/test-orphan",
            }
        ],
    )

    def _failed_remove(command, **_kwargs):
        if command[:4] == ["git", "-C", str(orphan), "status"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:4] == ["git", "-C", str(orphan), "rev-parse"]:
            return subprocess.CompletedProcess(command, 0, "agent/test-orphan\n", "")
        remove_calls.append(list(command))
        return subprocess.CompletedProcess(command, 1, "", "not a registered worktree")

    monkeypatch.setattr(PRUNER.subprocess, "run", _failed_remove)

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert remove_calls == [["git", "worktree", "remove", "--force", str(orphan)]]
    assert released == []
    assert orphan.exists()
    assert "删除失败" in output
    assert "实删 0" in output


def test_marker_appearing_after_scan_blocks_enforce_effects(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    candidate = tmp_path / "ws-raced"
    candidate.mkdir()
    marker = tmp_path / ".ws-raced.claiming"
    effects: list[object] = []

    def _scan_then_claim(_parent: Path, _ttl: int) -> list[dict]:
        marker.touch()
        return [{"path": str(candidate), "reasons": ["no-gitfile"], "session": "raced"}]

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "scan_zombies", _scan_then_claim)
    monkeypatch.setattr(PRUNER, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, {str(workspace)}))
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))
    monkeypatch.setattr(PRUNER.subprocess, "run", lambda command, **_kwargs: effects.append(list(command)))

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert effects == []
    assert candidate.exists()
    assert marker.exists()
    assert "claim-in-progress" in output
    assert "实删 0" in output


def test_registration_appearing_after_scan_blocks_enforce_effects(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    candidate = tmp_path / "ws-registered"
    candidate.mkdir()
    effects: list[object] = []
    worktree_reads = 0

    def _registered_worktrees() -> tuple[bool, set[str]]:
        nonlocal worktree_reads
        worktree_reads += 1
        paths = {str(workspace)} if worktree_reads == 1 else {str(workspace), str(candidate)}
        return True, paths

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(
        PRUNER,
        "scan_zombies",
        lambda _parent, _ttl: [{"path": str(candidate), "reasons": ["no-gitfile"], "session": "registered"}],
    )
    monkeypatch.setattr(PRUNER, "_registered_worktrees", _registered_worktrees)
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))
    monkeypatch.setattr(PRUNER.subprocess, "run", lambda command, **_kwargs: effects.append(list(command)))

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert effects == []
    assert candidate.exists()
    assert worktree_reads >= 2
    assert "registered" in output
    assert "实删 0" in output


def test_dirtying_after_scan_blocks_enforce_effects(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    candidate = tmp_path / "ws-dirty-race"
    candidate.mkdir()
    (candidate / ".git").touch()
    effects: list[object] = []

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(
        PRUNER,
        "scan_zombies",
        lambda _parent, _ttl: [
            {
                "path": str(candidate),
                "reasons": ["idle-8.0d"],
                "session": "dirty-race",
                "branch": "agent/test-dirty-race",
            }
        ],
    )
    monkeypatch.setattr(PRUNER, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, {str(workspace)}))
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))

    def _dirty_status(command, **_kwargs):
        if command[:4] == ["git", "-C", str(candidate), "status"]:
            return subprocess.CompletedProcess(command, 0, " M changed.txt\n", "")
        effects.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(PRUNER.subprocess, "run", _dirty_status)

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert effects == []
    assert candidate.exists()
    assert "dirty-worktree" in output
    assert "实删 0" in output


def test_claim_lifecycle_guard_blocks_pruner_enforce(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    candidate = tmp_path / "ws-guarded"
    candidate.mkdir()
    (tmp_path / ".ws-guarded.lifecycle-lock").mkdir()
    effects: list[object] = []

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, set()))
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))
    monkeypatch.setattr(PRUNER.subprocess, "run", lambda command, **_kwargs: effects.append(list(command)))

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert effects == []
    assert candidate.exists()
    assert "lifecycle-guard-held" in output
    assert "实删 0" in output


def test_unprovable_worktree_registry_fails_closed(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    (tmp_path / "ws-unprovable").mkdir()
    effects: list[object] = []

    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (False, set()))
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))
    monkeypatch.setattr(PRUNER.subprocess, "run", lambda command, **_kwargs: effects.append(list(command)))

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 2

    output = capsys.readouterr().out
    assert effects == []
    assert "registered-state-unprovable" in output
    assert (tmp_path / "ws-unprovable").exists()


def test_registered_worktree_reader_preserves_command_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        PRUNER.subprocess,
        "run",
        lambda actual, **_kwargs: subprocess.CompletedProcess(actual, 128, "", "registry unavailable"),
    )

    assert PRUNER._registered_worktrees() == (False, set())


def test_registered_worktree_reader_parses_absolute_porcelain_paths(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "Workspace"
    child = tmp_path / "ws-child"
    porcelain = f"worktree {root}\nHEAD abc123\n\nworktree {child}\nHEAD def456\n"
    monkeypatch.setattr(
        PRUNER.subprocess,
        "run",
        lambda actual, **_kwargs: subprocess.CompletedProcess(actual, 0, porcelain, ""),
    )

    assert PRUNER._registered_worktrees() == (True, {str(root), str(child)})
