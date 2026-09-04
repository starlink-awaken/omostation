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

_BIN_GAC = Path(__file__).resolve().parents[1] / "bin" / "gac"
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

lc = importlib.import_module("clone-lifecycle")
ac = importlib.import_module("agent-clone")
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
    import shutil
    if remote.exists():
        shutil.rmtree(remote)
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
    identity_path = clone / ".git" / "agent-clone-identity.json"
    if json.loads(identity_path.read_text()).get("schema") == "agent-clone-identity/v1":
        qualify_clone_attempt(clone)
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


def qualify_clone_attempt(clone: Path, attempt_id: str = "attempt-001") -> str:
    """Upgrade a fixture clone to the new actor/attempt identity contract."""
    branch = f"agent/agent-1--{attempt_id}"
    git(clone, "branch", "-m", branch)
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity.update(
        {
            "schema": "agent-clone-identity/v2",
            "actor_id": "agent-1",
            "delivery_attempt_id": attempt_id,
            "working_branch": branch,
        }
    )
    identity_path.write_text(json.dumps(identity))
    return branch


def merged_pr_runner(
    head: str,
    calls: list[list[str]] | None = None,
    *,
    branch: str = "agent/agent-1",
    provenance_guard_ok: bool = False,
    platform_head: str | None = None,
    platform_base: str | None = None,
    platform_pr: int = 7,
    platform_repo: str = "owner/repository",
    platform_owner: str = "owner",
    platform_state: str = "MERGED",
    platform_base_name: str = "main",
):
    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if calls is not None:
            calls.append(cmd)
        if (
            provenance_guard_ok
            and len(cmd) >= 3
            and cmd[0] == sys.executable
            and cmd[1] == str(lc.AGENT_CLONE)
            and cmd[2] in {"guard", "retirement-provenance"}
        ):
            return subprocess.CompletedProcess(cmd, 0, '{"ok":true}\n', "")
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:5] == ["remote", "get-url"] and cmd[-1] == "origin":
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
                    "headRefName": branch,
                    "headRepositoryOwner": {"login": "owner"},
                }
            ]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        if cmd[:3] == ["gh", "pr", "view"]:
            payload = {
                "base_ref_name": platform_base_name,
                "base_ref_oid": platform_base,
                "branch": branch,
                "head_ref_oid": platform_head,
                "number": platform_pr,
                "owner": platform_owner,
                "repository": platform_repo,
                "state": platform_state,
                "url": f"https://example.test/pr/{platform_pr}",
                "merge_commit_oid": "a" * 40,
            }
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    return _run


def bind_fixture_provenance(clone: Path, attempt_id: str = "platform-fixture") -> str:
    """Bind a legacy fixture to the minimum valid v2 provenance contract."""
    branch = qualify_clone_attempt(clone, attempt_id)
    git(clone, "config", "--local", "user.name", "test")
    git(clone, "config", "--local", "user.email", "t@example.com")
    git(clone, "config", "--local", "user.useConfigOnly", "true")
    author = {
        "email_digest": hashlib.sha256(b"t@example.com").hexdigest(),
        "identity_digest": ac.author_identity_digest("test", "t@example.com"),
        "name_digest": hashlib.sha256(b"test").hexdigest(),
        "source": "clone-local",
        "use_config_only": True,
    }
    repository = {
        "canonical_repository": "github.com/owner/repository",
        "fetch_transport": "https",
        "fetch_url_digest": "1" * 64,
        "push_transport": "https",
        "push_url_digest": "1" * 64,
    }
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    receipt = {
        "schema": "clone-provenance/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": attempt_id,
        "clone_root": str(clone.resolve()),
        "repository": repository,
        "author": author,
        "frozen_root_sha": identity["frozen_root_sha"],
        "working_branch": branch,
        "status": "ready",
        "generated_at": None,
    }
    receipt["receipt_digest"] = ac.canonical_digest(
        receipt, exclude_field="receipt_digest"
    )
    (clone / ".git" / "agent-clone-provenance.json").write_text(
        json.dumps(receipt)
    )
    identity.update(
        {
            "provenance_required": True,
            "provenance_status": "ready",
            "provenance_receipt_digest": receipt["receipt_digest"],
        }
    )
    identity_path.write_text(json.dumps(identity))
    return branch


def make_platform_rebased_clone(
    tmp_path: Path, *, provenance: bool = False
) -> tuple[Path, str, str, str, str]:
    """Build local-original and platform-rebased commits with identical delivery changes."""
    clone, _remote, initial = make_retirable_clone(tmp_path)
    branch = git(clone, "branch", "--show-current").stdout.strip()
    (clone / "README.md").write_text("delivered\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "delivery")
    original = git(clone, "rev-parse", "HEAD").stdout.strip()

    git(clone, "switch", "-c", "platform-base", initial)
    (clone / "BASE.md").write_text("new base\n")
    git(clone, "add", "BASE.md")
    git(clone, "commit", "-m", "platform base")
    platform_base = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "switch", "-c", "platform-head")
    git(clone, "cherry-pick", original)
    platform_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "push", "--force", "origin", f"{platform_head}:refs/heads/{branch}")
    git(clone, "switch", branch)
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == original
    if provenance:
        bind_fixture_provenance(clone)
    return clone, original, platform_head, platform_base, initial


def make_advanced_platform_provenance_clone(
    tmp_path: Path,
    *,
    delivery_identity: tuple[str, str] = ("test", "t@example.com"),
) -> tuple[Path, str, str, str]:
    """Build a provenance-bound clone whose platform base imports another author."""
    clone, _remote, frozen = make_retirable_clone(tmp_path)
    branch = qualify_clone_attempt(clone, "platform-attempt")
    git(clone, "config", "--local", "user.name", "test")
    git(clone, "config", "--local", "user.email", "t@example.com")
    git(clone, "config", "--local", "user.useConfigOnly", "true")
    author = {
        "email_digest": hashlib.sha256(b"t@example.com").hexdigest(),
        "identity_digest": ac.author_identity_digest("test", "t@example.com"),
        "name_digest": hashlib.sha256(b"test").hexdigest(),
        "source": "clone-local",
        "use_config_only": True,
    }
    repository = {
        "canonical_repository": "github.com/owner/repository",
        "fetch_transport": "https",
        "fetch_url_digest": "1" * 64,
        "push_transport": "https",
        "push_url_digest": "1" * 64,
    }
    receipt = {
        "schema": "clone-provenance/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": "platform-attempt",
        "clone_root": str(clone.resolve()),
        "repository": repository,
        "author": author,
        "frozen_root_sha": frozen,
        "working_branch": branch,
        "status": "ready",
        "generated_at": None,
    }
    receipt["receipt_digest"] = ac.canonical_digest(receipt, exclude_field="receipt_digest")
    (clone / ".git" / "agent-clone-provenance.json").write_text(json.dumps(receipt))
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity.update(
        {
            "provenance_required": True,
            "provenance_status": "ready",
            "provenance_receipt_digest": receipt["receipt_digest"],
        }
    )
    identity_path.write_text(json.dumps(identity))

    git(clone, "switch", "-c", "platform-base", frozen)
    (clone / "BASE.md").write_text("platform base\n")
    git(clone, "add", "BASE.md")
    imported_env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "platform",
        "GIT_AUTHOR_EMAIL": "platform@example.com",
        "GIT_COMMITTER_NAME": "platform",
        "GIT_COMMITTER_EMAIL": "platform@example.com",
    }
    imported = subprocess.run(
        ["git", "-C", str(clone), "commit", "-m", "platform base"],
        capture_output=True,
        text=True,
        env=imported_env,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr
    platform_base = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "branch", "-f", branch, platform_base)
    git(clone, "switch", branch)
    (clone / "README.md").write_text("delivered on platform base\n")
    git(clone, "add", "README.md")
    delivery_env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": delivery_identity[0],
        "GIT_AUTHOR_EMAIL": delivery_identity[1],
        "GIT_COMMITTER_NAME": delivery_identity[0],
        "GIT_COMMITTER_EMAIL": delivery_identity[1],
    }
    delivered = subprocess.run(
        ["git", "-C", str(clone), "commit", "-m", "delivery"],
        capture_output=True,
        text=True,
        env=delivery_env,
        check=False,
    )
    assert delivered.returncode == 0, delivered.stderr
    platform_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "push", "--force", "origin", f"HEAD:refs/heads/{branch}")
    return clone, frozen, platform_base, platform_head


def make_platform_merge_wrapper(
    clone: Path,
    platform_base: str,
    source_head: str,
    *,
    parents: list[str] | None = None,
) -> str:
    """Create a GitHub-authored merge wrapper without moving the source branch."""
    tree = git(clone, "rev-parse", f"{source_head}^{{tree}}").stdout.strip()
    wrapper_env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "GitHub",
        "GIT_AUTHOR_EMAIL": "noreply@github.com",
        "GIT_COMMITTER_NAME": "GitHub",
        "GIT_COMMITTER_EMAIL": "noreply@github.com",
    }
    command = ["git", "-C", str(clone), "commit-tree", tree]
    for parent in parents or [source_head, platform_base]:
        command.extend(["-p", parent])
    created = subprocess.run(
        command,
        input="Merge branch into main\n",
        capture_output=True,
        text=True,
        env=wrapper_env,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    return created.stdout.strip()


def make_platform_base_advance(clone: Path, platform_base: str) -> str:
    """Create one platform-authored empty mainline advance without moving HEAD."""
    tree = git(clone, "rev-parse", f"{platform_base}^{{tree}}").stdout.strip()
    platform_env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "platform",
        "GIT_AUTHOR_EMAIL": "platform@example.com",
        "GIT_COMMITTER_NAME": "platform",
        "GIT_COMMITTER_EMAIL": "platform@example.com",
    }
    created = subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "commit-tree",
            tree,
            "-p",
            platform_base,
        ],
        input="advance platform base\n",
        capture_output=True,
        text=True,
        env=platform_env,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    return created.stdout.strip()


def provenance_platform_runner(
    clone: Path,
    platform_head: str,
    platform_base: str,
    *,
    branch: str,
    calls: list[list[str]] | None = None,
):
    """Run real selective provenance verification while faking only GitHub PR I/O."""
    base_runner = merged_pr_runner(
        platform_head,
        calls,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
    )

    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if (
            len(cmd) >= 3
            and cmd[0] == sys.executable
            and cmd[2] == "retirement-provenance"
        ):
            if calls is not None:
                calls.append(cmd)
            identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
            try:
                base_sha = cmd[cmd.index("--platform-base") + 1]
                head_sha = cmd[cmd.index("--platform-head") + 1]
                ac.verify_clone_provenance(
                    str(clone),
                    identity,
                    platform_base_sha=base_sha,
                    platform_head_sha=head_sha,
                )
            except (ValueError, TypeError, ac.ToolError) as exc:
                return subprocess.CompletedProcess(cmd, 1, "", str(exc))
            return subprocess.CompletedProcess(cmd, 0, '{"ok":true}\n', "")
        return base_runner(cmd, **kwargs)

    return _run


def make_abortable_clone(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """A v2 root-only clone that was deliberately never admitted as a writer."""
    clone, _remote, head = make_retirable_clone(tmp_path)
    attempt = "attempt-001"
    branch = f"agent/agent-1--{attempt}"
    git(clone, "branch", "-m", branch)
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity.update(
        {
            "schema": "agent-clone-identity/v2",
            "agent_id": "agent-1",
            "actor_id": "agent-1",
            "delivery_attempt_id": attempt,
            "canonical_root": str(clone.resolve()),
            "source_url": "https://github.com/owner/repository.git",
            "frozen_root_sha": head,
            "working_branch": branch,
            "profile": "root-only",
            "readiness_profile": "root-only",
            "readiness_status": "degraded",
            "ready": False,
            "required_submodules": [],
        }
    )
    identity_path.write_text(json.dumps(identity))
    baseline = tmp_path / "baseline.json"
    baseline_payload = {
        "schema": "agent-clone-manifest/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": attempt,
        "canonical_root": str(clone.resolve()),
        "origin_url": "https://github.com/owner/repository.git",
        "root_head_sha": head,
        "branch": branch,
        "detached": False,
        "repositories": [],
    }
    baseline_payload["manifest_digest"] = lc._canonical_json_digest(baseline_payload)
    baseline.write_text(json.dumps(baseline_payload))
    readiness = tmp_path / "readiness.json"
    readiness_payload = {
        "schema": "clone-readiness/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": attempt,
        "profile": "root-only",
        "source_url": "https://github.com/owner/repository.git",
        "root_head_sha": head,
        "working_branch": branch,
        "required_submodules": [],
        "initialized_submodules": [],
        "checks": {"writer_admission": {"required": True, "status": "degraded"}},
        "degraded_checks": ["writer_admission"],
        "status": "degraded",
    }
    readiness_payload["receipt_digest"] = lc._canonical_json_digest(readiness_payload)
    readiness.write_text(json.dumps(readiness_payload))
    (clone / ".git" / "agent-clone-readiness.json").write_text(json.dumps(readiness_payload))
    identity["readiness_receipt_digest"] = readiness_payload["receipt_digest"]
    identity_path.write_text(json.dumps(identity))
    authority = tmp_path / "authority"
    (authority / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    return clone, baseline, readiness, head


def abort_runner(head: str, calls: list[list[str]] | None = None):
    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if calls is not None:
            calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:5] == ["remote", "get-url"] and cmd[-1] == "origin":
            return subprocess.CompletedProcess(cmd, 0, "https://github.com/owner/repository.git\n", "")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if len(cmd) >= 4 and cmd[0:2] == ["git", "-C"] and "ls-remote" in cmd:
            return subprocess.CompletedProcess(cmd, 2, "", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
    return _run


def abort_args(tmp_path: Path, clone: Path, baseline: Path, readiness: Path, *, apply: bool = False):
    return argparse.Namespace(
        destination=str(clone), agent_id="agent-1", delivery_attempt_id="attempt-001",
        expected_repository="owner/repository", baseline=str(baseline), readiness=str(readiness),
        claims_root=str(tmp_path / "authority"), evidence=str(tmp_path / "abort-authorization.json"), apply=apply,
    )


def test_abort_unready_dry_run_then_apply_removes_only_exact_degraded_fixture(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    assert lc.cmd_abort_unready(args) == lc.EXIT_OK
    assert clone.exists() and not Path(args.evidence).exists()
    args.apply = True
    assert lc.cmd_abort_unready(args) == lc.EXIT_OK
    assert not clone.exists()
    receipt = json.loads(Path(args.evidence).read_text())
    assert receipt["schema"] == "clone-abort-authorization/v1"
    assert receipt["status"] == "authorized"


def test_abort_unready_rejects_identity_and_readiness_mismatch(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    identity["ready"] = True
    (clone / ".git" / "agent-clone-identity.json").write_text(json.dumps(identity))
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY


def test_abort_unready_rejects_recomputed_readiness_digest_and_baseline_branch_mismatch(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity["readiness_receipt_digest"] = "0" * 64
    identity_path.write_text(json.dumps(identity))
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    identity["readiness_receipt_digest"] = json.loads(readiness.read_text())["receipt_digest"]
    identity_path.write_text(json.dumps(identity))
    baseline_payload = json.loads(baseline.read_text())
    baseline_payload["branch"] = "agent/other--attempt"
    baseline_payload["manifest_digest"] = lc._canonical_json_digest(baseline_payload, "manifest_digest")
    baseline.write_text(json.dumps(baseline_payload))
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    identity["ready"] = False
    (clone / ".git" / "agent-clone-identity.json").write_text(json.dumps(identity))
    payload = json.loads(readiness.read_text())
    payload["degraded_checks"] = ["writer_admission", "dependencies"]
    payload["receipt_digest"] = lc._canonical_json_digest(payload, "receipt_digest")
    readiness.write_text(json.dumps(payload))
    (clone / ".git" / "agent-clone-readiness.json").write_text(json.dumps(payload))
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY


def test_abort_unready_rejects_reflog_ignored_and_stash(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    (clone / "ignored.tmp").write_text("x\n")
    (clone / ".gitignore").write_text(".omo/_delivery/\nignored.tmp\n")
    git(clone, "add", ".gitignore")
    git(clone, "commit", "-m", "ignore")
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    git(clone, "reset", "--hard", head)
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY  # reset hides files, never its attempt reflog.
    git(clone, "reflog", "expire", "--expire=now", "--all")
    git(clone, "gc", "--prune=now")
    (clone / "stash-me").write_text("x\n")
    git(clone, "stash", "push", "-u", "-m", "new work")
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY


def test_abort_unready_allows_divergent_pre_attempt_head_reflog(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    branch = "agent/agent-1--attempt-001"
    git(clone, "switch", "main")
    (clone / "pre-attempt.txt").write_text("not attempt work\n")
    git(clone, "add", "pre-attempt.txt")
    git(clone, "commit", "-m", "pre-attempt clone source")
    git(clone, "switch", branch)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    assert lc.cmd_abort_unready(abort_args(tmp_path, clone, baseline, readiness)) == lc.EXIT_OK


def test_abort_unready_rejects_active_actor_missing_authority_and_symlink(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    run_file = Path(args.claims_root) / ".omo" / "_delivery" / "agent-workflows" / "runs" / "active.yaml"
    run_file.write_text("status: active\nactor: agent-1\n")
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    run_file.unlink()
    shutil = __import__("shutil")
    shutil.rmtree(Path(args.claims_root) / ".omo")
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    (Path(args.claims_root) / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    link = tmp_path / "agent-link" / "ws"
    link.parent.mkdir()
    link.symlink_to(clone, target_is_directory=True)
    args.destination = str(link)
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY


def test_abort_unready_accepts_initialized_submodule_gitfile_and_rejects_authorization_tamper(tmp_path, monkeypatch):
    clone, baseline, readiness, _head = make_abortable_clone(tmp_path)
    child_remote = tmp_path / "child.git"
    child_remote.mkdir()
    git(child_remote, "init", "--bare", "-b", "main")
    child_source = tmp_path / "child-source"
    child_source.mkdir()
    git(child_source, "init", "-b", "main")
    (child_source / "child.txt").write_text("child\n")
    git(child_source, "add", "child.txt")
    git(child_source, "commit", "-m", "child")
    git(child_source, "remote", "add", "origin", str(child_remote))
    git(child_source, "push", "origin", "main")
    configured = git(clone, "-c", "protocol.file.allow=always", "submodule", "add", str(child_remote), "projects/omo")
    assert configured.returncode == 0, configured.stderr
    git(clone, "add", ".gitmodules", "projects/omo")
    git(clone, "commit", "-m", "add child")
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    child_head = git(clone / "projects/omo", "rev-parse", "HEAD").stdout.strip()
    assert (clone / "projects/omo" / ".git").is_file()
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity.update({"frozen_root_sha": head, "required_submodules": ["projects/omo"]})
    identity_path.write_text(json.dumps(identity))
    baseline_payload = json.loads(baseline.read_text())
    baseline_payload.update({"root_head_sha": head, "branch": "agent/agent-1--attempt-001", "detached": False, "repositories": [{"path": "projects/omo", "pinned_sha": child_head, "child_head": child_head, "origin": "https://github.com/owner/repository.git"}]})
    baseline_payload["manifest_digest"] = lc._canonical_json_digest(baseline_payload, "manifest_digest")
    baseline.write_text(json.dumps(baseline_payload))
    readiness_payload = json.loads(readiness.read_text())
    readiness_payload.update({"root_head_sha": head, "required_submodules": [{"path": "projects/omo", "pinned_sha": child_head, "child_head": child_head, "initialized": True, "origin": "https://github.com/owner/repository.git", "expected_origin": "https://github.com/owner/repository.git"}], "initialized_submodules": ["projects/omo"]})
    readiness_payload["receipt_digest"] = lc._canonical_json_digest(readiness_payload, "receipt_digest")
    readiness.write_text(json.dumps(readiness_payload))
    (clone / ".git" / "agent-clone-readiness.json").write_text(json.dumps(readiness_payload))
    identity["readiness_receipt_digest"] = readiness_payload["receipt_digest"]
    identity_path.write_text(json.dumps(identity))
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness)
    assert lc.cmd_abort_unready(args) == lc.EXIT_OK
    args.apply = True
    Path(args.evidence).write_text("{\"schema\":\"forged\"}\n")
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    assert clone.exists()


def test_abort_unready_rejects_evidence_parent_resolving_inside_clone(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    link = tmp_path / "evidence-link"
    link.symlink_to(clone / ".git", target_is_directory=True)
    evidence = link / "receipt.json"
    payload = lc._authorization_payload(abort_args(tmp_path, clone, baseline, readiness), clone, "a" * 64)
    assert lc._write_authorization(str(evidence), payload, clone) is False
    assert not (clone / ".git" / "receipt.json").exists()


def test_abort_unready_authorization_parent_swap_never_writes_into_clone(tmp_path, monkeypatch):
    clone, baseline, readiness, _head = make_abortable_clone(tmp_path)
    parent = tmp_path / "evidence-parent"
    parent.mkdir()
    evidence = parent / "receipt.json"
    payload = lc._authorization_payload(abort_args(tmp_path, clone, baseline, readiness), clone, "a" * 64)
    real_open = lc.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        result = real_open(path, flags, *args, **kwargs)
        if (Path(path) == parent or path == parent.name) and not swapped:
            swapped = True
            original = tmp_path / "evidence-parent-original"
            parent.rename(original)
            parent.symlink_to(clone / ".git", target_is_directory=True)
        return result

    monkeypatch.setattr(lc.os, "open", swapping_open)
    assert lc._write_authorization(str(evidence), payload, clone) is False
    assert swapped is True
    assert not (clone / ".git" / "receipt.json").exists()


def test_abort_unready_authorization_rejects_inode_preserving_ancestor_swap(tmp_path, monkeypatch):
    clone, baseline, readiness, _head = make_abortable_clone(tmp_path)
    root = tmp_path / "evidence-root"
    parent = root / "parent"
    parent.mkdir(parents=True)
    evidence = parent / "receipt.json"
    payload = lc._authorization_payload(abort_args(tmp_path, clone, baseline, readiness), clone, "a" * 64)
    real_open = lc.os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        result = real_open(path, flags, *args, **kwargs)
        if (Path(path) == parent or path == "parent") and not swapped:
            swapped = True
            parent.rename(clone / ".git" / "parent")
            root.rename(tmp_path / "evidence-root-original")
            root.symlink_to(clone / ".git", target_is_directory=True)
        return result

    monkeypatch.setattr(lc.os, "open", swapping_open)
    assert lc._write_authorization(str(evidence), payload, clone) is False
    assert swapped is True
    assert not (clone / ".git" / "parent" / "receipt.json").exists()


def test_abort_unready_second_read_race_restores_clone(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(lc, "run", abort_runner(head, calls))
    args = abort_args(tmp_path, clone, baseline, readiness, apply=True)
    real_assess = lc._abort_assessment
    count = 0
    def race_assessment(*values):
        nonlocal count
        count += 1
        if count == 2:
            return None, "remote_changed"
        return real_assess(*values)
    monkeypatch.setattr(lc, "_abort_assessment", race_assessment)
    assert lc.cmd_abort_unready(args) == lc.EXIT_POLICY
    assert clone.exists()
    assert Path(args.evidence).exists()


def test_abort_unready_absent_requires_matching_authorization_and_parser_preserves_retire(tmp_path, monkeypatch):
    clone, baseline, readiness, head = make_abortable_clone(tmp_path)
    monkeypatch.setattr(lc, "run", abort_runner(head))
    args = abort_args(tmp_path, clone, baseline, readiness, apply=True)
    assert lc.cmd_abort_unready(args) == lc.EXIT_OK
    assert lc.cmd_abort_unready(args) == lc.EXIT_OK
    bad = argparse.Namespace(**vars(args))
    bad.delivery_attempt_id = "other"
    assert lc.cmd_abort_unready(bad) == lc.EXIT_POLICY
    parser = lc.build_parser()
    dry = parser.parse_args(["abort-unready", "--destination", "/tmp/a/ws", "--agent-id", "a", "--delivery-attempt-id", "x", "--expected-repository", "owner/repo", "--baseline", "/tmp/b", "--readiness", "/tmp/r", "--claims-root", "/tmp/c"])
    apply = parser.parse_args(["abort-unready", "--destination", "/tmp/a/ws", "--agent-id", "a", "--delivery-attempt-id", "x", "--expected-repository", "owner/repo", "--baseline", "/tmp/b", "--readiness", "/tmp/r", "--claims-root", "/tmp/c", "--apply", "--evidence", "/tmp/e"])
    retire = parser.parse_args(["retire", "--destination", "/tmp/a/ws"])
    assert dry.apply is False and apply.apply is True and retire.func is lc.cmd_retire


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
            readiness=None,
            provenance=None,
            expected_repository=None,
            profile=None,
            submodule=["projects/omo"],
            all_submodules=False,
        )
    )

    assert rc == 0
    assert calls[0][calls[0].index("--revision") + 1] == "origin/main"
    assert "--no-submodules" not in calls[0]
    assert calls[0][-2:] == ["--submodule", "projects/omo"]
    assert calls[2][2] == "verify"
    assert calls[3][2] == "readiness"
    assert (tmp_path / "agent-1").is_dir()


def test_onboard_forwards_transport_sources_and_returns_create_transport(tmp_path, monkeypatch, capsys):
    calls: list[list[str]] = []
    transport = {"schema": "clone-transport/v1", "transport_digest": "digest"}

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        stdout = json.dumps({"transport": transport}) if cmd[2] == "create" else "{}"
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_onboard(
        argparse.Namespace(
            agent_id="agent-1", delivery_attempt_id="attempt-1", source="authority", revision="origin/main",
            transport_source="/tmp/local-root", submodule_source=["projects/omo=/tmp/local-omo"],
            destination=str(tmp_path / "agent-1" / "ws"), manifest=str(tmp_path / "baseline.json"),
            readiness=str(tmp_path / "readiness.json"), provenance=str(tmp_path / "provenance.json"),
            expected_repository="owner/repo", profile=None, submodule=["projects/omo"], all_submodules=False,
        )
    )
    assert rc == lc.EXIT_OK
    create = calls[0]
    assert create[create.index("--transport-source") + 1] == "/tmp/local-root"
    assert create[create.index("--submodule-source") + 1] == "projects/omo=/tmp/local-omo"
    assert json.loads(capsys.readouterr().out)["transport"] == transport


def test_onboard_defaults_to_governance_profile_and_emits_readiness(tmp_path, monkeypatch):
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
            readiness=str(tmp_path / "readiness.json"),
            provenance=str(tmp_path / "provenance.json"),
            expected_repository="starlink-awaken/omostation",
            profile=None,
            submodule=[],
            all_submodules=False,
        )
    )

    assert rc == 0
    assert calls[0][-2:] == ["--profile", "governance"]
    assert calls[1][2] == "provenance"
    assert calls[1][calls[1].index("--expected-repository") + 1] == "starlink-awaken/omostation"
    assert calls[1][-2:] == ["--output", str(tmp_path / "provenance.json")]
    assert calls[4][2] == "readiness"
    assert calls[4][-2:] == ["--output", str(tmp_path / "readiness.json")]


def test_onboard_passes_attempt_and_qualifies_default_receipt_paths(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(lc, "run", fake_run)
    dest = tmp_path / "actor-1" / "attempts" / "attempt-001" / "ws"
    rc = lc.cmd_onboard(
        argparse.Namespace(
            agent_id="actor-1",
            delivery_attempt_id="attempt-001",
            source="source",
            revision="origin/main",
            destination=str(dest),
            manifest=None,
            readiness=None,
            provenance=None,
            expected_repository="starlink-awaken/omostation",
            profile=None,
            submodule=[],
            all_submodules=False,
        )
    )

    assert rc == lc.EXIT_OK
    create = calls[0]
    assert create[create.index("--delivery-attempt-id") + 1] == "attempt-001"
    manifest = calls[2]
    provenance = calls[1]
    readiness = calls[4]
    assert manifest[manifest.index("--output") + 1].endswith(
        "actor-1-attempt-001-baseline.json"
    )
    assert provenance[provenance.index("--output") + 1].endswith(
        "actor-1-attempt-001-provenance.json"
    )
    assert readiness[readiness.index("--output") + 1].endswith(
        "actor-1-attempt-001-readiness.json"
    )


def test_onboard_all_submodules_maps_to_full_named_profile(tmp_path, monkeypatch):
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
            readiness=str(tmp_path / "readiness.json"),
            provenance=str(tmp_path / "provenance.json"),
            expected_repository="starlink-awaken/omostation",
            profile=None,
            submodule=[],
            all_submodules=True,
        )
    )

    assert rc == 0
    assert calls[0][-2:] == ["--profile", "full"]
    assert calls[1][2] == "provenance"
    assert calls[4][2] == "readiness"


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
    transported = parser.parse_args(
        [
            "onboard", "--agent-id", "agent-1", "--destination", "/tmp/agent-1/ws",
            "--transport-source", "/tmp/root", "--submodule-source", "projects/omo=/tmp/omo",
        ]
    )

    assert default.revision == "origin/main"
    assert pinned.revision == "refs/tags/baseline-v1"
    assert default.profile is None
    assert default.expected_repository is None
    assert default.provenance is None
    assert transported.transport_source == "/tmp/root"
    assert transported.submodule_source == ["projects/omo=/tmp/omo"]


def test_bound_repository_slug_reenters_provenance_guard(tmp_path, monkeypatch):
    clone = tmp_path / "agent-1" / "ws"
    (clone / ".git").mkdir(parents=True)
    (clone / ".git" / "agent-clone-provenance.json").write_text(
        json.dumps(
            {
                "repository": {
                    "canonical_repository": "github.com/starlink-awaken/omostation"
                }
            }
        )
    )
    calls: list[tuple[list[str], dict]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, '{"ok":true}\n', "")

    monkeypatch.setattr(lc, "run", fake_run)
    slug, error = lc.bound_repository_slug(
        clone,
        {
            "agent_id": "agent-1",
            "provenance_required": True,
        },
    )

    assert error is None
    assert slug == "starlink-awaken/omostation"
    assert calls[0][0][1] == str(lc.AGENT_CLONE)
    assert "guard" in calls[0][0]
    assert calls[0][1]["env"]["AGENT_ID"] == "agent-1"


def test_makefile_has_one_clone_onboard_target_and_separate_scan_target():
    makefile = (lc.ROOT / "Makefile").read_text(encoding="utf-8")
    target_lines = [line for line in makefile.splitlines() if line.startswith("clone-onboard:")]
    assert len(target_lines) == 1
    assert "clone-onboard-scan:" in makefile
    assert makefile.count('test -n "$(DELIVERY_ATTEMPT_ID)"') == 5
    assert makefile.count("agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)") >= 5
    assert "--delivery-attempt-id $(DELIVERY_ATTEMPT_ID)" in makefile
    assert 'test -n "$(CLAIMS_ROOT)"' in makefile
    assert '--claims-root "$(CLAIMS_ROOT)"' in makefile


def test_snapshot_creates_valid_manifest(tmp_path):
    """snapshot 生成有效 manifest."""
    clone, _remote, _head = make_retirable_clone(tmp_path)
    output = tmp_path / "baseline.json"
    rc = lc.cmd_snapshot(argparse.Namespace(clone=str(clone), output=str(output)))
    assert rc == 0
    d = json.loads(output.read_text())
    assert "root_head_sha" in d
    assert "repositories" in d


def test_readiness_resume_routes_through_agent_clone(tmp_path, monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, '{"status":"ready"}\n', "")

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_readiness(
        argparse.Namespace(
            clone=str(tmp_path / "agent" / "ws"),
            manifest=str(tmp_path / "baseline.json"),
            output=str(tmp_path / "readiness.json"),
        )
    )

    assert rc == 0
    assert calls[0][2] == "readiness"
    assert calls[0][-2:] == ["--output", str(tmp_path / "readiness.json")]
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


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
    clone, _remote, _head = make_retirable_clone(tmp_path)
    qualify_clone_attempt(clone)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
            dry_run=True,
        )
    )
    assert rc == 0
    out = capsys.readouterr()
    assert "dry_run" in out.out


def test_integrate_dry_run_rejects_legacy_v1_clone(tmp_path, capsys):
    clone, _remote, _head = make_retirable_clone(tmp_path)

    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
            dry_run=True,
        )
    )

    assert rc == lc.EXIT_POLICY
    assert "identity" in capsys.readouterr().err


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
    wrong_attempt = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-002",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )
    assert wrong_attempt == lc.EXIT_POLICY
    assert not any(cmd[:4] == ["git", "-C", str(clone), "push"] for cmd in calls)
    calls.clear()
    capsys.readouterr()

    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
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
    assert any(
        "agent/agent-1--attempt-001" in cmd
        for cmd in calls
        if cmd[:3] == ["gh", "pr", "list"]
    )


def test_attempt_changeset_and_integrate_bind_exact_pr_head(tmp_path, monkeypatch, capsys):
    clone, _remote, _initial_head = make_retirable_clone(tmp_path)
    branch = qualify_clone_attempt(clone)
    baseline, changeset, authority, head = make_verified_changeset(tmp_path, clone)

    stored = json.loads(changeset.read_text())
    assert stored["schema"] == "cross-repo-changeset/v3"
    assert stored["actor_id"] == "agent-1"
    assert stored["delivery_attempt_id"] == "attempt-001"

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == [
            "remote",
            "get-url",
            "origin",
        ]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "git@github.com:owner/repository.git\n",
                "",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, "https://example.test/pr/9\n", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    wrong_attempt = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-002",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )
    assert wrong_attempt == lc.EXIT_POLICY
    assert not any(cmd[:4] == ["git", "-C", str(clone), "push"] for cmd in calls)
    calls.clear()
    capsys.readouterr()

    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == lc.EXIT_OK
    result = json.loads(capsys.readouterr().out)
    assert result["branch"] == branch
    assert result["actor_id"] == "agent-1"
    assert result["delivery_attempt_id"] == "attempt-001"
    assert result["head_sha"] == head
    pr_list = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    pr_create = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    push = next(cmd for cmd in calls if cmd[:4] == ["git", "-C", str(clone), "push"])
    assert push[4:] == [
        "--porcelain",
        f"--force-with-lease=refs/heads/{branch}:",
        "origin",
        f"{head}:refs/heads/{branch}",
    ]
    assert pr_list[pr_list.index("--head") + 1] == branch
    assert pr_create[pr_create.index("--head") + 1] == f"owner:{branch}"


def test_integrate_rejects_atomic_attempt_branch_race_before_pr(
    tmp_path,
    monkeypatch,
    capsys,
):
    clone, _remote, _initial_head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, _head = make_verified_changeset(tmp_path, clone)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == [
            "remote",
            "get-url",
            "origin",
        ]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "git@github.com:owner/repository.git\n",
                "",
            )
        if cmd[:4] == ["git", "-C", str(clone), "push"]:
            if any(arg.startswith("--force-with-lease=") for arg in cmd):
                return subprocess.CompletedProcess(cmd, 1, "", "stale info")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["gh", "pr"]:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == lc.EXIT_POLICY
    assert not any(cmd[:2] == ["gh", "pr"] for cmd in calls)
    assert "push" in capsys.readouterr().err


def test_integrate_rejects_same_head_remote_attempt_as_reuse(
    tmp_path,
    monkeypatch,
    capsys,
):
    clone, _remote, _initial_head = make_retirable_clone(tmp_path)
    baseline, changeset, authority, _head = make_verified_changeset(tmp_path, clone)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:6] == [
            "remote",
            "get-url",
            "origin",
        ]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "git@github.com:owner/repository.git\n",
                "",
            )
        if cmd[:4] == ["git", "-C", str(clone), "push"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "To origin\n=\tHEAD:refs/heads/agent/agent-1--attempt-001\t[up to date]\nDone\n",
                "",
            )
        if cmd[:2] == ["gh", "pr"]:
            raise AssertionError("reused attempt must stop before PR lookup")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)

    monkeypatch.setattr(lc, "run", fake_run)
    rc = lc.cmd_integrate(
        argparse.Namespace(
            clone=str(clone),
            agent_id="agent-1",
            delivery_attempt_id="attempt-001",
            dry_run=False,
            base="main",
            baseline=str(baseline),
            changeset=str(changeset),
            claims_root=str(authority),
        )
    )

    assert rc == lc.EXIT_POLICY
    assert "delivery_attempt_reused" in capsys.readouterr().err


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
                    "headRefName": "agent/agent-1--attempt-001",
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
            delivery_attempt_id="attempt-001",
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
    assert pr_call[pr_call.index("--head") + 1] == "agent/agent-1--attempt-001"


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
            delivery_attempt_id="attempt-001",
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
            delivery_attempt_id="attempt-001",
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
            delivery_attempt_id="attempt-001",
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
            delivery_attempt_id="attempt-001",
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
            delivery_attempt_id="attempt-001",
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
    base_args = [
        "integrate",
        "--clone",
        "/tmp/c",
        "--agent-id",
        "agent-1",
        "--delivery-attempt-id",
        "attempt-001",
    ]
    dry = parser.parse_args(base_args)
    apply = parser.parse_args([*base_args, "--apply"])

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


def test_retire_platform_rebase_requires_explicit_pr_flag(tmp_path, monkeypatch, capsys):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "push", "origin", "--delete", branch)
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(
            platform_head,
            branch=branch,
            platform_head=platform_head,
            platform_base=platform_base,
        ),
    )

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == original
    assert '"reason": "pr_not_merged"' in capsys.readouterr().err


def test_retire_rejects_legacy_platform_rebase_without_provenance(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _original_base = (
        make_platform_rebased_clone(tmp_path)
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    calls: list[list[str]] = []
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(
            original,
            calls,
            branch=branch,
            platform_head=platform_head,
            platform_base=platform_base,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == original
    assert '"reason": "platform_provenance_required"' in capsys.readouterr().err
    assert not any(
        len(cmd) >= 3
        and cmd[0] == sys.executable
        and cmd[1] == str(lc.AGENT_CLONE)
        and cmd[2] == "retirement-provenance"
        for cmd in calls
    )


def test_retire_accepts_exact_platform_rebase_source_proof_for_provenance_clone(
    tmp_path, monkeypatch, capsys
):
    clone, frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "switch", "-c", "original-source", frozen)
    (clone / "README.md").write_text("delivered on platform base\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "original delivery")
    original_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "branch", "-f", branch, original_head)
    git(clone, "switch", branch)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])
    calls: list[list[str]] = []
    monkeypatch.setattr(
        lc,
        "run",
        provenance_platform_runner(
            clone,
            platform_head,
            platform_base,
            branch=branch,
            calls=calls,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_OK
    assert not clone.exists()
    proof = json.loads(capsys.readouterr().out)["platform_rebased_source_proof"]
    assert proof["original_head_sha"] == original_head
    assert proof["platform_head_sha"] == platform_head
    assert proof["platform_base_sha"] == platform_base
    assert proof["original_base_sha"] == frozen
    assert proof["changed_paths"] == ["README.md"]
    assert proof["receipt_digest"] == lc._canonical_json_digest(
        proof, "receipt_digest"
    )
    assert any(
        len(cmd) >= 3
        and cmd[0] == sys.executable
        and cmd[1] == str(lc.AGENT_CLONE)
        and cmd[2] == "retirement-provenance"
        for cmd in calls
    )


def test_retire_rejects_wrong_author_in_rewritten_platform_head_when_local_head_differs(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _original_base = (
        make_platform_rebased_clone(tmp_path)
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity["provenance_required"] = True
    identity_path.write_text(json.dumps(identity))
    (clone / ".git" / "agent-clone-provenance.json").write_text(
        json.dumps(
            {
                "repository": {
                    "canonical_repository": "github.com/owner/repository"
                }
            }
        )
    )
    base_runner = merged_pr_runner(
        original,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
    )
    calls: list[list[str]] = []

    def wrong_platform_author_runner(
        cmd: list[str], **kwargs
    ) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if (
            len(cmd) >= 3
            and cmd[0] == sys.executable
            and cmd[1] == str(lc.AGENT_CLONE)
        ):
            if cmd[2] == "guard":
                return subprocess.CompletedProcess(cmd, 0, '{"ok":true}\n', "")
            if cmd[2] == "retirement-provenance":
                return subprocess.CompletedProcess(
                    cmd,
                    lc.EXIT_POLICY,
                    "",
                    "platform delivery author differs from clone author",
                )
        return base_runner(cmd, **kwargs)

    monkeypatch.setattr(lc, "run", wrong_platform_author_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert any(
        len(cmd) >= 3
        and cmd[0] == sys.executable
        and cmd[1] == str(lc.AGENT_CLONE)
        and cmd[2] == "retirement-provenance"
        for cmd in calls
    )
    assert '"reason": "clone_provenance_mismatch"' in capsys.readouterr().err


def test_platform_provenance_verifies_exact_pr_range_when_local_head_differs(
    tmp_path, monkeypatch
):
    clone, frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "switch", "-c", "original-source", frozen)
    (clone / "README.md").write_text("delivered on platform base\n")
    git(clone, "add", "README.md")
    git(clone, "commit", "-m", "original delivery")
    original_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "branch", "-f", branch, original_head)
    git(clone, "switch", branch)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    verified = ac.verify_clone_provenance(
        str(clone),
        identity,
        platform_base_sha=platform_base,
        platform_head_sha=platform_head,
    )

    assert verified == receipt
    assert original_head != platform_head


def test_platform_provenance_accepts_exact_github_merge_wrapper(
    tmp_path, monkeypatch
):
    clone, _frozen, platform_base, source_head = (
        make_advanced_platform_provenance_clone(tmp_path)
    )
    wrapper_head = make_platform_merge_wrapper(clone, platform_base, source_head)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    verified = ac.verify_clone_provenance(
        str(clone),
        identity,
        platform_base_sha=platform_base,
        platform_head_sha=wrapper_head,
    )

    assert verified == receipt
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == source_head


def test_platform_provenance_accepts_repeated_github_merge_wrappers(
    tmp_path, monkeypatch
):
    clone, _frozen, first_base, source_head = (
        make_advanced_platform_provenance_clone(tmp_path)
    )
    first_wrapper = make_platform_merge_wrapper(clone, first_base, source_head)
    final_base = make_platform_base_advance(clone, first_base)
    final_wrapper = make_platform_merge_wrapper(clone, final_base, first_wrapper)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    verified = ac.verify_clone_provenance(
        str(clone),
        identity,
        platform_base_sha=final_base,
        platform_head_sha=final_wrapper,
    )

    assert verified == receipt
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == source_head


def test_repeated_platform_wrapper_rejects_non_ancestor_side_parent(
    tmp_path, monkeypatch
):
    clone, frozen, first_base, source_head = (
        make_advanced_platform_provenance_clone(tmp_path)
    )
    unrelated_side = make_platform_base_advance(clone, frozen)
    first_wrapper = make_platform_merge_wrapper(
        clone,
        unrelated_side,
        source_head,
    )
    final_base = make_platform_base_advance(clone, first_base)
    final_wrapper = make_platform_merge_wrapper(clone, final_base, first_wrapper)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    with pytest.raises(ac.ToolError) as exc_info:
        ac.verify_clone_provenance(
            str(clone),
            identity,
            platform_base_sha=final_base,
            platform_head_sha=final_wrapper,
        )

    assert exc_info.value.reason == "clone_provenance_mismatch"


def test_platform_merge_wrapper_still_rejects_wrong_delivery_author(
    tmp_path, monkeypatch
):
    clone, _frozen, platform_base, source_head = (
        make_advanced_platform_provenance_clone(
            tmp_path,
            delivery_identity=("intruder", "intruder@example.com"),
        )
    )
    wrapper_head = make_platform_merge_wrapper(clone, platform_base, source_head)
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    with pytest.raises(ac.ToolError) as exc_info:
        ac.verify_clone_provenance(
            str(clone),
            identity,
            platform_base_sha=platform_base,
            platform_head_sha=wrapper_head,
        )

    assert exc_info.value.reason == "clone_provenance_mismatch"


def test_platform_merge_wrapper_rejects_non_base_second_parent(
    tmp_path, monkeypatch
):
    clone, _frozen, platform_base, source_head = (
        make_advanced_platform_provenance_clone(tmp_path)
    )
    wrapper_head = make_platform_merge_wrapper(
        clone,
        platform_base,
        source_head,
        parents=[platform_base, source_head],
    )
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    identity = json.loads((clone / ".git" / "agent-clone-identity.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])

    with pytest.raises(ac.ToolError) as exc_info:
        ac.verify_clone_provenance(
            str(clone),
            identity,
            platform_base_sha=platform_base,
            platform_head_sha=wrapper_head,
        )

    assert exc_info.value.reason == "clone_provenance_mismatch"


def test_retire_accepts_provenance_clone_on_advanced_platform_base(
    tmp_path, monkeypatch, capsys
):
    clone, frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    calls: list[list[str]] = []
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])
    monkeypatch.setattr(
        lc,
        "run",
        provenance_platform_runner(
            clone,
            platform_head,
            platform_base,
            branch=branch,
            calls=calls,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_OK
    assert not clone.exists()
    result = json.loads(capsys.readouterr().out)
    proof = result["platform_rebased_source_proof"]
    assert proof["original_base_sha"] == platform_base
    assert proof["platform_head_sha"] == platform_head
    assert proof["original_head_sha"] == platform_head
    assert proof["changed_paths"] == ["README.md"]
    guard_call = next(
        cmd
        for cmd in calls
        if len(cmd) >= 3
        and cmd[0] == sys.executable
        and cmd[1] == str(lc.AGENT_CLONE)
        and cmd[2] == "retirement-provenance"
    )
    assert guard_call[guard_call.index("--platform-base") + 1] == platform_base
    assert guard_call[guard_call.index("--platform-head") + 1] == platform_head
    assert frozen != platform_base


def test_retire_rejects_wrong_author_in_platform_delivery_range(
    tmp_path, monkeypatch, capsys
):
    clone, _frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path,
        delivery_identity=("intruder", "intruder@example.com"),
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])
    monkeypatch.setattr(
        lc,
        "run",
        provenance_platform_runner(
            clone,
            platform_head,
            platform_base,
            branch=branch,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "clone_provenance_mismatch"' in capsys.readouterr().err


def test_retire_rejects_verified_receipt_repository_different_from_pr_query(
    tmp_path, monkeypatch, capsys
):
    clone, _frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    receipt_path = clone / ".git" / "agent-clone-provenance.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["repository"]["canonical_repository"] = "github.com/other/repository"
    receipt["receipt_digest"] = ac.canonical_digest(receipt, exclude_field="receipt_digest")
    receipt_path.write_text(json.dumps(receipt))
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity["provenance_receipt_digest"] = receipt["receipt_digest"]
    identity_path.write_text(json.dumps(identity))
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])
    monkeypatch.setattr(
        lc,
        "run",
        provenance_platform_runner(
            clone,
            platform_head,
            platform_base,
            branch=branch,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "platform_repository_binding_mismatch"' in capsys.readouterr().err


def test_retire_rejects_origin_change_after_platform_guard(
    tmp_path, monkeypatch, capsys
):
    clone, _frozen, platform_base, platform_head = make_advanced_platform_provenance_clone(
        tmp_path
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    receipt = json.loads((clone / ".git" / "agent-clone-provenance.json").read_text())
    monkeypatch.setattr(ac, "repository_provenance", lambda *_args: receipt["repository"])
    monkeypatch.setattr(ac, "live_author_identity", lambda *_args: receipt["author"])
    stable = provenance_platform_runner(
        clone,
        platform_head,
        platform_base,
        branch=branch,
    )
    origin_reads = 0

    def changed_origin_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal origin_reads
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:5] == ["remote", "get-url"]:
            origin_reads += 1
            if origin_reads > 1:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "git@github.com:other/repository.git\n",
                    "",
                )
        return stable(cmd, **kwargs)

    monkeypatch.setattr(lc, "run", changed_origin_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert origin_reads >= 2
    assert '"reason": "platform_origin_raced"' in capsys.readouterr().err


@pytest.mark.parametrize(
    ("runner_overrides", "reason"),
    [
        ({"platform_pr": 8}, "platform_pr_identity_mismatch"),
        ({"branch": "agent/other"}, "platform_pr_identity_mismatch"),
        ({"platform_owner": "other"}, "platform_pr_identity_mismatch"),
        ({"platform_repo": "other/repository"}, "platform_pr_identity_mismatch"),
        ({"platform_base_name": "release"}, "platform_pr_identity_mismatch"),
        ({"platform_state": "OPEN"}, "platform_pr_not_merged"),
    ],
)
def test_retire_rejects_wrong_platform_pr_identity(
    tmp_path, monkeypatch, capsys, runner_overrides, reason
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    kwargs = {
        "branch": branch,
        "platform_head": platform_head,
        "platform_base": platform_base,
        "provenance_guard_ok": True,
        **runner_overrides,
    }
    monkeypatch.setattr(lc, "run", merged_pr_runner(original, **kwargs))

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert f'"reason": "{reason}"' in capsys.readouterr().err


@pytest.mark.parametrize("missing", ["head", "base"])
def test_retire_platform_rebase_requires_local_objects(
    tmp_path, monkeypatch, capsys, missing
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "push", "origin", "--delete", branch, check=False)
    fake = "f" * 40
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(
            original,
            branch=branch,
            platform_head=fake if missing == "head" else platform_head,
            platform_base=fake if missing == "base" else platform_base,
            provenance_guard_ok=True,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "platform_object_missing"' in capsys.readouterr().err


def test_retire_platform_rebase_rejects_non_equivalent_tree(tmp_path, monkeypatch, capsys):
    clone, original, _platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "switch", "platform-head")
    (clone / "EXTRA.md").write_text("not delivery\n")
    git(clone, "add", "EXTRA.md")
    git(clone, "commit", "-m", "different platform result")
    different_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "push", "--force", "origin", f"{different_head}:refs/heads/{branch}")
    git(clone, "switch", branch)
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(
            original,
            branch=branch,
            platform_head=different_head,
            platform_base=platform_base,
            provenance_guard_ok=True,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "platform_tree_mismatch"' in capsys.readouterr().err


def test_retire_platform_rebase_rechecks_live_proof_before_quarantine(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    stable = merged_pr_runner(
        original,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
        provenance_guard_ok=True,
    )
    views = 0

    def drifting_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal views
        result = stable(cmd, **kwargs)
        if cmd[:3] == ["gh", "pr", "view"]:
            views += 1
            if views == 2:
                payload = json.loads(result.stdout)
                payload["head_ref_oid"] = "e" * 40
                return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return result

    monkeypatch.setattr(lc, "run", drifting_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert views == 2
    assert '"reason": "platform_proof_raced"' in capsys.readouterr().err


def test_retire_platform_rebase_restores_clone_on_quarantine_live_drift(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    stable = merged_pr_runner(
        original,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
        provenance_guard_ok=True,
    )
    views = 0

    def drifting_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal views
        result = stable(cmd, **kwargs)
        if cmd[:3] == ["gh", "pr", "view"]:
            views += 1
            if views == 3:
                payload = json.loads(result.stdout)
                payload["base_ref_oid"] = "e" * 40
                return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return result

    monkeypatch.setattr(lc, "run", drifting_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == original
    assert views == 3
    assert "post-quarantine verification changed; original path restored" in capsys.readouterr().err


def test_retire_platform_rebase_restores_clone_on_quarantine_origin_drift(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    stable = merged_pr_runner(
        original,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
        provenance_guard_ok=True,
    )
    origin_reads = 0

    def drifting_origin_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal origin_reads
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:5] == ["remote", "get-url"]:
            origin_reads += 1
            if origin_reads >= 4:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "git@github.com:other/repository.git\n",
                    "",
                )
        return stable(cmd, **kwargs)

    monkeypatch.setattr(lc, "run", drifting_origin_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == original
    assert origin_reads >= 4
    assert not list(clone.parent.glob(".ws.retire-quarantine-*"))
    stderr = capsys.readouterr().err
    assert '"reason": "destination_raced"' in stderr
    assert "post-quarantine verification changed; original path restored" in stderr


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_retire_platform_rebase_rejects_non_exact_live_schema(
    tmp_path, monkeypatch, capsys, mutation
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    stable = merged_pr_runner(
        original,
        branch=branch,
        platform_head=platform_head,
        platform_base=platform_base,
        provenance_guard_ok=True,
    )

    def schema_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        result = stable(cmd, **kwargs)
        if cmd[:3] == ["gh", "pr", "view"]:
            payload = json.loads(result.stdout)
            if mutation == "missing":
                del payload["base_ref_oid"]
            else:
                payload["unexpected"] = "field"
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return result

    monkeypatch.setattr(lc, "run", schema_runner)

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "platform_pr_query_invalid"' in capsys.readouterr().err


def test_retire_platform_rebase_requires_surviving_branch_at_platform_head(
    tmp_path, monkeypatch, capsys
):
    clone, original, platform_head, platform_base, _initial = make_platform_rebased_clone(
        tmp_path, provenance=True
    )
    branch = git(clone, "branch", "--show-current").stdout.strip()
    git(clone, "push", "--force", "origin", f"{platform_base}:refs/heads/{branch}")
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(
            original,
            branch=branch,
            platform_head=platform_head,
            platform_base=platform_base,
            provenance_guard_ok=True,
        ),
    )

    rc = lc.cmd_retire(
        argparse.Namespace(destination=str(clone), platform_rebased_pr=7)
    )

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert '"reason": "head_not_pushed"' in capsys.readouterr().err


def test_retire_parser_exposes_platform_rebased_pr():
    args = lc.build_parser().parse_args(
        ["retire", "--destination", "/tmp/agent/ws", "--platform-rebased-pr", "2004"]
    )

    assert args.platform_rebased_pr == 2004


def test_agent_clone_keeps_platform_author_scope_out_of_default_guard():
    parser = ac.build_parser()
    retirement = parser.parse_args(
        [
            "retirement-provenance",
            "--clone",
            "/tmp/agent/ws",
            "--platform-base",
            "a" * 40,
            "--platform-head",
            "b" * 40,
        ]
    )

    assert retirement.func is ac.cmd_retirement_provenance
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "guard",
                "--workspace",
                "/tmp/agent/ws",
                "--platform-base",
                "a" * 40,
                "--platform-head",
                "b" * 40,
            ]
        )


def test_retire_removes_ready_attempt_qualified_v2_clone(tmp_path, monkeypatch):
    clone, _remote, head = make_retirable_clone(tmp_path)
    branch = qualify_clone_attempt(clone, "attempt-002")
    provenance = {
        "schema": "clone-provenance/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": "attempt-002",
        "clone_root": str(clone.resolve()),
        "repository": {
            "canonical_repository": "github.com/owner/repository",
            "fetch_transport": "https",
            "fetch_url_digest": "1" * 64,
            "push_transport": "https",
            "push_url_digest": "1" * 64,
        },
        "author": {
            "email_digest": "2" * 64,
            "identity_digest": "3" * 64,
            "name_digest": "4" * 64,
            "source": "clone-local",
            "use_config_only": True,
        },
        "frozen_root_sha": head,
        "working_branch": branch,
        "status": "ready",
        "generated_at": "2026-08-23T00:00:00Z",
    }
    provenance["receipt_digest"] = lc._canonical_json_digest(provenance)
    (clone / ".git" / "agent-clone-provenance.json").write_text(json.dumps(provenance))
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity.update(
        {
            "provenance_required": True,
            "provenance_status": "ready",
            "provenance_receipt_digest": provenance["receipt_digest"],
        }
    )
    identity_path.write_text(json.dumps(identity))
    calls: list[list[str]] = []
    monkeypatch.setattr(
        lc,
        "run",
        merged_pr_runner(head, calls, branch=branch, provenance_guard_ok=True),
    )

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_OK
    assert not clone.exists()
    assert any(
        len(cmd) >= 3
        and cmd[0] == sys.executable
        and cmd[1] == str(lc.AGENT_CLONE)
        and cmd[2] == "guard"
        and "--require-clone" in cmd
        for cmd in calls
    )
    pr_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    assert branch in pr_call


@pytest.mark.parametrize("binding", ["actor", "attempt", "branch"])
def test_retire_rejects_v2_clone_without_exact_actor_attempt_binding(tmp_path, monkeypatch, binding):
    clone, _remote, head = make_retirable_clone(tmp_path)
    branch = qualify_clone_attempt(clone, "attempt-002")
    identity_path = clone / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    if binding == "actor":
        identity["actor_id"] = "other-agent"
    elif binding == "attempt":
        identity["delivery_attempt_id"] = ""
    else:
        identity["working_branch"] = "agent/agent-1"
    identity_path.write_text(json.dumps(identity))
    calls: list[list[str]] = []
    monkeypatch.setattr(lc, "run", merged_pr_runner(head, calls, branch=branch))

    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))

    assert rc == lc.EXIT_POLICY
    assert clone.exists()
    assert not any(cmd[:3] == ["gh", "pr"] for cmd in calls)


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


# ---------------------------------------------------------------------------
# T1-02 squash-successor clone retirement — Phase 3 TDD tests
# ---------------------------------------------------------------------------


def make_squash_merged_clone(tmp_path: Path) -> tuple[Path, Path, str, str, str, str, str]:
    """构建 squash-successor topology。"""
    remote = tmp_path / "remote.git"
    import shutil
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir()
    git(remote, "init", "--bare", "-b", "main")
    clone = tmp_path / "agent-1" / "ws"
    clone.mkdir(parents=True)
    git(clone, "init", "-b", "main")
    (clone / "README.md").write_text("root\n")
    policy = clone / ".omo" / "_truth" / "registry" / "swarm-coordination.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text("topology_migration:\n  integration_root: 'x'\n")
    git(clone, "add", "README.md", str(policy.relative_to(clone)))
    git(clone, "commit", "-m", "initial")
    git(clone, "remote", "add", "origin", str(remote))
    git(clone, "push", "origin", "HEAD:refs/heads/main")
    frozen_root = git(clone, "rev-parse", "HEAD").stdout.strip()

    foreign_env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "platform",
        "GIT_AUTHOR_EMAIL": "platform@example.com",
        "GIT_COMMITTER_NAME": "platform",
        "GIT_COMMITTER_EMAIL": "platform@example.com",
    }
    (clone / "MAIN1.md").write_text("main succ 1\n")
    git(clone, "add", "MAIN1.md")
    r = subprocess.run(["git", "-C", str(clone), "commit", "-m", "main successor 1"],
                       capture_output=True, text=True, env=foreign_env)
    assert r.returncode == 0, r.stderr
    main_succ_1 = git(clone, "rev-parse", "HEAD").stdout.strip()

    (clone / "MAIN2.md").write_text("main succ 2\n")
    git(clone, "add", "MAIN2.md")
    r = subprocess.run(["git", "-C", str(clone), "commit", "-m", "main successor 2"],
                       capture_output=True, text=True, env=foreign_env)
    assert r.returncode == 0, r.stderr
    main_succ_2 = git(clone, "rev-parse", "HEAD").stdout.strip()
    delivery_base = main_succ_2

    git(clone, "switch", "-c", "agent/agent-1", frozen_root)
    git(clone, "merge", "main", "-m", "merge main into delivery branch")
    (clone / "DELIVERY.md").write_text("delivery\n")
    git(clone, "add", "DELIVERY.md")
    git(clone, "commit", "-m", "delivery")
    delivery_head = git(clone, "rev-parse", "HEAD").stdout.strip()
    git(clone, "switch", "main")
    (clone / "BASE.md").write_text("pr base\n")
    git(clone, "add", "BASE.md")
    r = subprocess.run(["git", "-C", str(clone), "commit", "-m", "pr base"],
                       capture_output=True, text=True, env=foreign_env)
    assert r.returncode == 0, r.stderr
    pr_base = git(clone, "rev-parse", "HEAD").stdout.strip()

    # squash merge: single parent = pr_base, tree = delivery_tree (用 merge --squash)
    git(clone, "checkout", "main")
    r = subprocess.run(["git", "-C", str(clone), "merge", "--squash", "agent/agent-1"],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"merge --squash failed: {r.stderr}"
    git(clone, "commit", "-m", "squash merge #2881")
    main_head = git(clone, "rev-parse", "HEAD").stdout.strip()

    tag_name = "delivery/test-v1"
    subprocess.run(
        ["git", "-C", str(clone), "tag", "-a", tag_name, delivery_head, "-m", "delivery tag"],
        check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(clone), "push", "origin", tag_name],
                   check=True, capture_output=True)
    git(clone, "push", "-u", "origin", "agent/agent-1")
    # push main so origin/main includes the squash merge
    git(clone, "push", "origin", "main")

    # 构建 v2 identity
    subprocess.run(["git", "-C", str(clone), "checkout", "agent/agent-1"],
                   check=True, capture_output=True)
    identity = {
        "schema": "agent-clone-identity/v2",
        "agent_id": "agent-1",
        "actor_id": "agent-1",
        "delivery_attempt_id": "t1-02-fixture",
        "canonical_root": str(clone.resolve()),
        "source_url": str(remote.resolve()),
        "frozen_root_sha": frozen_root,
        "working_branch": "agent/agent-1",
        "ready": True,
    }
    (clone / ".git" / "agent-clone-identity.json").write_text(json.dumps(identity))
    # 确保 working tree clean
    subprocess.run(['git', '-C', str(clone), 'checkout', '--', '.'],
                   check=True, capture_output=True)
    subprocess.run(['git', '-C', str(clone), 'clean', '-fd'],
                   check=True, capture_output=True)


    return clone, remote, delivery_head, pr_base, delivery_base, tag_name, main_head


def test_retire_squash_successor_ordinary_retire_fails(tmp_path, monkeypatch, capsys):
    """RED: squash-successor topology 走普通退场应失败。"""
    clone, _remote, delivery_head, _pr_base, _delivery_base, _tag, _main = \
        make_squash_merged_clone(tmp_path)
    monkeypatch.setattr(lc, "run", merged_pr_runner(delivery_head))
    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))
    assert rc == lc.EXIT_POLICY
    assert clone.exists()


def _squash_pr_runner(head: str, merge_commit: str, pr_base: str,
                      calls: list[list[str]] | None = None, provenance_ok: bool = True):
    """Mock runner for squash-merged PR retirement test."""
    def _run(cmd: list[str], **kwargs):
        if calls is not None:
            calls.append(cmd)
        if (provenance_ok and len(cmd) >= 3
                and cmd[0] == sys.executable and cmd[1] == str(lc.AGENT_CLONE)
                and cmd[2] in {"guard", "retirement-provenance"}):
            return subprocess.CompletedProcess(cmd, 0, '{"ok":true}\n', "")
        if len(cmd) >= 6 and cmd[0:2] == ["git", "-C"] and cmd[3:5] == ["remote", "get-url"] and cmd[-1] == "origin":
            return subprocess.CompletedProcess(cmd, 0, "git@github.com:owner/repository.git\n", "")
        if cmd[:3] == ["gh", "pr", "view"]:
            payload = {
                "base_ref_name": "main",
                "base_ref_oid": pr_base,
                "branch": "agent/agent-1",
                "head_ref_oid": head,
                "merge_commit_oid": merge_commit,
                "number": 2881,
                "owner": "owner",
                "repository": "owner/repository",
                "state": "MERGED",
                "url": "https://example.test/pr/2881",
            }
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
    return _run


def test_retire_squash_successor_full_flow(tmp_path, monkeypatch):
    """GREEN: 完整 squash-successor 退场流程。"""
    clone, _remote, delivery_head, pr_base, delivery_base, tag_name, main_head = \
        make_squash_merged_clone(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(lc, "run", _squash_pr_runner(delivery_head, main_head, pr_base, calls))
    evidence = tmp_path / "squash-retirement-proof.json"
    ns = argparse.Namespace(
        destination=str(clone),
        platform_rebased_pr=None,
        squash_merged_pr=2881,
        source_tag=tag_name,
        delivery_base=delivery_base,
        evidence=str(evidence),
    )
    rc = lc.cmd_retire(ns)
    assert rc == 0, f"expected EXIT_OK, got {rc}"
    assert not clone.exists(), "clone should be deleted"
    assert evidence.exists(), "proof receipt should exist"
    di_path = Path(f"{evidence}.delete-intent")
    assert di_path.exists(), "delete-intent receipt should exist"
    st_path = Path(f"{evidence}.settled")
    assert st_path.exists(), "settlement receipt should exist"
    # 验证 receipt 链 digest 一致性
    proof = json.loads(evidence.read_text())
    di = json.loads(di_path.read_text())
    st = json.loads(st_path.read_text())
    assert di["proof_digest"] == proof["receipt_digest"]
    assert st["proof_digest"] == proof["receipt_digest"]
    assert st["delete_intent_digest"] == di["receipt_digest"]
    assert proof["status"] == "verified_for_retirement"
    assert di["status"] == "delete_authorized"
    assert st["status"] == "retired"


def test_retire_squash_successor_defers_bound_provenance_until_pr_base(
    tmp_path, monkeypatch
):
    """Squash mode must not use the ordinary provenance range before P3/P5."""
    clone, _remote, delivery_head, pr_base, delivery_base, tag_name, main_head = \
        make_squash_merged_clone(tmp_path)
    monkeypatch.setattr(
        lc,
        "run",
        _squash_pr_runner(delivery_head, main_head, pr_base),
    )
    monkeypatch.setattr(
        lc,
        "bound_repository_slug",
        lambda *_args: pytest.fail(
            "squash retirement must resolve live origin before it knows the PR base"
        ),
    )
    evidence = tmp_path / "squash-retirement-proof.json"
    rc = lc.cmd_retire(
        argparse.Namespace(
            destination=str(clone),
            platform_rebased_pr=None,
            squash_merged_pr=2881,
            source_tag=tag_name,
            delivery_base=delivery_base,
            evidence=str(evidence),
        )
    )

    assert rc == lc.EXIT_OK
    assert not clone.exists()
    assert Path(f"{evidence}.settled").exists()


    """RED: squash-successor topology 走普通退场应失败。"""
    clone, _remote, delivery_head, _pr_base, _delivery_base, _tag, _main = \
        make_squash_merged_clone(tmp_path)
    monkeypatch.setattr(lc, "run", merged_pr_runner(delivery_head))
    rc = lc.cmd_retire(argparse.Namespace(destination=str(clone)))
    assert rc == lc.EXIT_POLICY
    assert clone.exists()


def test_retire_squash_successor_cli_recognized():
    """GREEN: --squash-merged-pr 参数已被 parser 识别。"""
    ns = lc.build_parser().parse_args([
        "retire",
        "--destination", "/tmp/nonexistent",
        "--squash-merged-pr", "2881",
        "--source-tag", "delivery/test-v1",
        "--delivery-base", "a" * 40,
        "--evidence", "/tmp/proof.json",
    ])
    assert ns.squash_merged_pr == 2881
    assert ns.source_tag == "delivery/test-v1"
    assert ns.delivery_base == "a" * 40
    assert ns.evidence == "/tmp/proof.json"


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
