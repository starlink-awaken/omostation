#!/usr/bin/env python3
"""clone-lifecycle.py 集成测试 — 自动化 clone 生命周期管道."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

lc = importlib.import_module("clone-lifecycle")
REAL_AGENT_CLONE = lc.AGENT_CLONE

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


@pytest.fixture(autouse=True)
def _restore_agent_clone(monkeypatch):
    monkeypatch.setattr(lc, "AGENT_CLONE", REAL_AGENT_CLONE)


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
    policy = clone / ".omo" / "_truth" / "registry" / "swarm-coordination.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        "topology_migration:\n"
        f"  integration_root: '{(tmp_path / 'authority').resolve()}'\n"
    )
    git(clone, "add", ".gitignore", "README.md", str(policy.relative_to(clone)))
    git(clone, "commit", "-m", "initial")
    git(clone, "switch", "-c", "agent/agent-1")
    git(clone, "remote", "add", "origin", str(remote))
    git(clone, "push", "origin", "HEAD:refs/heads/main")
    git(clone, "push", "-u", "origin", "agent/agent-1")
    authority = tmp_path / "authority"
    cloned = subprocess.run(
        ["git", "clone", str(remote), str(authority)],
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr
    wrapper = tmp_path / "agent-clone-test-wrapper.py"
    wrapper.write_text(
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        f"tool = Path({str(REAL_AGENT_CLONE)!r})\n"
        "spec = importlib.util.spec_from_file_location('agent_clone_test_cli', tool)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "assert spec and spec.loader\n"
        "spec.loader.exec_module(module)\n"
        f"module.ACCOUNT_WORKSPACE_ROOT = Path({str(authority)!r})\n"
        "raise SystemExit(module.main(sys.argv[1:]))\n"
    )
    lc.AGENT_CLONE = wrapper
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


def make_verified_changeset(tmp_path: Path, clone: Path) -> tuple[Path, Path, Path, str]:
    baseline = tmp_path / "baseline.json"
    manifest = subprocess.run(
        [
            sys.executable,
            str(lc.AGENT_CLONE),
            "manifest",
            "--clone",
            str(clone),
            "--output",
            str(baseline),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert manifest.returncode == 0, manifest.stderr
    authority = tmp_path / "authority"
    runs = authority / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True)
    (runs / "active.yaml").write_text(
        "run_id: active\nstatus: active\nactor: human-owner\n"
        "updated_at: '2026-08-21T00:00:00Z'\nclaims:\n"
        "  - actor: agent-1\n    claimed_at: '2026-08-21T00:00:01Z'\n"
        "    paths:\n      - README.md\n"
    )
    (clone / "README.md").write_text("integrate\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "integrate")
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    changeset = tmp_path / "changeset.json"
    generated = subprocess.run(
        [
            sys.executable,
            str(lc.AGENT_CLONE),
            "changeset",
            "--clone",
            str(clone),
            "--baseline",
            str(baseline),
            "--output",
            str(changeset),
            "--verify-claims",
            "--claims-root",
            str(authority),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    return baseline, changeset, authority, head


def merged_pr_runner(head: str, calls: list[list[str]] | None = None):
    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if calls is not None:
            calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "git@github.com:owner/repository.git\n",
                "",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            payload = [
                {
                    "number": 7,
                    "url": "https://example.test/pr/7",
                    "headRefOid": head,
                    "headRefName": "agent/agent-1",
                    "headRepositoryOwner": {"login": "owner"},
                }
            ]
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
            revision="origin/main",
            destination=str(tmp_path / "agent-1" / "ws"),
            manifest=str(tmp_path / "baseline.json"),
            submodule=["projects/omo"],
            all_submodules=False,
        )
    )

    assert rc == 0
    assert calls[0][calls[0].index("--revision") + 1] == "origin/main"
    assert "--no-submodules" not in calls[0]
    assert calls[0][-2:] == ["--submodule", "projects/omo"]
    assert calls[2][2] == "verify"
    assert (tmp_path / "agent-1").is_dir()


def test_onboard_parser_defaults_to_canonical_main_and_allows_override():
    parser = lc.build_parser()

    default = parser.parse_args(
        ["onboard", "--agent-id", "agent-1", "--destination", "/tmp/agent-1/ws"]
    )
    pinned = parser.parse_args(
        [
            "onboard",
            "--agent-id",
            "agent-1",
            "--destination",
            "/tmp/agent-1/ws",
            "--revision",
            "refs/tags/baseline-v1",
        ]
    )

    assert default.revision == "origin/main"
    assert pinned.revision == "refs/tags/baseline-v1"


def test_snapshot_creates_valid_manifest(tmp_path):
    """snapshot 生成有效 manifest."""
    clone, _remote, _head = make_retirable_clone(tmp_path)
    output = tmp_path / "baseline.json"
    rc = lc.cmd_snapshot(argparse.Namespace(clone=str(clone), output=str(output)))
    assert rc == 0
    d = json.loads(output.read_text())
    assert "root_head_sha" in d
    assert "repositories" in d


def test_changeset_no_change(tmp_path, monkeypatch):
    """无变更时 changeset 正确检测."""
    clone, _remote, _head = make_retirable_clone(tmp_path)
    baseline = tmp_path / "base.json"
    # Generate baseline first
    lc.cmd_snapshot(argparse.Namespace(clone=str(clone), output=str(baseline)))
    output = tmp_path / "cs.json"
    authority = tmp_path / "authority"
    (authority / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    rc = lc.cmd_changeset(
        argparse.Namespace(
            clone=str(clone),
            baseline=str(baseline),
            output=str(output),
            verify_claims=True,
            claims_root=str(authority),
        )
    )
    assert rc == 0
    cs = json.loads(output.read_text())
    assert cs["no_change"] is True
    assert cs["claim_verification"]["all_covered"] is True


def test_changeset_with_verify_claims(tmp_path, monkeypatch):
    """claim 校验开启时输出包含 claim_verification."""
    clone, _remote, _head = make_retirable_clone(tmp_path)
    baseline = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(clone), output=str(baseline)))
    output = tmp_path / "cs.json"
    authority = tmp_path / "authority"
    (authority / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    rc = lc.cmd_changeset(
        argparse.Namespace(
            clone=str(clone),
            baseline=str(baseline),
            output=str(output),
            verify_claims=True,
            claims_root=str(authority),
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
            claims_root=str(tmp_path / "authority"),
        )
    )

    assert rc == lc.EXIT_POLICY


def test_changeset_missing_or_disabled_claim_verification_is_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lc,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "{}", ""),
    )
    for name, claim_verification in (
        ("missing", None),
        ("disabled", {"enabled": False, "all_covered": True, "violations": []}),
    ):
        output = tmp_path / f"{name}.json"
        payload = {"change_id": "abc", "changes": [{"path": "README.md"}]}
        if claim_verification is not None:
            payload["claim_verification"] = claim_verification
        output.write_text(json.dumps(payload))

        rc = lc.cmd_changeset(
            argparse.Namespace(
                clone=str(tmp_path / "clone"),
                baseline=str(tmp_path / "baseline.json"),
                output=str(output),
                verify_claims=True,
                claims_root=str(tmp_path / "authority"),
            )
        )

        assert rc == lc.EXIT_POLICY


def test_changeset_audit_reports_persisted_change_count(tmp_path, monkeypatch, capsys):
    output = tmp_path / "cs.json"
    output.write_text(
        json.dumps(
            {
                "change_id": "abc",
                "changes": [{"path": "README.md"}],
                "claim_verification": {
                    "enabled": True,
                    "violations": [],
                    "all_covered": True,
                },
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
            claims_root=str(tmp_path / "authority"),
        )
    )

    assert rc == lc.EXIT_OK
    assert "changes=1" in capsys.readouterr().err


def test_integrate_dry_run(tmp_path, capsys):
    """integrate dry-run 不实际推送."""
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(tmp_path / "not-created"),
            agent_id="pilot",
            dry_run=True,
        )
    )
    assert rc == 0
    out = capsys.readouterr()
    assert "dry_run" in out.out


def test_integrate_apply_is_reachable_and_creates_pr(tmp_path, monkeypatch, capsys):
    clone, _remote, _initial_head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, head = make_verified_changeset(tmp_path, clone)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "git@github.com:owner/repository.git\n",
                "",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, "https://example.test/pr/8\n", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["head_sha"] == head
    assert result["pr_url"] == "https://example.test/pr/8"
    assert any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)
    assert all("owner/repository" in cmd for cmd in calls if cmd[:3] in (["gh", "pr", "list"], ["gh", "pr", "create"]))
    assert any("agent/agent-1" in cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])


def test_integrate_reuses_only_exact_owner_branch_and_head_pr(tmp_path, monkeypatch, capsys):
    clone, _remote, _initial_head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, head = make_verified_changeset(tmp_path, clone)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(cmd, 0, "git@github.com:owner/repository.git\n", "")
        if cmd[:3] == ["gh", "pr", "list"]:
            payload = [
                {
                    "url": "https://example.test/pr/8",
                    "headRefName": "agent/agent-1",
                    "headRefOid": head,
                    "headRepositoryOwner": {"login": "owner"},
                }
            ]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        if cmd[:3] == ["gh", "pr", "create"]:
            raise AssertionError("exact existing PR must be reused")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == lc.EXIT_OK
    assert json.loads(capsys.readouterr().out)["pr_url"] == "https://example.test/pr/8"
    pr_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    assert pr_call[pr_call.index("--head") + 1] == "agent/agent-1"


def test_integrate_apply_requires_claims_root_before_push(tmp_path, monkeypatch):
    clone, _remote, _head = make_retirable_clone(tmp_path)
    baseline, changeset, _authority, _verified_head = make_verified_changeset(tmp_path, clone)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, "https://example.test/pr/8\n", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=None,
        )
    )

    assert rc == lc.EXIT_POLICY
    assert not any("push" in cmd for cmd in calls)
    assert not any(cmd[:2] == ["gh", "pr"] for cmd in calls)


def test_integrate_apply_rejects_stale_or_unclaimed_receipt_before_push(tmp_path, monkeypatch):
    clone, _remote, _head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, _verified_head = make_verified_changeset(tmp_path, clone)
    (clone / "README.md").write_text("new head\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "new head")
    calls: list[list[str]] = []

    def recording_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", recording_run)
    stale_rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )
    assert stale_rc == lc.EXIT_POLICY
    assert not any("push" in cmd for cmd in calls)

    receipt = json.loads(changeset.read_text())
    receipt["root_candidate_sha"] = git(clone, "rev-parse", "HEAD").stdout.strip()
    receipt["claim_verification"]["all_covered"] = False
    receipt["claim_verification"]["violations"] = ["README.md"]
    receipt["change_id"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in receipt.items() if key != "change_id"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    unclaimed = tmp_path / "unclaimed.json"
    unclaimed.write_text(json.dumps(receipt))
    calls.clear()
    unclaimed_rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(unclaimed),
            claims_root=str(authority),
        )
    )
    assert unclaimed_rc == lc.EXIT_POLICY
    assert not any("push" in cmd for cmd in calls)


def test_integrate_rechecks_claims_immediately_before_push(tmp_path, monkeypatch):
    clone, _remote, _head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, _verified_head = make_verified_changeset(tmp_path, clone)
    run_file = authority / ".omo" / "_delivery" / "agent-workflows" / "runs" / "active.yaml"
    calls: list[list[str]] = []
    verify_count = 0

    def racing_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal verify_count
        calls.append(cmd)
        if "verify-changeset" in cmd:
            verify_count += 1
            if verify_count == 2:
                run_file.write_text(
                    run_file.read_text().replace(
                        "2026-08-21T00:00:00Z", "2026-08-21T00:00:02Z"
                    )
                )
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(cmd, 0, "git@github.com:owner/repository.git\n", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", racing_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == lc.EXIT_POLICY
    assert verify_count == 2
    assert not any("push" in cmd for cmd in calls)
    assert not any(cmd[:2] == ["gh", "pr"] for cmd in calls)


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
            baseline=str(tmp_path / "baseline.json"),
            changeset=str(tmp_path / "changeset.json"),
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
    calls: list[list[str]] = []
    monkeypatch.setattr(lc, "run", merged_pr_runner(head, calls))
    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))
    assert rc == 0
    assert not clone.exists()
    assert not list(clone.parent.glob(".ws.retire-quarantine-*"))
    pr_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    assert ["--repo", "owner/repository"] == pr_call[pr_call.index("--repo") : pr_call.index("--repo") + 2]
    assert "agent/agent-1" in pr_call


def test_retire_allows_exact_merged_pr_after_remote_branch_deleted(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    git(clone, "push", "origin", "--delete", "agent/agent-1")
    calls: list[list[str]] = []
    monkeypatch.setattr(lc, "run", merged_pr_runner(head, calls))

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_OK
    assert not clone.exists()
    assert any(cmd[:3] == ["gh", "pr", "list"] for cmd in calls)


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


def test_retire_does_not_delegate_verified_payload_to_path_rmtree(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    original = clone.parent / "original-payload"
    victim_source = clone.parent / "victim-source"
    victim_source.mkdir()
    sentinel = victim_source / "must-survive.txt"
    sentinel.write_text("keep\n")
    real_rmtree = lc.shutil.rmtree
    injected = False

    def racing_rmtree(path, *args, **kwargs):
        nonlocal injected
        target = Path(path)
        if target.name == "payload" and ".ws.retire-quarantine-" in target.parent.name and not injected:
            injected = True
            target.rename(original)
            victim_source.rename(target)
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc.shutil, "rmtree", racing_rmtree)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert injected is False
    assert rc == lc.EXIT_OK
    assert sentinel.read_text() == "keep\n"
    assert not original.exists()


def test_retire_fd_binding_detects_payload_swap_after_open(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    expected_stat = clone.lstat()
    original = clone.parent / "opened-original-payload"
    victim_source = clone.parent / "victim-source"
    victim_source.mkdir()
    sentinel = victim_source / "must-survive.txt"
    sentinel.write_text("keep\n")
    real_scandir = lc.os.scandir
    injected = False
    victim_location: Path | None = None

    def racing_scandir(path):
        nonlocal injected, victim_location
        if isinstance(path, int) and os.path.samestat(expected_stat, os.fstat(path)) and not injected:
            injected = True
            payload = next(clone.parent.glob(".ws.retire-quarantine-*/payload"))
            payload.rename(original)
            victim_source.rename(payload)
            victim_location = payload / sentinel.name
        return real_scandir(path)

    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc.os, "scandir", racing_scandir)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert injected is True
    assert rc == lc.EXIT_POLICY
    assert victim_location is not None
    assert victim_location.read_text() == "keep\n"
    assert original.exists()


def test_retire_fails_closed_without_fd_bound_delete_support(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc, "FD_BOUND_DELETE_SUPPORTED", False)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert not list(clone.parent.glob(".ws.retire-quarantine-*"))


def test_retire_never_follows_nested_file_replacement_symlink(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    external_victim = tmp_path / "external-victim.txt"
    external_victim.write_text("keep\n")
    real_unlink = lc.os.unlink
    injected = False

    def racing_unlink(path, *args, **kwargs):
        nonlocal injected
        directory_fd = kwargs.get("dir_fd")
        if path == "README.md" and directory_fd is not None and not injected:
            injected = True
            os.rename(path, "README.retired", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.symlink(external_victim, path, dir_fd=directory_fd)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc.os, "unlink", racing_unlink)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert injected is True
    assert rc == lc.EXIT_POLICY
    assert external_victim.read_text() == "keep\n"
    assert list(clone.parent.glob(".ws.retire-quarantine-*"))


def test_retire_detects_identity_swap_at_quarantine_boundary(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    original = clone.parent / "original-ws"
    victim_source = clone.parent / "victim-source"
    victim_source.mkdir()
    (victim_source / "must-survive.txt").write_text("keep\n")
    real_rename = lc.os.rename
    injected = False

    def racing_rename(source, destination, *args, **kwargs):
        nonlocal injected
        if Path(source) == clone and not injected:
            injected = True
            real_rename(clone, original)
            real_rename(victim_source, clone)
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc.os, "rename", racing_rename)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_POLICY
    assert (clone / "must-survive.txt").read_text() == "keep\n"
    assert original.exists()


def test_retire_restores_clone_if_it_becomes_dirty_inside_quarantine(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    real_rename = lc.os.rename
    injected = False

    def late_write_after_rename(source, destination, *args, **kwargs):
        nonlocal injected
        result = real_rename(source, destination, *args, **kwargs)
        if Path(source) == clone and not injected:
            injected = True
            (Path(destination) / "late-write.txt").write_text("preserve\n")
        return result

    monkeypatch.setattr(lc, "run", merged_pr_runner(head))
    monkeypatch.setattr(lc.os, "rename", late_write_after_rename)

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_POLICY
    assert (clone / "late-write.txt").read_text() == "preserve\n"
    assert not list(clone.parent.glob(".ws.retire-quarantine-*"))


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
    clone, _remote, _head = make_retirable_clone(tmp_path)
    output = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(clone), output=str(output)))
    err = capsys.readouterr().err
    assert "LIFECYCLE=snapshot_ok" in err


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
