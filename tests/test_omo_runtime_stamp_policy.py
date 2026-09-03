"""Regression tests for immutable runtime final-tree policy checks."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "omo-runtime-stamp-policy.py"


def _load():
    spec = importlib.util.spec_from_file_location("runtime_stamp_policy_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True)
    return run.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "runtime-policy@example.invalid")
    _git(repo, "config", "user.name", "Runtime Policy Test")
    return repo


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def test_treeish_rejects_tracked_smoke_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/consumer-audit-smoke.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "tracked output")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    report = mod.evaluate_treeish(head)
    assert report["ok"] is False
    assert report["forbidden_tracked_paths"] == ["runtime/consumer-audit-smoke.json"]


def test_treeish_ignore_rules_do_not_allow_tracked_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("runtime/*.json\n", encoding="utf-8")
    path = repo / "runtime/output.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-f", "runtime/output.json")
    head = _commit(repo, "tracked output")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(head)["forbidden_tracked_paths"] == ["runtime/output.json"]


@pytest.mark.parametrize(
    "relative",
    [
        "runtime/AGENTS.md",
        "runtime/README.md",
        "runtime/runtime-space-boundary.yaml",
        "runtime/system-runtime-boundary.yaml",
        "runtime/cron/systemd/example.service",
        "runtime/ssot-stable/tool.py",
        "runtime/sandbox/tasks/example.yaml",
        "runtime/coordination/handoffs/test-run-001.json",
    ],
)
def test_treeish_allows_explicit_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    repo = _repo(tmp_path)
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("contract\n", encoding="utf-8")
    head = _commit(repo, "contract")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(head)["forbidden_tracked_paths"] == []


def test_treeish_allows_projection_registered_in_requested_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    projection = repo / "runtime/custom-projection.json"
    projection.parent.mkdir(parents=True)
    projection.write_text("{}\n", encoding="utf-8")
    registry = repo / ".omo/_truth/registry/runtime-projections.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "projections:\n"
        "  custom:\n"
        "    canonical: runtime/custom-projection.json\n"
        "    legacy: runtime/legacy-projection.json\n",
        encoding="utf-8",
    )
    head = _commit(repo, "registered projection")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)

    report = mod.evaluate_treeish(head)

    assert report["forbidden_tracked_paths"] == []


def test_treeish_uses_requested_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/transient.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    old = _commit(repo, "add")
    path.unlink()
    new = _commit(repo, "delete")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(old)["forbidden_tracked_paths"] == ["runtime/transient.json"]
    assert mod.evaluate_treeish(new)["forbidden_tracked_paths"] == []


def test_treeish_rejects_symlink_and_gitlink_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    runtime = repo / "runtime"
    runtime.mkdir()
    (runtime / "target").write_text("x", encoding="utf-8")
    (runtime / "link").symlink_to("target")
    head = _commit(repo, "symlink")
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},runtime/gitlink")
    _git(repo, "commit", "-qm", "gitlink")
    current = _git(repo, "rev-parse", "HEAD")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    report = mod.evaluate_treeish(current)
    assert report["invalid_modes"] == ["runtime/gitlink", "runtime/link"]
    assert report["ok"] is False


def test_treeish_json_paths_are_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    for name in ("z.json", "a.json"):
        path = repo / "runtime" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "outputs")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    assert mod.evaluate_treeish(head)["forbidden_tracked_paths"] == ["runtime/a.json", "runtime/z.json"]


def test_treeish_invalid_revision_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    with pytest.raises(ValueError, match="treeish"):
        mod.evaluate_treeish("does-not-exist")


def test_treeish_unreadable_revision_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/output.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "tracked output")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    real_run = mod.subprocess.run

    def fail_ls_tree(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = args[0]
        if isinstance(command, list) and command[:2] == ["git", "ls-tree"]:
            return subprocess.CompletedProcess(command, 128, b"", b"unreadable tree")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fail_ls_tree)
    with pytest.raises(ValueError, match="cannot be listed"):
        mod.evaluate_treeish(head)


def test_treeish_does_not_inspect_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/output.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "tracked output")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)

    class WorktreeAccessTrap:
        def exists(self) -> bool:
            raise AssertionError("treeish mode must not inspect the worktree")

        def rglob(self, _pattern: str) -> object:
            raise AssertionError("treeish mode must not inspect the worktree")

        def stat(self) -> object:
            raise AssertionError("treeish mode must not inspect the worktree")

        def read_text(self, **_kwargs: object) -> str:
            raise AssertionError("treeish mode must not inspect the worktree")

    trap = WorktreeAccessTrap()
    monkeypatch.setattr(mod, "RUNTIME_DIR", trap)
    monkeypatch.setattr(mod, "GITIGNORE", trap)
    monkeypatch.setattr(mod, "REGISTRY", trap)
    real_run = mod.subprocess.run

    def fail_ls_files(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        if isinstance(command, list) and command[:2] == ["git", "ls-files"]:
            raise AssertionError("treeish mode must not inspect tracked worktree files")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fail_ls_files)
    report = mod.evaluate_treeish(head)
    assert report["forbidden_tracked_paths"] == ["runtime/output.json"]


def test_treeish_does_not_require_worktree_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    path = repo / "runtime/output.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    head = _commit(repo, "tracked output")
    shutil.rmtree(repo / "runtime")
    mod = _load()
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(mod, "RUNTIME_DIR", repo / "runtime")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--treeish", head, "--json"])

    assert mod.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["forbidden_tracked_paths"] == ["runtime/output.json"]


def test_workpacket_runtime_patterns_have_no_tracked_outputs() -> None:
    ledger = yaml.safe_load((ROOT / "docs/plans/3y-bet-ledger.yaml").read_text(encoding="utf-8"))
    bet = next(item for item in ledger["bets"] if item["id"] == "BET-Y1Q3-T6-15")
    patterns = [path for path in bet["write_surfaces"] if path.startswith("runtime/")]
    paths = sorted(
        {
            path
            for pattern in patterns
            for path in subprocess.run(
                ["git", "ls-files", "--", pattern],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.splitlines()
            if path
        }
    )
    assert paths == []


def test_workpacket_runtime_families_are_ignored() -> None:
    ledger = yaml.safe_load((ROOT / "docs/plans/3y-bet-ledger.yaml").read_text(encoding="utf-8"))
    bet = next(item for item in ledger["bets"] if item["id"] == "BET-Y1Q3-T6-15")
    patterns = {path for path in bet["write_surfaces"] if path.startswith("runtime/")}
    witnesses = {
        "runtime/bos-neural-mesh-*": "runtime/bos-neural-mesh-future.json",
        "runtime/concept-weave-preflight*.json": "runtime/concept-weave-preflight-future.json",
        "runtime/consumer-audit-*.json": "runtime/consumer-audit-future.json",
        "runtime/control/evidence/documents-weijian-*/documents-weijian-*.json": (
            "runtime/control/evidence/documents-weijian-future/documents-weijian-future.json"
        ),
        "runtime/daily-health-preflight*.json": "runtime/daily-health-preflight-future.json",
        "runtime/heartbeats/weijian-*": "runtime/heartbeats/weijian-future",
        "runtime/kos-preflight-*.json": "runtime/kos-preflight-future.json",
        "runtime/predictor-preflight*.json": "runtime/predictor-preflight-future.json",
        "runtime/quarantine/documents-bos-neural-mesh-20260828/*": (
            "runtime/quarantine/documents-bos-neural-mesh-20260828/future.json"
        ),
        "runtime/task-inventory/snapshots/2026082[78]-*.json": (
            "runtime/task-inventory/snapshots/20260827-future.json"
        ),
    }
    assert patterns == set(witnesses)

    not_ignored = [
        witness
        for witness in witnesses.values()
        if subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", "--", witness],
            cwd=ROOT,
            check=False,
        ).returncode
        != 0
    ]
    assert not_ignored == []


def test_invalid_treeish_cli_fails_closed() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--treeish", "does-not-exist", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "treeish" in (result.stderr + result.stdout).lower()
