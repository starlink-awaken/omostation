import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "bin/panorama/panorama-collect.py"


def _collector():
    spec = importlib.util.spec_from_file_location("panorama_workspace_provenance_test", COLLECTOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_observation_binds_the_exact_inventory_and_real_scope(tmp_path, monkeypatch):
    collector = _collector()
    code_root = tmp_path / "code"
    state_root = tmp_path / "state"
    code_root.mkdir()
    lock_root = state_root / ".omo/_delivery/agent-workflows/locks"
    lock_root.mkdir(parents=True)
    (lock_root / "project.lock.yaml").write_text("lock\n", encoding="utf-8")
    listing = (
        f"worktree {code_root}\nHEAD abc\nbranch refs/heads/main\n\n"
        f"worktree {code_root}/task\nHEAD def\nbranch refs/heads/task\n\n"
    )
    monkeypatch.setattr(
        collector.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=listing),
    )

    evidence = collector._collect_workspace_hygiene_observation(
        code_root=code_root,
        runtime_root=state_root,
    )
    expected = {
        "worktrees": [
            {"path": str(code_root), "branch": "refs/heads/main"},
            {"path": f"{code_root}/task", "branch": "refs/heads/task"},
        ],
        "total_worktrees": 2,
        "lock_files": [str(lock_root / "project.lock.yaml")],
        "total_lock_files": 1,
    }

    assert evidence["status"] == "OBSERVED"
    assert evidence["value"] == expected
    assert evidence["source_digest"] == collector._sha256_bytes(collector._canonical_json_bytes(expected))
    assert evidence["provenance"]["source_ref"] == "bin/panorama/panorama-collect.py::collect_workspace_hygiene"
    assert evidence["provenance"]["collector_sha256"] == collector._sha256_bytes(COLLECTOR.read_bytes())
    assert evidence["provenance"]["scope"] == {"code_root": str(code_root), "state_root": str(state_root)}
    assert evidence["observed_at"] is not None
    assert evidence["last_success_at"] == evidence["observed_at"]
    assert evidence["last_attempt_at"] >= evidence["observed_at"]


def test_worktree_read_failure_stays_unknown_instead_of_claiming_zero(tmp_path, monkeypatch):
    collector = _collector()
    code_root = tmp_path / "code"
    state_root = tmp_path / "state"
    code_root.mkdir()
    (state_root / ".omo/_delivery/agent-workflows/locks").mkdir(parents=True)
    monkeypatch.setattr(
        collector.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=128, stdout="", stderr="git unavailable"),
    )

    evidence = collector._collect_workspace_hygiene_observation(
        code_root=code_root,
        runtime_root=state_root,
    )

    assert evidence["status"] == "UNKNOWN"
    assert evidence["value"] is None
    assert evidence["source_digest"] is None
    assert evidence["observed_at"] is None
    assert evidence["error_class"] == "workspace_worktree_read_failed"


def test_default_workspace_observation_uses_authority_roots_not_publisher_root(tmp_path, monkeypatch):
    collector = _collector()
    canonical = tmp_path / "canonical"
    publisher = tmp_path / "publisher"
    state = tmp_path / "state"
    canonical.mkdir()
    publisher.mkdir()
    lock_root = state / ".omo/_delivery/agent-workflows/locks"
    lock_root.mkdir(parents=True)
    monkeypatch.setattr(collector, "ROOT", publisher)
    monkeypatch.setattr(collector, "canonical_root", lambda: canonical)
    monkeypatch.setattr(collector, "state_root", lambda: state)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    called = {}

    def list_worktrees(command, **kwargs):
        called["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=f"worktree {canonical}\nHEAD abc\nbranch refs/heads/main\n\n",
        )

    monkeypatch.setattr(collector.subprocess, "run", list_worktrees)

    evidence = collector._collect_workspace_hygiene_observation()

    assert evidence["status"] == "OBSERVED"
    assert called["command"][2] == str(canonical)
    assert evidence["provenance"]["scope"] == {"code_root": str(canonical), "state_root": str(state)}
