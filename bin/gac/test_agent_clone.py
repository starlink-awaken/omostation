"""Real-repository tests for bin/gac/agent-clone.py (BET-Y1Q1-T1-05 D1 pilot).

Every test builds real temporary git repositories (source, bare remote,
submodule) and drives the CLI via subprocess.  No source-string assertions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "bin" / "gac" / "agent-clone.py"
MANAGED_PYTHON = Path(__file__).resolve().parents[2] / "bin" / "gac" / "managed-python"
PRE_COMMIT = Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"
CANONICAL_REPOSITORY = "starlink-awaken/omostation"
CANONICAL_REMOTE = "https://github.com/starlink-awaken/omostation.git"

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(cwd: Path, *args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    e.update(_GIT_ENV)
    if env:
        e.update(env)
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=e,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd} (rc={proc.returncode}):\n{proc.stderr}")
    return proc


def run_cli(
    *argv: str,
    env: dict | None = None,
    check: bool = True,
    trusted_root: Path | None = None,
    cwd: Path | None = None,
    auto_attempt: bool = True,
) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    if env:
        e.update(env)
    else:
        # never leak an ambient AGENT_ID from the host into guard tests
        e.pop("AGENT_ID", None)
    effective_argv = list(argv)
    if (
        auto_attempt
        and effective_argv[:1] == ["create"]
        and "--delivery-attempt-id" not in effective_argv
    ):
        effective_argv.extend(["--delivery-attempt-id", "attempt-test"])
    argv = tuple(effective_argv)
    command = [sys.executable, str(TOOL), *argv]
    if "--claims-root" in argv:
        root = trusted_root or Path(argv[argv.index("--claims-root") + 1])
        bootstrap = (
            "import importlib.util,sys; from pathlib import Path; "
            "p=Path(sys.argv[2]); s=importlib.util.spec_from_file_location('agent_clone_test_cli',p); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "m.ACCOUNT_WORKSPACE_ROOT=Path(sys.argv[1]); raise SystemExit(m.main(sys.argv[3:]))"
        )
        command = [sys.executable, "-c", bootstrap, str(root), str(TOOL), *argv]
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=e,
        cwd=cwd,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"agent-clone {' '.join(argv)} failed (rc={proc.returncode}):\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def parse_json(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


def load_tool_module():
    spec = importlib.util.spec_from_file_location("agent_clone_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_canonical(obj: dict, exclude: str | None = None) -> str:
    if exclude is not None:
        obj = {k: v for k, v in obj.items() if k != exclude}
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def make_source(base: Path, submodule_name: str = "childmod", with_hooks: bool = False) -> tuple[Path, Path, Path]:
    """Build source repo with one submodule and a bare remote.

    Returns (source, child, bare).
    """
    child = base / "child-repo"
    child.mkdir(parents=True)
    git(child, "init", "-b", "main")
    (child / "f.txt").write_text("c1\n")
    git(child, "add", "f.txt")
    git(child, "commit", "-m", "c1")

    src = base / "source-repo"
    src.mkdir(parents=True)
    git(src, "init", "-b", "main")
    (src / "README.md").write_text("root\n")
    policy = src / ".omo" / "_truth" / "registry" / "swarm-coordination.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        "topology_migration:\n"
        f"  integration_root: '{(base / 'authority').resolve()}'\n"
    )
    git(src, "add", "README.md", str(policy.relative_to(src)))
    git(
        src,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(child),
        submodule_name,
    )
    if with_hooks:
        (src / ".githooks").mkdir()
        (src / ".githooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
        git(src, "add", ".githooks")
    git(src, "commit", "-m", "m1")

    bare = base / "source-bare.git"
    git(base, "init", "--bare", "-b", "main", "source-bare.git")
    git(src, "remote", "add", "origin", str(bare))
    git(src, "push", "-u", "origin", "main")
    return src, child, bare


def make_governance_profile_source(base: Path) -> tuple[Path, Path]:
    """Build a root repo exposing the exact governance profile gitlinks."""
    child = base / "governance-child"
    child.mkdir(parents=True)
    git(child, "init", "-b", "main")
    (child / "payload.txt").write_text("governance\n")
    git(child, "add", "payload.txt")
    git(child, "commit", "-m", "child")

    src = base / "governance-source"
    src.mkdir()
    git(src, "init", "-b", "main")
    (src / "README.md").write_text("root\n")
    policy = src / ".omo" / "_truth" / "registry" / "swarm-coordination.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        "topology_migration:\n"
        f"  integration_root: '{(base / 'authority').resolve()}'\n"
    )
    hooks = src / ".githooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    tool_dir = src / "bin" / "gac"
    tool_dir.mkdir(parents=True)
    shutil.copy2(MANAGED_PYTHON, tool_dir / "managed-python")
    (tool_dir / "managed-python").chmod(0o755)
    workflow = src / "bin" / "agent-workflow.py"
    workflow.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "if sys.argv[1:] == ['status', '--json']:\n"
        "    print(json.dumps({'ok': True}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(2)\n"
    )
    workflow.chmod(0o755)
    git(src, "add", "README.md", ".omo", ".githooks", "bin")
    for path in (
        "projects/omo",
        "projects/ecos",
        "projects/agora",
        "projects/cockpit",
        "projects/cockpit-ui",
    ):
        git(
            src,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(child),
            path,
        )
    git(src, "commit", "-m", "governance profile")
    bare = base / "governance-source.git"
    git(base, "init", "--bare", "-b", "main", bare.name)
    git(src, "remote", "add", "origin", str(bare))
    git(src, "push", "-u", "origin", "main")
    return src, bare


def make_nested_source(base: Path) -> tuple[Path, Path]:
    nested = base / "nested"
    nested.mkdir()
    git(nested, "init", "-b", "main")
    (nested / "nested.txt").write_text("nested\n")
    git(nested, "add", "nested.txt")
    git(nested, "commit", "-m", "nested")

    outer = base / "outer"
    outer.mkdir()
    src, child, bare = make_source(outer)
    git(
        child,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(nested),
        "grandchild",
    )
    git(child, "commit", "-m", "add nested")
    git(src / "childmod", "fetch", "origin")
    git(src / "childmod", "checkout", git(child, "rev-parse", "HEAD").stdout.strip())
    git(src, "add", "childmod")
    git(src, "commit", "-m", "advance child pointer")
    git(src, "push", "origin", "main")
    return bare, nested


def create_clone(tmp: Path, bare: Path, name: str = "clone", **extra: object) -> Path:
    dest = tmp / name
    argv = [
        "create",
        "--json",
        "--agent-id",
        "agent-1",
        "--delivery-attempt-id",
        "attempt-helper",
        "--source",
        str(bare),
        "--destination",
        str(dest),
    ]
    for flag, value in extra.items():
        argv.append(f"--{flag.replace('_', '-')}")
        if value is not True:
            argv.append(str(value))
    proc = run_cli(*argv, check=False)
    assert proc.returncode == 0, proc.stderr
    assert parse_json(proc)["reason"] == "clone_created"
    authority = tmp / "authority"
    if not authority.exists():
        cloned = subprocess.run(
            ["git", "clone", "--no-recurse-submodules", str(bare), str(authority)],
            capture_output=True,
            text=True,
            env={**os.environ, **_GIT_ENV},
            check=False,
        )
        assert cloned.returncode == 0, cloned.stderr
    return dest


def write_manifest(tmp: Path, clone: Path, name: str = "manifest.json") -> Path:
    out = tmp / name
    proc = run_cli("manifest", "--clone", str(clone), "--output", str(out), "--json")
    assert parse_json(proc)["reason"] == "manifest_generated"
    return out


def bind_provenance(tmp: Path, clone: Path, name: str = "provenance.json") -> Path:
    """Bind one clone to the canonical root repository and local Git identity."""
    git(clone, "config", "--local", "user.name", "Agent One")
    git(clone, "config", "--local", "user.email", "agent-one@example.test")
    git(clone, "remote", "set-url", "origin", CANONICAL_REMOTE)
    output = tmp / name
    proc = run_cli(
        "provenance",
        "--clone",
        str(clone),
        "--expected-repository",
        CANONICAL_REPOSITORY,
        "--output",
        str(output),
        "--json",
        env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    assert parse_json(proc)["status"] == "ready"
    return output


def write_active_claim(authority: Path, *paths: str, actor: str = "agent-1", name: str = "active") -> Path:
    runs = authority / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    rendered = "\n".join(f"      - {path}" for path in paths)
    run = runs / f"{name}.yaml"
    run.write_text(
        f"run_id: {name}\nstatus: active\nactor: human-owner\nupdated_at: '2026-08-21T00:00:00Z'\n"
        f"claims:\n  - actor: {actor}\n    claimed_at: '2026-08-21T00:00:01Z'\n    paths:\n{rendered}\n"
    )
    return run


def tamper_manifest(path: Path, mutate, recompute: bool = True) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    if recompute:
        data["manifest_digest"] = sha256_canonical(data, exclude="manifest_digest")
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# create + independence
# ---------------------------------------------------------------------------


def test_create_requires_delivery_attempt_id(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(tmp_path / "missing-attempt"),
        check=False,
        auto_attempt=False,
    )

    assert proc.returncode != 0
    assert "--delivery-attempt-id" in proc.stderr


def test_create_clone_with_submodule_and_no_alternates(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    assert (dest / "README.md").exists()
    assert (dest / "childmod" / "f.txt").exists()

    # identity lives under the git common dir and is never a tracked file
    ident_file = dest / ".git" / "agent-clone-identity.json"
    assert ident_file.is_file()
    assert "agent-clone-identity.json" not in git(dest, "ls-files").stdout
    identity = json.loads(ident_file.read_text())
    assert identity["agent_id"] == "agent-1"
    assert identity["canonical_root"] == str(dest.resolve())
    assert identity["frozen_root_sha"] == git(dest, "rev-parse", "HEAD").stdout.strip()
    assert identity["schema"] == "agent-clone-identity/v2"
    assert identity["delivery_attempt_id"] == "attempt-helper"
    assert identity["working_branch"] == "agent/agent-1--attempt-helper"
    assert git(dest, "branch", "--show-current").stdout.strip() == identity["working_branch"]

    # no persistent alternates anywhere in the clone
    assert not (dest / ".git" / "objects" / "info" / "alternates").exists()
    assert not (dest / ".git" / "modules" / "childmod" / "objects" / "info" / "alternates").exists()

    # cloned independently: removing the source leaves the clone fully functional
    bare_contents = git(tmp_path / "source-bare.git", "rev-parse", "HEAD").stdout.strip()
    shutil.rmtree(tmp_path / "source-bare.git")
    assert git(dest, "rev-parse", "HEAD").stdout.strip() == bare_contents


def test_attempt_qualified_identity_binds_manifest_provenance_readiness_and_guard(tmp_path):
    _src, bare = make_governance_profile_source(tmp_path)
    dest = tmp_path / "attempt-clone"
    created = run_cli(
        "create",
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--profile",
        "governance",
        "--json",
        check=False,
    )
    assert created.returncode == 0, created.stderr
    payload = parse_json(created)
    assert payload["actor_id"] == "actor-1"
    assert payload["delivery_attempt_id"] == "attempt-001"
    assert payload["working_branch"] == "agent/actor-1--attempt-001"

    identity_path = dest / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    assert identity["schema"] == "agent-clone-identity/v2"
    assert identity["agent_id"] == identity["actor_id"] == "actor-1"
    assert identity["delivery_attempt_id"] == "attempt-001"
    assert git(dest, "branch", "--show-current").stdout.strip() == identity["working_branch"]

    provenance_path = bind_provenance(tmp_path, dest, "attempt-provenance.json")
    manifest_path = write_manifest(tmp_path, dest, "attempt-manifest.json")
    readiness_path = tmp_path / "attempt-readiness.json"
    ready = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest_path),
        "--output",
        str(readiness_path),
        "--json",
        env={"OMO_MANAGED_PYTHON": sys.executable},
    )
    assert parse_json(ready)["status"] == "ready"

    manifest = json.loads(manifest_path.read_text())
    provenance = json.loads(provenance_path.read_text())
    readiness = json.loads(readiness_path.read_text())
    for receipt, schema in (
        (manifest, "agent-clone-manifest/v2"),
        (provenance, "clone-provenance/v2"),
        (readiness, "clone-readiness/v2"),
    ):
        assert receipt["schema"] == schema
        assert receipt["actor_id"] == "actor-1"
        assert receipt["delivery_attempt_id"] == "attempt-001"

    admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "actor-1"},
    )
    admission = parse_json(admitted)
    assert admission["state"] == "verified_clone"
    assert admission["actor_id"] == "actor-1"
    assert admission["delivery_attempt_id"] == "attempt-001"


def test_attempt_id_cannot_reuse_an_existing_remote_branch(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    first = tmp_path / "first-attempt"
    created = run_cli(
        "create",
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--source",
        str(bare),
        "--destination",
        str(first),
        "--no-submodules",
        "--json",
    )
    branch = parse_json(created)["working_branch"]
    git(first, "push", "origin", branch)

    second = run_cli(
        "create",
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--source",
        str(bare),
        "--destination",
        str(tmp_path / "second-attempt"),
        "--no-submodules",
        "--json",
        check=False,
    )
    assert second.returncode != 0
    assert parse_json(second)["reason"] == "delivery_attempt_reused"
    assert not (tmp_path / "second-attempt").exists()


def test_attempt_manifest_mismatch_is_rejected_after_digest_recompute(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "attempt-clone"
    run_cli(
        "create",
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--no-submodules",
        "--json",
    )
    manifest = write_manifest(tmp_path, dest, "attempt-manifest.json")
    tamper_manifest(
        manifest,
        lambda data: data.update(delivery_attempt_id="attempt-002"),
    )

    rejected = run_cli(
        "verify",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--json",
        check=False,
    )
    assert rejected.returncode != 0
    assert parse_json(rejected)["reason"] == "identity_mismatch"


def test_attempt_changeset_keeps_stable_claim_actor_and_rejects_attempt_mismatch(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "attempt-clone"
    run_cli(
        "create",
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--no-submodules",
        "--json",
    )
    baseline = write_manifest(tmp_path, dest, "attempt-baseline.json")
    authority = tmp_path / "authority"
    cloned = subprocess.run(
        ["git", "clone", "--no-recurse-submodules", str(bare), str(authority)],
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr
    write_active_claim(authority, "README.md", actor="actor-1")
    (dest / "README.md").write_text("attempt delivery\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "attempt delivery")
    changeset = tmp_path / "attempt-changeset.json"
    generated = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(changeset),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
        trusted_root=authority,
    )
    assert parse_json(generated)["changes_count"] == 1
    receipt = json.loads(changeset.read_text())
    assert receipt["schema"] == "cross-repo-changeset/v3"
    assert receipt["actor_id"] == "actor-1"
    assert receipt["delivery_attempt_id"] == "attempt-001"
    assert receipt["claim_verification"]["snapshot"]["agent_id"] == "actor-1"

    verified = run_cli(
        "verify-changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--changeset",
        str(changeset),
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-001",
        "--claims-root",
        str(authority),
        "--json",
        trusted_root=authority,
    )
    assert parse_json(verified)["ok"] is True

    rejected = run_cli(
        "verify-changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--changeset",
        str(changeset),
        "--agent-id",
        "actor-1",
        "--delivery-attempt-id",
        "attempt-002",
        "--claims-root",
        str(authority),
        "--json",
        trusted_root=authority,
        check=False,
    )
    assert rejected.returncode != 0
    assert parse_json(rejected)["reason"] == "changeset_attempt_mismatch"


def test_create_initializes_only_root_gitlinks(tmp_path):
    bare, _nested = make_nested_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    assert (dest / "childmod" / ".git").exists()
    assert not (dest / "childmod" / "grandchild" / ".git").exists()


def test_create_initializes_only_requested_submodules(tmp_path):
    src, _child, bare = make_source(tmp_path)
    second = tmp_path / "second-child"
    second.mkdir()
    git(second, "init", "-b", "main")
    (second / "second.txt").write_text("second\n")
    git(second, "add", "second.txt")
    git(second, "commit", "-m", "second")
    git(
        src,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(second),
        "secondmod",
    )
    git(src, "commit", "-m", "add second child")
    git(src, "push", "origin", "main")

    dest = tmp_path / "selective-clone"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--submodule",
        "childmod",
        "--json",
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_json(proc)
    assert result["initialized_submodules"] == ["childmod"]
    assert (dest / "childmod" / ".git").exists()
    assert not (dest / "secondmod" / ".git").exists()


def test_named_submodule_profiles_are_exact_and_root_only_is_read_only():
    tool = load_tool_module()
    gitlinks = {
        "projects/omo": "1" * 40,
        "projects/ecos": "2" * 40,
        "projects/agora": "3" * 40,
        "projects/cockpit": "4" * 40,
        "projects/cockpit-ui": "5" * 40,
        "projects/runtime": "6" * 40,
    }

    assert tool.resolve_submodule_profile("root-only", gitlinks) == []
    assert tool.resolve_submodule_profile("governance", gitlinks) == [
        "projects/agora",
        "projects/cockpit",
        "projects/cockpit-ui",
        "projects/ecos",
        "projects/omo",
    ]
    assert tool.resolve_submodule_profile("full", gitlinks) == sorted(gitlinks)


def test_readiness_remote_projection_redacts_credentials_and_query_tokens():
    tool = load_tool_module()
    assert (
        tool.redact_remote("https://user:secret@github.com/org/repo.git?token=hidden#fragment")
        == "https://github.com/org/repo.git"
    )
    assert tool.redact_remote("git@github.com:org/repo.git") == "github.com:org/repo.git"


def test_root_remote_canonicalization_binds_transport_and_repository():
    tool = load_tool_module()

    https = tool.canonical_remote_descriptor(
        "https://GitHub.com/StarLink-Awaken/OMOStation.git/"
    )
    ssh = tool.canonical_remote_descriptor(
        "git@github.com:starlink-awaken/omostation.git"
    )

    assert https["canonical_repository"] == "github.com/starlink-awaken/omostation"
    assert https["transport"] == "https"
    assert ssh["canonical_repository"] == https["canonical_repository"]
    assert ssh["transport"] == "ssh"

    for invalid in (
        "https://user:secret@github.com/starlink-awaken/omostation.git",
        "https://github.com/starlink-awaken/omostation.git?token=secret",
        "https://github.com/starlink-awaken/omostation.git#fragment",
        "ssh://git@github.com:2222/starlink-awaken/omostation.git",
        "https://example.test/starlink-awaken/omostation.git",
    ):
        with pytest.raises(tool.ToolError) as exc:
            tool.canonical_remote_descriptor(invalid)
        assert exc.value.reason == "repository_provenance_invalid"


def test_provenance_rejects_fetch_push_repository_mismatch(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    git(dest, "config", "--local", "user.name", "Agent One")
    git(dest, "config", "--local", "user.email", "agent-one@example.test")
    git(dest, "remote", "set-url", "origin", CANONICAL_REMOTE)
    git(dest, "remote", "set-url", "--push", "origin", "git@github.com:someone/fork.git")

    proc = run_cli(
        "provenance",
        "--clone",
        str(dest),
        "--expected-repository",
        CANONICAL_REPOSITORY,
        "--output",
        str(tmp_path / "mismatch.json"),
        "--json",
        env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "repository_provenance_mismatch"


def test_provenance_rejects_ambiguous_multiple_fetch_urls(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    git(dest, "config", "--local", "user.name", "Agent One")
    git(dest, "config", "--local", "user.email", "agent-one@example.test")
    git(dest, "remote", "set-url", "origin", CANONICAL_REMOTE)
    git(dest, "remote", "set-url", "--add", "origin", "git@github.com:starlink-awaken/omostation.git")

    proc = run_cli(
        "provenance",
        "--clone",
        str(dest),
        "--expected-repository",
        CANONICAL_REPOSITORY,
        "--output",
        str(tmp_path / "ambiguous.json"),
        "--json",
        env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "repository_provenance_invalid"


def test_provenance_receipt_redacts_author_and_live_guard_revalidates(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    receipt_path = bind_provenance(tmp_path, dest)

    receipt_text = receipt_path.read_text()
    receipt = json.loads(receipt_text)
    assert receipt["schema"] == "clone-provenance/v2"
    assert receipt["repository"]["canonical_repository"] == (
        "github.com/starlink-awaken/omostation"
    )
    assert receipt["repository"]["fetch_url_digest"]
    assert receipt["repository"]["push_url_digest"]
    assert receipt["author"]["identity_digest"]
    assert "Agent One" not in receipt_text
    assert "agent-one@example.test" not in receipt_text

    admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    assert parse_json(admitted)["state"] == "verified_clone"

    hook_env_admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={
            "AGENT_ID": "agent-1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Agent One",
            "GIT_AUTHOR_EMAIL": "agent-one@example.test",
            "GIT_COMMITTER_NAME": "Agent One",
            "GIT_COMMITTER_EMAIL": "agent-one@example.test",
        },
        cwd=dest,
    )
    assert parse_json(hook_env_admitted)["state"] == "verified_clone"

    repository_env_admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={
            "AGENT_ID": "agent-1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "remote.origin.url",
            "GIT_CONFIG_VALUE_0": "https://github.com/someone/spoofed.git",
            "GIT_INDEX_FILE": ".git/index",
            "GIT_AUTHOR_NAME": "Agent One",
            "GIT_AUTHOR_EMAIL": "agent-one@example.test",
            "GIT_COMMITTER_NAME": "Agent One",
            "GIT_COMMITTER_EMAIL": "agent-one@example.test",
        },
        cwd=dest,
    )
    assert parse_json(repository_env_admitted)["state"] == "verified_clone"

    overridden = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={
            "AGENT_ID": "agent-1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Other",
            "GIT_AUTHOR_EMAIL": "other@example.test",
            "GIT_COMMITTER_NAME": "Other",
            "GIT_COMMITTER_EMAIL": "other@example.test",
        },
        check=False,
    )
    assert overridden.returncode == 1
    assert parse_json(overridden)["reason"] == "clone_provenance_mismatch"

    git(dest, "remote", "set-url", "origin", "https://github.com/someone/fork.git")
    drifted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )
    assert drifted.returncode == 1
    assert parse_json(drifted)["reason"] == "clone_provenance_mismatch"


def test_provenance_binding_refuses_non_frozen_head(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    (dest / "README.md").write_text("post-create\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "post create")
    git(dest, "config", "--local", "user.name", "Agent One")
    git(dest, "config", "--local", "user.email", "agent-one@example.test")
    git(dest, "remote", "set-url", "origin", CANONICAL_REMOTE)

    proc = run_cli(
        "provenance",
        "--clone",
        str(dest),
        "--expected-repository",
        CANONICAL_REPOSITORY,
        "--output",
        str(tmp_path / "late.json"),
        "--json",
        env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "provenance_late_binding"


def test_guard_rejects_committed_author_outside_bound_identity(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    bind_provenance(tmp_path, dest)
    (dest / "README.md").write_text("wrong author\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "wrong author")

    rejected = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )

    assert rejected.returncode == 1
    assert parse_json(rejected)["reason"] == "clone_provenance_mismatch"


def test_expected_submodule_origin_uses_git_resolved_relative_url(tmp_path):
    tool = load_tool_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / ".gitmodules").write_text(
        '[submodule "projects/omo"]\n'
        "\tpath = projects/omo\n"
        "\turl = ../omostation-omo.git\n"
    )
    git(
        repo,
        "config",
        "submodule.projects/omo.url",
        "https://github.com/starlink-awaken/omostation-omo.git",
    )

    assert tool.expected_submodule_origins(repo)["projects/omo"] == (
        "https://github.com/starlink-awaken/omostation-omo.git"
    )


def test_governance_profile_emits_verified_readiness_receipt(tmp_path):
    _src, bare = make_governance_profile_source(tmp_path)
    dest = tmp_path / "governance-clone"
    created = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--profile",
        "governance",
        "--json",
    )
    assert parse_json(created)["profile"] == "governance"
    provenance_path = bind_provenance(tmp_path, dest, "governance-provenance.json")
    manifest = write_manifest(tmp_path, dest, "governance-manifest.json")
    receipt_path = tmp_path / "governance-readiness.json"

    ready = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--output",
        str(receipt_path),
        "--json",
        env={"OMO_MANAGED_PYTHON": sys.executable},
    )

    result = parse_json(ready)
    receipt = json.loads(receipt_path.read_text())
    assert result["status"] == "ready"
    assert receipt["schema"] == "clone-readiness/v2"
    assert receipt["profile_schema"] == "clone-submodule-profile/v1"
    assert receipt["profile"] == "governance"
    assert [item["path"] for item in receipt["required_submodules"]] == [
        "projects/agora",
        "projects/cockpit",
        "projects/cockpit-ui",
        "projects/ecos",
        "projects/omo",
    ]
    assert receipt["checks"]["managed_python_pyyaml"]["status"] == "pass"
    assert receipt["checks"]["workflow_entrypoint"]["status"] == "pass"
    assert receipt["checks"]["clone_provenance"]["status"] == "pass"
    assert json.loads(provenance_path.read_text())["status"] == "ready"
    assert receipt["receipt_digest"] == sha256_canonical(receipt, exclude="receipt_digest")
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["readiness_status"] == "ready"
    assert identity["readiness_receipt_digest"] == receipt["receipt_digest"]
    resumed = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--output",
        str(receipt_path),
        "--json",
        env={"OMO_MANAGED_PYTHON": sys.executable},
    )
    assert parse_json(resumed)["receipt_digest"] == receipt["receipt_digest"]
    admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
    )
    assert parse_json(admitted)["state"] == "verified_clone"

    hook_index_admitted = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={
            "AGENT_ID": "agent-1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_INDEX_FILE": ".git/index",
            "GIT_AUTHOR_NAME": "Agent One",
            "GIT_AUTHOR_EMAIL": "agent-one@example.test",
            "GIT_COMMITTER_NAME": "Agent One",
            "GIT_COMMITTER_EMAIL": "agent-one@example.test",
        },
        cwd=dest,
    )
    assert parse_json(hook_index_admitted)["state"] == "verified_clone"

    (dest / "README.md").write_text("next commit\n")
    git(dest, "add", "README.md")
    git(
        dest,
        "commit",
        "-m",
        "next commit",
        env={
            "GIT_AUTHOR_NAME": "Agent One",
            "GIT_AUTHOR_EMAIL": "agent-one@example.test",
            "GIT_COMMITTER_NAME": "Agent One",
            "GIT_COMMITTER_EMAIL": "agent-one@example.test",
        },
    )
    descendant = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    assert parse_json(descendant)["state"] == "verified_clone"

    internal_receipt = dest / ".git" / "agent-clone-readiness.json"
    tampered = json.loads(internal_receipt.read_text())
    tampered["status"] = "degraded"
    internal_receipt.write_text(json.dumps(tampered))
    rejected = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert rejected.returncode == 1
    assert parse_json(rejected)["reason"] == "clone_readiness_mismatch"

def test_root_only_profile_receipt_is_degraded_and_not_writer_ready(tmp_path):
    _src, bare = make_governance_profile_source(tmp_path)
    dest = tmp_path / "root-only-clone"
    created = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--profile",
        "root-only",
        "--json",
    )
    assert parse_json(created)["initialized_submodules"] == []
    manifest = write_manifest(tmp_path, dest, "root-only-manifest.json")
    receipt_path = tmp_path / "root-only-readiness.json"

    degraded = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--output",
        str(receipt_path),
        "--json",
        env={"OMO_MANAGED_PYTHON": sys.executable},
    )

    receipt = json.loads(receipt_path.read_text())
    assert parse_json(degraded)["status"] == "degraded"
    assert receipt["status"] == "degraded"
    assert "writer_admission" in receipt["degraded_checks"]
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["ready"] is False
    rejected = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert rejected.returncode == 1
    assert parse_json(rejected)["reason"] == "clone_readiness_mismatch"

    forged = json.loads((dest / ".git" / "agent-clone-readiness.json").read_text())
    forged["status"] = "ready"
    forged["degraded_checks"] = []
    forged["checks"]["writer_admission"]["status"] = "pass"
    forged["receipt_digest"] = sha256_canonical(forged, exclude="receipt_digest")
    (dest / ".git" / "agent-clone-readiness.json").write_text(json.dumps(forged))
    identity["ready"] = True
    identity["readiness_status"] = "ready"
    identity["readiness_receipt_digest"] = forged["receipt_digest"]
    (dest / ".git" / "agent-clone-identity.json").write_text(json.dumps(identity))
    still_rejected = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert still_rejected.returncode == 1
    assert parse_json(still_rejected)["reason"] == "clone_readiness_mismatch"


def test_governance_profile_rejects_missing_required_gitlinks(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "missing-governance"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--profile",
        "governance",
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "profile_gitlink_missing"
    assert not dest.exists()


def test_explicit_submodule_profile_is_custom_degraded_and_not_writer_ready(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "custom-clone"
    created = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--submodule",
        "childmod",
        "--json",
    )
    assert parse_json(created)["profile"] == "custom"
    manifest = write_manifest(tmp_path, dest, "custom-manifest.json")
    receipt_path = tmp_path / "custom-readiness.json"

    readiness = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--output",
        str(receipt_path),
        "--json",
    )

    assert parse_json(readiness)["status"] == "degraded"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["profile"] == "custom"
    assert "writer_admission" in receipt["degraded_checks"]
    rejected = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert rejected.returncode == 1
    assert parse_json(rejected)["reason"] == "clone_readiness_mismatch"


def test_readiness_rejects_profile_origin_drift_even_when_manifest_matches(tmp_path):
    _src, bare = make_governance_profile_source(tmp_path)
    dest = tmp_path / "origin-drift-clone"
    run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--profile",
        "governance",
        "--json",
    )
    bind_provenance(tmp_path, dest, "origin-drift-provenance.json")
    git(dest / "projects" / "ecos", "remote", "set-url", "origin", "https://example.test/wrong.git")
    manifest = write_manifest(tmp_path, dest, "origin-drift-manifest.json")

    proc = run_cli(
        "readiness",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--output",
        str(tmp_path / "origin-drift-readiness.json"),
        "--json",
        env={"OMO_MANAGED_PYTHON": sys.executable},
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "profile_origin_mismatch"


def test_create_refuses_existing_path(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    empty = tmp_path / "empty-dir"
    empty.mkdir()
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(empty),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "destination_collision"
    assert os.listdir(empty) == []

    dangling = tmp_path / "dangling-destination"
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dangling),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "destination_collision"
    assert dangling.is_symlink()


def test_create_with_revision(tmp_path):
    src, _child, bare = make_source(tmp_path)
    (src / "README.md").write_text("v2\n")
    git(src, "add", "README.md")
    git(src, "commit", "-m", "m2")
    git(src, "push", "origin", "main")
    m1_sha = git(src, "rev-parse", "HEAD~1").stdout.strip()

    dest = tmp_path / "clone"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--revision",
        m1_sha,
        "--json",
    )
    assert parse_json(proc)["reason"] == "clone_created"
    assert git(dest, "rev-parse", "HEAD").stdout.strip() == m1_sha
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["frozen_root_sha"] == m1_sha
    assert git(dest, "branch", "--show-current").stdout.strip() == "agent/agent-1--attempt-test"


def test_create_resolves_local_source_revision_before_clone(tmp_path):
    src, _child, bare = make_source(tmp_path)
    updater = tmp_path / "updater"
    git(tmp_path, "clone", str(bare), str(updater))
    (updater / "README.md").write_text("remote-v2\n")
    git(updater, "add", "README.md")
    git(updater, "commit", "-m", "remote-v2")
    git(updater, "push", "origin", "main")
    git(src, "fetch", "origin", "main")
    expected = git(src, "rev-parse", "origin/main").stdout.strip()
    assert git(src, "rev-parse", "main").stdout.strip() != expected

    dest = tmp_path / "clone-from-local-source"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(src),
        "--destination",
        str(dest),
        "--revision",
        "origin/main",
        "--json",
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert git(dest, "rev-parse", "HEAD").stdout.strip() == expected
    assert git(dest, "remote", "get-url", "origin").stdout.strip() == str(bare)
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["frozen_root_sha"] == expected
    assert identity["source_url"] == str(bare)


def test_create_resolves_stale_remote_ref_from_canonical_upstream_without_source_writes(
    tmp_path,
):
    _src, _child, bare = make_source(tmp_path)
    middle = tmp_path / "middle-clone"
    leaf = tmp_path / "leaf-clone"
    updater = tmp_path / "updater"
    git(tmp_path, "clone", str(bare), str(middle))
    git(tmp_path, "clone", str(bare), str(leaf))
    git(leaf, "remote", "set-url", "origin", str(middle))
    stale_leaf_ref = git(leaf, "rev-parse", "origin/main").stdout.strip()
    stale_middle_ref = git(middle, "rev-parse", "origin/main").stdout.strip()

    git(tmp_path, "clone", str(bare), str(updater))
    (updater / "README.md").write_text("remote-v2\n")
    git(updater, "add", "README.md")
    git(updater, "commit", "-m", "remote-v2")
    git(updater, "push", "origin", "main")
    expected = git(updater, "rev-parse", "HEAD").stdout.strip()
    assert expected not in {stale_leaf_ref, stale_middle_ref}

    destination = tmp_path / "canonical-upstream-clone"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(leaf),
        "--destination",
        str(destination),
        "--revision",
        "origin/main",
        "--no-submodules",
        "--json",
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert git(destination, "rev-parse", "HEAD").stdout.strip() == expected
    assert git(destination, "remote", "get-url", "origin").stdout.strip() == str(bare)
    identity = json.loads((destination / ".git" / "agent-clone-identity.json").read_text())
    assert identity["source_url"] == str(bare)
    assert identity["frozen_root_sha"] == expected
    assert git(leaf, "rev-parse", "origin/main").stdout.strip() == stale_leaf_ref
    assert git(middle, "rev-parse", "origin/main").stdout.strip() == stale_middle_ref


def test_create_rejects_local_origin_cycle_before_destination_write(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    left = tmp_path / "left-clone"
    right = tmp_path / "right-clone"
    git(tmp_path, "clone", str(bare), str(left))
    git(tmp_path, "clone", str(bare), str(right))
    git(left, "remote", "set-url", "origin", str(right))
    git(right, "remote", "set-url", "origin", str(left))
    destination = tmp_path / "cycle-destination"

    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(left),
        "--destination",
        str(destination),
        "--revision",
        "origin/main",
        "--no-submodules",
        "--json",
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "origin_cycle"
    assert not destination.exists()


def test_create_resolves_relative_local_origin_against_source_repo(tmp_path):
    src, _child, bare = make_source(tmp_path)
    upstream = tmp_path / "upstream repo.git"
    bare.rename(upstream)
    git(src, "remote", "set-url", "origin", "../upstream repo.git")

    dest = tmp_path / "clone-from-relative-origin"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(src),
        "--destination",
        str(dest),
        "--revision",
        "main",
        "--json",
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert git(dest, "remote", "get-url", "origin").stdout.strip() == str(upstream)
    assert git(dest, "ls-remote", "origin").returncode == 0
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["source_url"] == str(upstream)


def test_atomic_publish_refuses_to_replace_existing_directory(tmp_path):
    tool = load_tool_module()
    staging = tmp_path / "staging"
    destination = tmp_path / "destination"
    staging.mkdir()
    destination.mkdir()
    victim_inode = destination.stat().st_ino

    try:
        tool.atomic_publish_no_replace(str(staging), str(destination))
    except tool.ToolError as exc:
        assert exc.reason == "destination_collision"
    else:
        raise AssertionError("atomic publication replaced an existing destination")

    assert destination.is_dir()
    assert destination.stat().st_ino == victim_inode
    assert staging.is_dir()


def test_create_reports_published_clone_when_staging_cleanup_fails(tmp_path, monkeypatch):
    tool = load_tool_module()
    _src, _child, bare = make_source(tmp_path)
    destination = tmp_path / "published-clone"

    def fail_cleanup(_path):
        raise PermissionError("simulated cleanup failure")

    monkeypatch.setattr(tool.shutil, "rmtree", fail_cleanup)
    args = tool.argparse.Namespace(
        agent_id="agent-1",
        delivery_attempt_id="attempt-001",
        source=str(bare),
        destination=str(destination),
        revision=None,
        no_submodules=True,
    )

    try:
        tool.cmd_create(args)
    except tool.ToolError as exc:
        assert exc.reason == "staging_cleanup_failed"
        assert exc.details["publication_state"] == "published_cleanup_unconfirmed"
        assert exc.details["published_resource"] == str(destination.resolve())
        assert str(destination.resolve()) not in exc.details["residual_resources"]
    else:
        raise AssertionError("cleanup failure was reported as clone success")

    assert destination.is_dir()


def test_create_preserves_cleanup_evidence_for_unexpected_primary_error(tmp_path, monkeypatch):
    tool = load_tool_module()
    _src, _child, bare = make_source(tmp_path)
    destination = tmp_path / "unpublished-clone"

    def fail_identity(_root, _identity):
        raise OSError("simulated identity write failure")

    def fail_cleanup(_path):
        raise PermissionError("simulated cleanup failure")

    monkeypatch.setattr(tool, "write_identity", fail_identity)
    monkeypatch.setattr(tool.shutil, "rmtree", fail_cleanup)
    args = tool.argparse.Namespace(
        agent_id="agent-1",
        delivery_attempt_id="attempt-001",
        source=str(bare),
        destination=str(destination),
        revision=None,
        no_submodules=True,
    )

    try:
        tool.cmd_create(args)
    except tool.ToolError as exc:
        assert exc.reason == "internal_error"
        assert exc.exit_code == tool.EXIT_USAGE
        assert exc.details["cleanup_reason"] == "PermissionError"
        assert len(exc.details["residual_resources"]) == 1
    else:
        raise AssertionError("unexpected error lost its cleanup evidence")

    assert not destination.exists()


def test_create_submodule_failure_does_not_publish_partial_destination(tmp_path):
    src, _child, bare = make_source(tmp_path)
    doomed = tmp_path / "doomed-child"
    doomed.mkdir()
    git(doomed, "init", "-b", "main")
    (doomed / "doomed.txt").write_text("doomed\n")
    git(doomed, "add", "doomed.txt")
    git(doomed, "commit", "-m", "doomed")
    git(
        src,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(doomed),
        "z-doomed",
    )
    git(src, "commit", "-m", "add doomed child")
    git(src, "push", "origin", "main")
    shutil.rmtree(doomed)

    dest = tmp_path / "must-not-be-published"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--json",
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "submodule_init_failed"
    assert not dest.exists()
    assert not list(tmp_path.glob(f".{dest.name}.agent-clone-*"))


def test_create_no_submodules_manifest_uninitialized(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "clone"
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(dest),
        "--no-submodules",
        "--json",
    )
    assert parse_json(proc)["submodules_initialized"] is False
    m = write_manifest(tmp_path, dest, "m.json")
    data = json.loads(m.read_text())
    entry = data["repositories"][0]
    assert entry["initialized"] is False
    assert entry["child_head"] is None
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json")
    assert parse_json(proc)["reason"] == "verified"


def test_invalid_agent_id(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    for bad in ("", "a/b", "..", "has space", "x" * 65):
        proc = run_cli(
            "create",
            "--agent-id",
            bad,
            "--source",
            str(bare),
            "--destination",
            str(tmp_path / "c"),
            "--json",
            check=False,
        )
        assert proc.returncode == 2, bad
        assert parse_json(proc)["reason"] == "agent_id_invalid"


# ---------------------------------------------------------------------------
# manifest + verify
# ---------------------------------------------------------------------------


def test_manifest_deterministic_digest_and_verify(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    m1 = write_manifest(tmp_path, dest, "m1.json")
    m2 = write_manifest(tmp_path, dest, "m2.json")
    assert m1.read_text() == m2.read_text()  # deterministic: no timestamps

    data = json.loads(m1.read_text())
    assert data["schema"] == "agent-clone-manifest/v2"
    assert data["agent_id"] == "agent-1"
    assert data["detached"] is False
    assert len(data["repositories"]) == 1
    entry = data["repositories"][0]
    assert entry["path"] == "childmod"
    assert entry["initialized"] is True
    assert entry["clean"] is True
    assert entry["child_head"] == entry["pinned_sha"]
    assert entry["origin"] is not None
    assert data["manifest_digest"] == sha256_canonical(data, exclude="manifest_digest")

    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m1), "--json")
    assert parse_json(proc)["reason"] == "verified"


def test_manifest_refuses_to_overwrite_existing_output(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    output = tmp_path / "manifest.json"
    output.write_text("sentinel\n")

    proc = run_cli(
        "manifest",
        "--clone",
        str(dest),
        "--output",
        str(output),
        "--json",
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "output_collision"
    assert output.read_text() == "sentinel\n"


def test_dirty_root_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    (dest / "untracked.txt").write_text("x\n")
    proc = run_cli(
        "manifest",
        "--clone",
        str(dest),
        "--output",
        str(tmp_path / "m.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "root_dirty"


def test_dirty_child_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    (dest / "childmod" / "dirty.txt").write_text("x\n")
    proc = run_cli(
        "manifest",
        "--clone",
        str(dest),
        "--output",
        str(tmp_path / "m.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_dirty"


def test_manifest_tamper_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    m = write_manifest(tmp_path, dest, "m.json")

    # plain tamper: digest no longer matches
    tamper_manifest(m, lambda d: d.__setitem__("root_head_sha", "0" * 40), recompute=False)
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "manifest_digest_mismatch"

    # digest-recomputed tamper of root sha: semantic check fires
    m = write_manifest(tmp_path, dest, "semantic-m.json")
    tamper_manifest(m, lambda d: d.__setitem__("root_head_sha", "0" * 40), recompute=True)
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "root_sha_mismatch"


def test_gitlink_drift_rejected(tmp_path):
    _src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    m = write_manifest(tmp_path, dest, "m.json")

    # real drift: move child, commit a new gitlink in the clone (root stays clean)
    (child / "f.txt").write_text("c2\n")
    git(child, "add", "f.txt")
    git(child, "commit", "-m", "c2")
    git(dest / "childmod", "fetch", "origin")
    git(dest / "childmod", "checkout", git(child, "rev-parse", "HEAD").stdout.strip())
    git(dest, "add", "childmod")
    git(dest, "commit", "-m", "gitlink drift")
    # root moved AND gitlink moved: verify must reject (root sha no longer matches)
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1

    # digest-recomputed manifest with a wrong pinned sha: gitlink_drift fires
    m2 = write_manifest(tmp_path, dest, "m2.json")
    tamper_manifest(m2, lambda d: d["repositories"][0].__setitem__("pinned_sha", "0" * 40))
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m2), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "gitlink_drift"


def test_child_head_drift_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    m = write_manifest(tmp_path, dest, "m.json")

    # digest-recomputed manifest with a wrong child_head
    tamper_manifest(m, lambda d: d["repositories"][0].__setitem__("child_head", "0" * 40))
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_head_drift"


def test_origin_drift_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    manifest = write_manifest(tmp_path, dest, "m.json")
    git(dest, "remote", "set-url", "origin", str(tmp_path / "elsewhere.git"))
    proc = run_cli(
        "verify",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "origin_drift"


def test_child_origin_drift_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    manifest = write_manifest(tmp_path, dest, "m.json")
    git(
        dest / "childmod",
        "remote",
        "set-url",
        "origin",
        str(tmp_path / "child-other.git"),
    )
    proc = run_cli(
        "verify",
        "--clone",
        str(dest),
        "--manifest",
        str(manifest),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_origin_drift"


# ---------------------------------------------------------------------------
# changeset
# ---------------------------------------------------------------------------


def _advance_source(src: Path, child: Path) -> str:
    """Advance child to c2 and source to m2; returns the new root commit."""
    (child / "f.txt").write_text("c2\n")
    git(child, "add", "f.txt")
    git(child, "commit", "-m", "c2")
    git(src / "childmod", "fetch", "origin")
    git(src / "childmod", "checkout", git(child, "rev-parse", "HEAD").stdout.strip())
    (src / "README.md").write_text("root v2\n")
    git(src, "add", "README.md", "childmod")
    git(src, "commit", "-m", "m2")
    git(src, "push", "origin", "main")
    return git(src, "rev-parse", "HEAD").stdout.strip()


def _ff_clone(dest: Path) -> None:
    git(dest, "fetch", "origin")
    git(dest, "merge", "--ff-only", "origin/main")
    git(dest, "submodule", "update", "--init", "--recursive")


def test_changeset_no_change_explicit(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(out),
        "--json",
    )
    assert parse_json(proc)["reason"] == "changeset_generated"
    data = json.loads(out.read_text())
    assert data["schema"] == "cross-repo-changeset/v3"
    assert data["no_change"] is True
    assert data["changes"] == []
    assert data["root_base_sha"] == data["root_candidate_sha"]
    assert data["baseline_manifest_digest"] == json.loads(baseline.read_text())["manifest_digest"]


def test_changeset_includes_declared_root_only_file(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md")
    (dest / "README.md").write_text("changed root file\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "change root file")
    output = tmp_path / "changeset.json"

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
    )

    data = json.loads(output.read_text())
    assert data["changes"] == [
        {
            "ancestry_proven": True,
            "base_sha": data["changes"][0]["base_sha"],
            "candidate_sha": data["changes"][0]["candidate_sha"],
            "kind": "root_file",
            "path": "README.md",
        }
    ]
    assert data["claim_verification"]["all_covered"] is True
    assert data["claim_verification"]["violations"] == []


def test_changeset_rejects_unclaimed_root_only_file(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    (dest / "README.md").write_text("changed root file\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "change root file")
    output = tmp_path / "changeset.json"
    authority = tmp_path / "authority"
    write_active_claim(authority, "OTHER.md")

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
        check=False,
    )

    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "claim_scope_violation"
    data = json.loads(output.read_text())
    assert [(change["kind"], change["path"]) for change in data["changes"]] == [
        ("root_file", "README.md"),
    ]
    assert data["claim_verification"]["violations"] == ["README.md"]


def test_changeset_requires_explicit_claims_root(tmp_path):
    tool = load_tool_module()
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    (dest / "README.md").write_text("changed root file\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "change root file")
    output = tmp_path / "changeset.json"
    with pytest.raises(tool.ToolError) as exc:
        tool.cmd_changeset(
            argparse.Namespace(
                clone=str(dest),
                baseline=str(baseline),
                output=str(output),
                verify_claims=True,
            )
        )
    assert exc.value.reason == "claims_root_required"
    assert not output.exists()


def test_changeset_does_not_authorize_clone_local_or_wrong_actor_claim(tmp_path):
    tool = load_tool_module()
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md", actor="different-agent")
    clone = tmp_path / "clone"
    write_active_claim(clone, "README.md")
    result = tool._verify_changeset_claims(
        str(authority), "agent-1", [{"path": "README.md"}]
    )
    assert result["claimed_paths"] == []
    assert result["violations"] == ["README.md"]


def test_claim_glob_does_not_cover_sibling_prefix():
    tool = load_tool_module()
    assert tool._path_covered_by_claim(["docs/**"], "docs/plan.md") is True
    assert tool._path_covered_by_claim(["docs/**"], "docs-archive/plan.md") is False


def test_claim_snapshot_rejects_race_and_symlink_escape(tmp_path, monkeypatch):
    tool = load_tool_module()
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md")
    real_build = tool._build_claim_snapshot
    calls = 0

    def racing_build(root, agent_id):
        nonlocal calls
        result = real_build(root, agent_id)
        calls += 1
        if calls == 2:
            result["runs"][0]["updated_at"] = "raced"
        return result

    monkeypatch.setattr(tool, "_build_claim_snapshot", racing_build)
    with pytest.raises(tool.ToolError) as race:
        tool._verify_changeset_claims(str(authority), "agent-1", [])
    assert race.value.reason == "claims_snapshot_raced"

    outside = tmp_path / "outside.yaml"
    outside.write_text("run_id: escaped\nstatus: active\nclaims: []\n")
    runs = authority / ".omo" / "_delivery" / "agent-workflows" / "runs"
    (runs / "escaped.yaml").symlink_to(outside)
    with pytest.raises(tool.ToolError) as escaped:
        real_build(str(authority), "agent-1")
    assert escaped.value.reason == "claims_run_escape"


def test_verify_changeset_binds_current_clone_baseline_head_paths_and_digest(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md")
    (dest / "README.md").write_text("claimed change\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "claimed change")
    output = tmp_path / "verified-changeset.json"

    generated = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    receipt = json.loads(output.read_text())
    assert receipt["clone_root"] == str(dest.resolve())
    assert receipt["schema"] == "cross-repo-changeset/v3"
    snapshot = receipt["claim_verification"]["snapshot"]
    assert snapshot["claims_root"] == str(authority.resolve())
    assert snapshot["source_root"].endswith("/.omo/_delivery/agent-workflows/runs")
    assert snapshot["runs"][0]["run_actor"] == "human-owner"
    assert snapshot["snapshot_digest"].startswith("sha256:")

    verified = run_cli(
        "verify-changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--changeset",
        str(output),
        "--agent-id",
        "agent-1",
        "--claims-root",
        str(authority),
        "--json",
        check=False,
    )
    assert verified.returncode == 0, verified.stderr
    assert parse_json(verified)["change_id"] == receipt["change_id"]


def test_verify_changeset_rejects_stale_head_and_tampered_changed_paths(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md")
    (dest / "README.md").write_text("claimed change\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "claimed change")
    output = tmp_path / "verified-changeset.json"
    run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
        "--verify-claims",
        "--claims-root",
        str(authority),
    )

    tampered = json.loads(output.read_text())
    tampered["changes"][0]["path"] = "UNCLAIMED.md"
    tampered["change_id"] = sha256_canonical(tampered, exclude="change_id")
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered))
    rejected = run_cli(
        "verify-changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--changeset",
        str(tampered_path),
        "--agent-id",
        "agent-1",
        "--claims-root",
        str(authority),
        "--json",
        check=False,
    )
    assert rejected.returncode == 1

    (dest / "README.md").write_text("newer than receipt\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "stale receipt")
    stale = run_cli(
        "verify-changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--changeset",
        str(output),
        "--agent-id",
        "agent-1",
        "--claims-root",
        str(authority),
        "--json",
        check=False,
    )
    assert stale.returncode == 1


def test_verify_changeset_rejects_claim_snapshot_drift_and_different_root(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    run = write_active_claim(authority, "README.md")
    (dest / "README.md").write_text("claimed change\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "claimed change")
    output = tmp_path / "verified-changeset.json"
    run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(output), "--verify-claims", "--claims-root", str(authority),
    )

    other = tmp_path / "other-authority"
    write_active_claim(other, "README.md")
    forged = run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(tmp_path / "forged.json"), "--verify-claims",
        "--claims-root", str(other), "--json", check=False,
        trusted_root=authority,
    )
    assert parse_json(forged)["reason"] == "claims_authority_mismatch"
    wrong_root = run_cli(
        "verify-changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--changeset", str(output), "--agent-id", "agent-1",
        "--claims-root", str(other), "--json", check=False,
    )
    assert parse_json(wrong_root)["reason"] == "claims_root_mismatch"

    run.write_text(run.read_text().replace("2026-08-21T00:00:00Z", "2026-08-21T00:00:02Z"))
    drift = run_cli(
        "verify-changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--changeset", str(output), "--agent-id", "agent-1",
        "--claims-root", str(authority), "--json", check=False,
    )
    assert parse_json(drift)["reason"] == "changeset_stale"

    run.write_text(run.read_text().replace("2026-08-21T00:00:02Z", "2026-08-21T00:00:00Z"))
    run.write_text(run.read_text().replace("      - README.md", "      - OTHER.md"))
    claim_drift = run_cli(
        "verify-changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--changeset", str(output), "--agent-id", "agent-1",
        "--claims-root", str(authority), "--json", check=False,
    )
    assert parse_json(claim_drift)["reason"] in {"claim_scope_violation", "changeset_stale"}

    run.write_text(run.read_text().replace("      - OTHER.md", "      - README.md"))
    write_active_claim(authority, "OTHER.md", name="additional")
    added = run_cli(
        "verify-changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--changeset", str(output), "--agent-id", "agent-1",
        "--claims-root", str(authority), "--json", check=False,
    )
    assert parse_json(added)["reason"] == "changeset_stale"


def test_changeset_rejects_locally_rebased_authority_policy(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    forged_authority = tmp_path / "forged-authority"
    policy = dest / ".omo" / "_truth" / "registry" / "swarm-coordination.yaml"
    policy.write_text(
        "topology_migration:\n"
        f"  integration_root: '{forged_authority.resolve()}'\n"
    )
    git(dest, "add", str(policy.relative_to(dest)))
    git(dest, "commit", "-m", "forge local authority policy")
    identity_path = dest / ".git" / "agent-clone-identity.json"
    identity = json.loads(identity_path.read_text())
    identity["source_url"] = str((tmp_path / "attacker.git").resolve())
    identity_path.write_text(json.dumps(identity))
    git(dest, "remote", "set-url", "origin", identity["source_url"])
    baseline = write_manifest(tmp_path, dest, "forged-baseline.json")
    write_active_claim(forged_authority, "README.md")
    (dest / "README.md").write_text("claimed change\n")
    git(dest, "add", "README.md")
    git(dest, "commit", "-m", "claimed change")

    rejected = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "forged-changeset.json"),
        "--verify-claims",
        "--claims-root",
        str(forged_authority),
        "--json",
        trusted_root=tmp_path / "authority",
        check=False,
    )

    assert parse_json(rejected)["reason"] == "claims_authority_mismatch"


def test_changeset_fast_forward_accepted(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md", "childmod")
    _new_root = _advance_source(src, child)
    _ff_clone(dest)

    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(out),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
    )
    assert parse_json(proc)["reason"] == "changeset_generated"
    data = json.loads(out.read_text())
    assert data["no_change"] is False
    assert {(change["kind"], change["path"]) for change in data["changes"]} == {
        ("root_file", "README.md"),
        ("gitlink", "childmod"),
    }
    assert data["claim_verification"]["checked"] == ["README.md", "childmod"]
    assert data["claim_verification"]["all_covered"] is True
    assert all(change["ancestry_proven"] is True for change in data["changes"])
    assert data["root_candidate_sha"] == git(dest, "rev-parse", "HEAD").stdout.strip()


def test_changeset_checks_deleted_and_renamed_root_paths(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare, no_submodules=True)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    authority = tmp_path / "authority"
    write_active_claim(authority, "README.md", "renamed.md")
    git(dest, "mv", "README.md", "renamed.md")
    git(dest, "commit", "-m", "rename root file")
    output = tmp_path / "changeset.json"

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(output),
        "--verify-claims",
        "--claims-root",
        str(authority),
        "--json",
    )

    assert proc.returncode == 0
    data = json.loads(output.read_text())
    assert [(change["kind"], change["path"]) for change in data["changes"]] == [
        ("root_file", "README.md"),
        ("root_file", "renamed.md"),
    ]
    assert data["claim_verification"]["checked"] == ["README.md", "renamed.md"]


def test_changeset_rejects_child_head_gitlink_mismatch(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    _advance_source(src, child)
    _ff_clone(dest)
    git(dest / "childmod", "checkout", "HEAD~1")
    git(dest, "config", "submodule.childmod.ignore", "all")

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_head_gitlink_mismatch"


def test_changeset_rewind_rejected(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    _new_root = _advance_source(src, child)
    _ff_clone(dest)
    baseline2 = write_manifest(tmp_path, dest, "baseline2.json")

    git(dest, "checkout", git(dest, "rev-parse", "HEAD~1").stdout.strip())
    git(dest, "submodule", "update", "--init", "--recursive")
    rewound_sha = git(dest, "rev-parse", "HEAD").stdout.strip()
    assert rewound_sha != json.loads(baseline2.read_text())["root_head_sha"]

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline2),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "root_rewind_or_diverged"


def test_changeset_divergence_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")

    # unrelated clean repository as candidate: baseline root is not an ancestor
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-b", "main")
    (other / "x.txt").write_text("x\n")
    git(other, "add", "x.txt")
    git(other, "commit", "-m", "x")

    proc = run_cli(
        "changeset",
        "--clone",
        str(other),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "root_rewind_or_diverged"


def test_changeset_child_rewind_rejected(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    _new_root = _advance_source(src, child)
    _ff_clone(dest)
    baseline2 = write_manifest(tmp_path, dest, "baseline2.json")

    # rewind child in the clone and commit the gitlink change (root stays clean)
    c1_sha = git(src / "childmod", "rev-parse", "HEAD~1").stdout.strip()
    git(dest / "childmod", "checkout", c1_sha)
    git(dest, "add", "childmod")
    git(dest, "commit", "-m", "child rewind")

    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline2),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_rewind_or_diverged"


def test_changeset_dirty_candidate_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    (dest / "untracked.txt").write_text("x\n")
    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "candidate_dirty"


def test_changeset_baseline_digest_validation(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    tamper_manifest(baseline, lambda d: d.__setitem__("root_head_sha", "0" * 40), recompute=False)
    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "baseline_digest_mismatch"


# ---------------------------------------------------------------------------
# guard
# ---------------------------------------------------------------------------


def test_guard_states(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    integration = tmp_path / "integration-workspace"
    integration.mkdir()
    dest = create_clone(tmp_path, bare)

    # no AGENT_ID: human operation allowed even on the integration root
    proc = run_cli(
        "guard",
        "--workspace",
        str(integration),
        "--integration-root",
        str(integration),
        "--json",
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "human"

    # AGENT_ID on the integration root: denied
    proc = run_cli(
        "guard",
        "--workspace",
        str(integration),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"

    # matching clone identity: verified clone
    proc = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "agent-1"},
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "verified_clone"

    # mismatched clone identity: denied
    proc = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "other-agent"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "clone_identity_mismatch"

    # git repo without identity: legacy isolated worktree, allowed but distinct
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    git(legacy, "init", "-b", "main")
    (legacy / "f.txt").write_text("x\n")
    git(legacy, "add", "f.txt")
    git(legacy, "commit", "-m", "x")
    proc = run_cli(
        "guard",
        "--workspace",
        str(legacy),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "agent-1"},
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "legacy_isolated_worktree"


def test_guard_require_clone_rejects_legacy_worktree(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    integration = tmp_path / "integration-workspace"
    integration.mkdir()
    dest = create_clone(tmp_path, bare)

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    git(legacy, "init", "-b", "main")
    (legacy / "f.txt").write_text("x\n")
    git(legacy, "add", "f.txt")
    git(legacy, "commit", "-m", "x")

    proc = run_cli(
        "guard",
        "--workspace",
        str(legacy),
        "--integration-root",
        str(integration),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "clone_identity_required"

    proc = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(integration),
        "--require-clone",
        "--json",
        env={"AGENT_ID": "agent-1"},
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "verified_clone"

    proc = run_cli(
        "guard",
        "--workspace",
        str(integration),
        "--integration-root",
        str(integration),
        "--require-clone",
        "--json",
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "human"


def test_tracked_pre_commit_requires_clone_for_agent_identity(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    git(legacy, "init", "-b", "main")
    (legacy / "f.txt").write_text("x\n")
    git(legacy, "add", "f.txt")
    git(legacy, "commit", "-m", "x")

    tool = legacy / "bin" / "gac" / "agent-clone.py"
    tool.parent.mkdir(parents=True)
    shutil.copy2(TOOL, tool)
    shutil.copy2(MANAGED_PYTHON, tool.parent / "managed-python")
    hook = legacy / ".githooks" / "pre-commit"
    hook.parent.mkdir()
    shutil.copy2(PRE_COMMIT, hook)

    env = os.environ.copy()
    env.update(_GIT_ENV)
    env.update({"AGENT_ID": "agent-1", "HOME": str(tmp_path / "alternate-home")})
    proc = subprocess.run(
        ["bash", str(hook)],
        cwd=legacy,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 1
    assert "clone_identity_required" in proc.stderr

    env.pop("AGENT_ID")
    proc = subprocess.run(
        ["bash", str(hook)],
        cwd=legacy,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    assert "human_operation_allowed" in proc.stderr


def test_tracked_pre_commit_rejects_real_linked_worktree_with_alternate_home(tmp_path):
    common = tmp_path / "common"
    common.mkdir()
    git(common, "init", "-b", "main")
    tool = common / "bin" / "gac" / "agent-clone.py"
    tool.parent.mkdir(parents=True)
    shutil.copy2(TOOL, tool)
    shutil.copy2(MANAGED_PYTHON, tool.parent / "managed-python")
    hook = common / ".githooks" / "pre-commit"
    hook.parent.mkdir()
    shutil.copy2(PRE_COMMIT, hook)
    git(common, "add", ".")
    git(common, "commit", "-m", "base")
    linked = tmp_path / "linked"
    git(common, "worktree", "add", "-b", "work/linked", str(linked))

    env = os.environ.copy()
    env.update(_GIT_ENV)
    env.update({"AGENT_ID": "agent-1", "HOME": str(tmp_path / "alternate-home")})
    proc = subprocess.run(
        ["bash", str(linked / ".githooks" / "pre-commit")],
        cwd=linked,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 1
    assert "clone_identity_required" in proc.stderr


# ---------------------------------------------------------------------------
# fail-closed create paths + portability
# ---------------------------------------------------------------------------


def test_destination_collision_and_clone_failure(tmp_path):
    _src, _child, bare = make_source(tmp_path)

    # non-empty destination: refused, and never deleted or reset
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("x\n")
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(bare),
        "--destination",
        str(occupied),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "destination_collision"
    assert (occupied / "keep.txt").read_text() == "x\n"

    # clone failure (missing source): fail closed, destination left absent
    proc = run_cli(
        "create",
        "--agent-id",
        "agent-1",
        "--source",
        str(tmp_path / "missing"),
        "--destination",
        str(tmp_path / "bad"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "delivery_attempt_lookup_failed"
    assert not (tmp_path / "bad").exists()


def test_paths_with_spaces(tmp_path):
    base = tmp_path / "sp ace base"
    _src, _child, bare = make_source(base, submodule_name="child mod")
    nested = tmp_path / "nested"
    nested.mkdir()
    dest = create_clone(nested, bare, name="cl one")

    m = write_manifest(base, dest, "ma nifest.json")
    data = json.loads(m.read_text())
    assert data["repositories"][0]["path"] == "child mod"
    assert data["repositories"][0]["initialized"] is True

    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json")
    assert parse_json(proc)["reason"] == "verified"

    out = base / "cs out.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(m),
        "--output",
        str(out),
        "--json",
    )
    assert parse_json(proc)["reason"] == "changeset_generated"


# ---------------------------------------------------------------------------
# hook activation + ready identity
# ---------------------------------------------------------------------------


def test_hooks_activation_and_ready_identity(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare)
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["ready"] is True
    assert git(dest, "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"
    assert (dest / ".githooks" / "pre-commit").exists()

    m = write_manifest(tmp_path, dest, "m.json")
    assert json.loads(m.read_text())["hooks_path"] == ".githooks"
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json")
    assert parse_json(proc)["reason"] == "verified"


def test_no_hooks_when_absent(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=False)
    dest = create_clone(tmp_path, bare)
    m = write_manifest(tmp_path, dest, "m.json")
    assert json.loads(m.read_text())["hooks_path"] is None
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json")
    assert parse_json(proc)["reason"] == "verified"


def test_hooks_path_drift_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path, with_hooks=True)
    dest = create_clone(tmp_path, bare)
    m = write_manifest(tmp_path, dest, "m.json")
    git(dest, "config", "core.hooksPath", "wrong-hooks")
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "hooks_path_drift"

    proc = run_cli(
        "guard",
        "--workspace",
        str(dest),
        "--integration-root",
        str(tmp_path / "integration"),
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "clone_identity_mismatch"


def test_identity_not_ready_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    ident_file = dest / ".git" / "agent-clone-identity.json"

    identity = json.loads(ident_file.read_text())
    identity["ready"] = False
    ident_file.write_text(json.dumps(identity, indent=2, sort_keys=True))
    proc = run_cli(
        "manifest",
        "--clone",
        str(dest),
        "--output",
        str(tmp_path / "m.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "identity_not_ready"

    identity["ready"] = True
    ident_file.write_text(json.dumps(identity, indent=2, sort_keys=True))
    m = write_manifest(tmp_path, dest, "m.json")
    identity["ready"] = False
    ident_file.write_text(json.dumps(identity, indent=2, sort_keys=True))
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(m), "--json", check=False)
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "identity_mismatch"


# ---------------------------------------------------------------------------
# changeset fail-closed child paths + determinism
# ---------------------------------------------------------------------------


def test_changeset_uninitialized_child_rejected(tmp_path):
    src, child, bare = make_source(tmp_path)
    clone_a = create_clone(tmp_path, bare, name="clone-a")
    baseline = write_manifest(tmp_path, clone_a, "baseline.json")
    _advance_source(src, child)

    clone_b = create_clone(tmp_path, bare, name="clone-b", no_submodules=True)
    git(clone_b, "fetch", "origin")
    git(clone_b, "merge", "--ff-only", "origin/main")
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone_b),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_uninitialized"


def test_changeset_unavailable_baseline_child_object_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    clone_a = create_clone(tmp_path, bare, name="clone-a")
    baseline = write_manifest(tmp_path, clone_a, "baseline.json")

    child_repo = clone_a / "childmod"
    git(child_repo, "checkout", "--orphan", "x")
    git(child_repo, "rm", "-rf", ".")
    (child_repo / "f.txt").write_text("x\n")
    git(child_repo, "add", "f.txt")
    git(child_repo, "commit", "-m", "x")
    git(clone_a, "add", "childmod")
    git(clone_a, "commit", "-m", "m2")
    git(child_repo, "reflog", "expire", "--expire=now", "--all")
    git(child_repo, "gc", "--prune=now", "--quiet")

    proc = run_cli(
        "changeset",
        "--clone",
        str(clone_a),
        "--baseline",
        str(baseline),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_rewind_or_diverged"


def test_changeset_change_id_deterministic(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    out1 = tmp_path / "cs1.json"
    out2 = tmp_path / "cs2.json"
    run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(out1),
    )
    run_cli(
        "changeset",
        "--clone",
        str(dest),
        "--baseline",
        str(baseline),
        "--output",
        str(out2),
    )
    assert json.loads(out1.read_text())["change_id"] == json.loads(out2.read_text())["change_id"]


# ---------------------------------------------------------------------------
# guard containment (nested + symlink alias)
# ---------------------------------------------------------------------------


def test_guard_nested_and_symlink_denied(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    integration = tmp_path / "integration-workspace"
    integration.mkdir()
    nested = integration / "nested"
    nested.mkdir()
    create_clone(nested, bare, name="cl")

    proc = run_cli(
        "guard",
        "--workspace",
        str(nested / "cl"),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"

    link = tmp_path / "ws-link"
    os.symlink(integration, link)
    proc = run_cli(
        "guard",
        "--workspace",
        str(link),
        "--integration-root",
        str(integration),
        "--json",
        env={"AGENT_ID": "agent-1"},
        check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"
