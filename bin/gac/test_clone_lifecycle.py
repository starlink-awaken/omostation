#!/usr/bin/env python3
"""clone-lifecycle.py 集成测试 — 自动化 clone 生命周期管道."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

lc = importlib.import_module("clone-lifecycle")

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(_GIT_ENV)
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return proc


def make_retirable_clone(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare", "-b", "main")
    clone = tmp_path / "agent-1" / "ws"
    clone.mkdir(parents=True)
    git(clone, "init", "-b", "main")
    (clone / ".gitignore").write_text(".omo/_delivery/\n")
    (clone / "README.md").write_text("root\n")
    git(clone, "add", ".gitignore", "README.md")
    git(clone, "commit", "-m", "initial")
    git(clone, "switch", "-c", "agent/agent-1")
    git(clone, "remote", "add", "origin", str(remote))
    git(clone, "push", "-u", "origin", "agent/agent-1")
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    identity = {
        "schema": "agent-clone-identity/v1",
        "agent_id": "agent-1",
        "canonical_root": str(clone.resolve()),
        "source_url": str(remote.resolve()),
        "frozen_root_sha": head,
        "working_branch": "agent/agent-1",
        "ready": True,
    }
    (clone / ".git" / "agent-clone-identity.json").write_text(json.dumps(identity))
    return clone, remote, head


def merged_pr_runner(head: str):
    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if cmd[:3] == ["gh", "pr", "list"]:
            payload = [{"number": 7, "url": "https://example.test/pr/7", "headRefOid": head}]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    return _run


def test_onboard_initializes_only_requested_submodules_and_verifies(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_onboard(
        argparse.Namespace(
            agent_id="agent-1",
            source="source",
            destination=str(tmp_path / "agent-1" / "ws"),
            manifest=str(tmp_path / "baseline.json"),
            submodule=["projects/omo"],
            all_submodules=False,
        )
    )

    assert rc == 0
    assert "--no-submodules" not in calls[0]
    assert calls[0][-2:] == ["--submodule", "projects/omo"]
    assert calls[2][2] == "verify"
    assert (tmp_path / "agent-1").is_dir()


def test_snapshot_creates_valid_manifest(tmp_path, monkeypatch):
    """snapshot 生成有效 manifest."""
    import subprocess

    # Use existing pilot clone as input
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return  # skip if no pilot
    output = tmp_path / "baseline.json"
    rc = lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(output)))
    assert rc == 0
    d = json.loads(output.read_text())
    assert "root_head_sha" in d
    assert "repositories" in d


def test_changeset_no_change(tmp_path):
    """无变更时 changeset 正确检测."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    baseline = tmp_path / "base.json"
    # Generate baseline first
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(baseline)))
    output = tmp_path / "cs.json"
    rc = lc.cmd_changeset(
        argparse.Namespace(
            clone=str(pilot),
            baseline=str(baseline),
            output=str(output),
            verify_claims=True,
        )
    )
    assert rc == 0
    cs = json.loads(output.read_text())
    assert cs["no_change"] is True
    assert cs["claim_verification"]["all_covered"] is True


def test_changeset_with_verify_claims(tmp_path):
    """claim 校验开启时输出包含 claim_verification."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    baseline = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(baseline)))
    output = tmp_path / "cs.json"
    rc = lc.cmd_changeset(
        argparse.Namespace(
            clone=str(pilot),
            baseline=str(baseline),
            output=str(output),
            verify_claims=True,
        )
    )
    assert rc == 0
    cs = json.loads(output.read_text())
    assert "claim_verification" in cs
    assert cs["claim_verification"]["enabled"] is True


def test_changeset_claim_violation_is_nonzero_even_if_receipt_exists(tmp_path, monkeypatch):
    output = tmp_path / "cs.json"
    output.write_text(
        json.dumps(
            {
                "change_id": "abc",
                "changes": [{"path": "README.md"}],
                "claim_verification": {"violations": ["README.md"], "all_covered": False},
            }
        )
    )
    monkeypatch.setattr(
        lc,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "{}", ""),
    )

    rc = lc.cmd_changeset(
        argparse.Namespace(
            clone=str(tmp_path / "clone"),
            baseline=str(tmp_path / "baseline.json"),
            output=str(output),
            verify_claims=True,
        )
    )

    assert rc == lc.EXIT_POLICY


def test_integrate_dry_run(tmp_path, capsys):
    """integrate dry-run 不实际推送."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(pilot),
            agent_id="pilot",
            dry_run=True,
        )
    )
    assert rc == 0
    out = capsys.readouterr()
    assert "dry_run" in out.out


def test_integrate_apply_is_reachable_and_creates_pr(tmp_path, monkeypatch, capsys):
    clone, _remote, head = make_retirable_clone(tmp_path)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, "https://example.test/pr/8\n", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(argparse.Namespace(clone=str(clone), agent_id="agent-1", dry_run=False, base="main"))

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["head_sha"] == head
    assert result["pr_url"] == "https://example.test/pr/8"
    assert any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)


def test_integrate_apply_rejects_repository_without_clone_identity(tmp_path, monkeypatch):
    clone, _remote, _head = make_retirable_clone(tmp_path)
    (clone / ".git" / "agent-clone-identity.json").unlink()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                json.dumps([{"url": "https://example.test/pr/9"}]),
                "",
            )
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)

    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
        )
    )

    assert rc == lc.EXIT_POLICY
    assert not any("push" in cmd for cmd in calls)


def test_integrate_parser_defaults_dry_run_and_exposes_apply():
    parser = lc.build_parser()
    dry = parser.parse_args(["integrate", "--clone", "/tmp/c", "--agent-id", "agent-1"])
    apply = parser.parse_args(["integrate", "--clone", "/tmp/c", "--agent-id", "agent-1", "--apply"])

    assert dry.dry_run is True
    assert apply.dry_run is False


def test_retire_removes_only_clean_pushed_merged_unleased_clone(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))
    assert rc == 0
    assert not clone.exists()


def test_retire_rejects_dirty_or_unpushed_clone(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    (clone / "dirty.txt").write_text("dirty\n")
    assert lc.cmd_retire(argparse.Namespace(destination=str(clone))) == lc.EXIT_POLICY
    assert clone.exists()
    (clone / "dirty.txt").unlink()
    (clone / "README.md").write_text("unpushed\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "unpushed")
    assert lc.cmd_retire(argparse.Namespace(destination=str(clone))) == lc.EXIT_POLICY
    assert clone.exists()


def test_retire_rejects_unmerged_pr_or_active_lock(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)

    def no_pr_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", no_pr_runner)
    assert lc.cmd_retire(argparse.Namespace(destination=str(clone))) == lc.EXIT_POLICY
    locks = clone / ".omo" / "_delivery" / "agent-workflows" / "locks"
    locks.mkdir(parents=True)
    (locks / "active.lock.yaml").write_text("status: active\n")
    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    assert lc.cmd_retire(argparse.Namespace(destination=str(clone))) == lc.EXIT_POLICY
    assert clone.exists()


def test_retire_rechecks_clone_after_remote_and_pr_checks(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)

    def racing_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if cmd[:3] == ["gh", "pr", "list"]:
            (clone / "late-write.txt").write_text("raced\n")
            payload = [{"number": 7, "url": "https://example.test/pr/7", "headRefOid": head}]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", racing_runner)

    assert lc.cmd_retire(argparse.Namespace(destination=str(clone))) == lc.EXIT_POLICY
    assert clone.exists()


def test_retire_rejects_symlink_and_linked_worktree(tmp_path):
    clone, _remote, _head = make_retirable_clone(tmp_path)
    link = tmp_path / "linked-ws"
    link.symlink_to(clone, target_is_directory=True)
    assert lc.cmd_retire(argparse.Namespace(destination=str(link))) == lc.EXIT_POLICY
    assert clone.exists()

    linked = tmp_path / "linked-agent" / "ws"
    linked.parent.mkdir()
    git(clone, "worktree", "add", "-b", "agent/linked", str(linked))
    assert (linked / ".git").is_file()
    assert lc.cmd_retire(argparse.Namespace(destination=str(linked))) == lc.EXIT_POLICY
    assert linked.exists()


def test_audit_logging(capsys, tmp_path):
    """审计日志输出到 stderr."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    output = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(output)))
    err = capsys.readouterr().err
    assert "LIFECYCLE=snapshot_ok" in err


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
