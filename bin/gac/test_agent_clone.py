#!/usr/bin/env python3
"""test_agent_clone.py - D1 pilot contract tests for bin/gac/agent-clone.py.

BET-Y1Q1-T1-05 D1 pilot: Python 3 stdlib-only CLI with subcommands
create / manifest / verify / changeset / verify-changeset / guard.

Every test builds real temporary git repositories (no mocks, no network)
and drives the CLI as a subprocess, asserting the binding contract:

* every subcommand supports --json and prints one JSON document to stdout
  with structured ``ok`` / ``reason`` fields (+ paths / digests);
* exit 0 = success, 1 = policy/verification failure, 2 = usage error;
* clone / manifest / changeset / guard semantics from the D1 contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

AGENT_CLONE = Path(__file__).with_name("agent-clone.py")


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_digest(obj: dict, exclude_field: str | None = None) -> str:
    if exclude_field is not None:
        obj = {k: v for k, v in obj.items() if k != exclude_field}
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def git(*args: str, cwd: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def run_cli(*argv: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(AGENT_CLONE), *argv],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def stdout_json(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


@pytest.fixture(autouse=True)
def hermetic_agent_env(monkeypatch):
    """Tests control AGENT_ID explicitly; never inherit the ambient one."""
    monkeypatch.delenv("AGENT_ID", raising=False)


@pytest.fixture()
def source_repo(tmp_path: Path) -> Path:
    """Minimal source repo: one commit on main."""
    repo = tmp_path / "source"
    repo.mkdir()
    assert git("init", "-b", "main", cwd=repo).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=repo).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=repo).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=repo).returncode == 0
    (repo / "a.txt").write_text("v1\n", encoding="utf-8")
    assert git("add", "a.txt", cwd=repo).returncode == 0
    assert git("commit", "-m", "initial", cwd=repo).returncode == 0
    return repo


@pytest.fixture()
def hooked_source_repo(tmp_path: Path) -> Path:
    """Source repo carrying .githooks/pre-commit so clones activate hooks."""
    repo = tmp_path / "hooked-source"
    repo.mkdir()
    assert git("init", "-b", "main", cwd=repo).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=repo).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=repo).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=repo).returncode == 0
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (repo / "a.txt").write_text("v1\n", encoding="utf-8")
    assert git("add", "a.txt", ".githooks/pre-commit", cwd=repo).returncode == 0
    assert git("commit", "-m", "initial with hooks", cwd=repo).returncode == 0
    return repo


def make_clone(
    source: Path,
    dest: Path,
    agent_id: str = "tester1",
    attempt_id: str = "att1",
    extra_args: tuple = (),
) -> dict:
    proc = run_cli(
        "create",
        "--agent-id",
        agent_id,
        "--delivery-attempt-id",
        attempt_id,
        "--source",
        str(source),
        "--destination",
        str(dest),
        "--no-submodules",
        "--json",
        *extra_args,
    )
    assert proc.returncode == 0, proc.stderr
    return stdout_json(proc)


def commit_in_clone(clone: Path, filename: str, content: str, message: str) -> str:
    assert git("config", "user.name", "D1 Tester", cwd=clone).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=clone).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=clone).returncode == 0
    (clone / filename).write_text(content, encoding="utf-8")
    assert git("add", filename, cwd=clone).returncode == 0
    assert git("commit", "-m", message, cwd=clone).returncode == 0
    return git("rev-parse", "HEAD", cwd=clone).stdout.strip()


def make_manifest(clone: Path, output: Path) -> dict:
    proc = run_cli("manifest", "--clone", str(clone), "--output", str(output), "--json")
    assert proc.returncode == 0, proc.stderr
    return stdout_json(proc)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_happy_path_json_shape(tmp_path: Path, source_repo: Path):
    dest = tmp_path / "clone"
    result = make_clone(source_repo, dest)
    assert result["ok"] is True
    assert result["reason"] == "clone_created"
    assert result["agent_id"] == "tester1"
    assert result["clone_root"] == os.path.realpath(dest)
    assert result["working_branch"] == "agent/tester1--att1"
    assert result["actor_id"] == "tester1"
    assert result["delivery_attempt_id"] == "att1"
    source_head = git("rev-parse", "HEAD", cwd=source_repo).stdout.strip()
    assert result["frozen_root_sha"] == source_head
    assert Path(result["identity_file"]).is_file()
    branch = git("symbolic-ref", "--short", "HEAD", cwd=dest).stdout.strip()
    assert branch == "agent/tester1--att1"
    # Source repository is never mutated by create.
    assert git("rev-parse", "HEAD", cwd=source_repo).stdout.strip() == source_head
    assert git("status", "--porcelain", cwd=source_repo).stdout.strip() == ""


def test_create_invalid_agent_id_is_usage_error(tmp_path: Path, source_repo: Path):
    proc = run_cli(
        "create",
        "--agent-id",
        "bad id!",
        "--delivery-attempt-id",
        "att1",
        "--source",
        str(source_repo),
        "--destination",
        str(tmp_path / "clone"),
        "--json",
    )
    assert proc.returncode == 2
    assert stdout_json(proc)["reason"] == "agent_id_invalid"


def test_create_missing_attempt_id_is_usage_error(tmp_path: Path, source_repo: Path):
    proc = run_cli(
        "create",
        "--agent-id",
        "tester1",
        "--source",
        str(source_repo),
        "--destination",
        str(tmp_path / "clone"),
        "--json",
    )
    assert proc.returncode == 2  # argparse: required flag absent


def test_create_destination_collision(tmp_path: Path, source_repo: Path):
    dest = tmp_path / "clone"
    dest.mkdir()
    proc = run_cli(
        "create",
        "--agent-id",
        "tester1",
        "--delivery-attempt-id",
        "att1",
        "--source",
        str(source_repo),
        "--destination",
        str(dest),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "destination_collision"


def test_create_unknown_submodule(tmp_path: Path, source_repo: Path):
    proc = run_cli(
        "create",
        "--agent-id",
        "tester1",
        "--delivery-attempt-id",
        "att1",
        "--source",
        str(source_repo),
        "--destination",
        str(tmp_path / "clone"),
        "--submodule",
        "nope",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "submodule_unknown"


def test_create_unknown_command_is_usage_error():
    proc = run_cli("frobnicate", "--json")
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# manifest + verify
# ---------------------------------------------------------------------------


def test_manifest_digest_self_consistent(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    result = make_manifest(clone, manifest_path)
    assert result["ok"] is True
    assert result["reason"] == "manifest_generated"
    assert result["manifest_digest"]
    assert result["root_head_sha"]
    with open(manifest_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["manifest_digest"] == canonical_digest(stored, exclude_field="manifest_digest")


def test_manifest_output_collision(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    make_manifest(clone, manifest_path)
    proc = run_cli(
        "manifest", "--clone", str(clone), "--output", str(manifest_path), "--json"
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "output_collision"


def test_manifest_without_identity(tmp_path: Path, source_repo: Path):
    proc = run_cli(
        "manifest",
        "--clone",
        str(source_repo),
        "--output",
        str(tmp_path / "m.json"),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "identity_missing"


def test_verify_ok(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    make_manifest(clone, manifest_path)
    proc = run_cli("verify", "--clone", str(clone), "--manifest", str(manifest_path), "--json")
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["reason"] == "verified"


def test_verify_digest_tamper(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    make_manifest(clone, manifest_path)
    with open(manifest_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    stored["root_head_sha"] = "0" * 40
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(stored, fh, indent=2, sort_keys=True)
    proc = run_cli("verify", "--clone", str(clone), "--manifest", str(manifest_path), "--json")
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "manifest_digest_mismatch"


def test_verify_dirty_root(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    make_manifest(clone, manifest_path)
    (clone / "a.txt").write_text("dirty\n", encoding="utf-8")
    proc = run_cli("verify", "--clone", str(clone), "--manifest", str(manifest_path), "--json")
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "root_dirty"


def test_verify_unreadable_manifest(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    proc = run_cli(
        "verify",
        "--clone",
        str(clone),
        "--manifest",
        str(tmp_path / "missing.json"),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "manifest_unreadable"


# ---------------------------------------------------------------------------
# changeset + verify-changeset
# ---------------------------------------------------------------------------


def test_changeset_enumerates_root_file_change(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    baseline = make_manifest(clone, baseline_path)
    new_head = commit_in_clone(clone, "b.txt", "hello\n", "add b")
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["reason"] == "changeset_generated"
    assert result["changes_count"] == 1
    assert result["no_change"] is False
    assert result["change_id"]
    with open(out, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["root_base_sha"] == baseline["root_head_sha"]
    assert stored["root_candidate_sha"] == new_head
    assert len(stored["changes"]) == 1
    change = stored["changes"][0]
    assert change["kind"] == "root_file"
    assert change["path"] == "b.txt"
    assert change["ancestry_proven"] is True
    # change_id is a digest over the changeset minus change_id and the
    # timestamped shadow projection sibling.
    recompute = {k: v for k, v in stored.items() if k not in {"change_id", "claims_authority_shadow"}}
    assert stored["change_id"] == canonical_digest(recompute, exclude_field="change_id")


def test_changeset_no_change(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["no_change"] is True
    assert result["changes_count"] == 0


def test_changeset_dirty_candidate(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    (clone / "a.txt").write_text("dirty\n", encoding="utf-8")
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "candidate_dirty"


def test_changeset_rewind_or_diverged(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    first_head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    commit_in_clone(clone, "b.txt", "hello\n", "add b")
    new_manifest = tmp_path / "new.json"
    make_manifest(clone, new_manifest)
    assert git("checkout", first_head, cwd=clone).returncode == 0
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(new_manifest),
        "--output",
        str(tmp_path / "cs.json"),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "root_rewind_or_diverged"


def test_changeset_verify_claims_requires_claims_root(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(tmp_path / "cs.json"),
        "--verify-claims",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "claims_root_required"


def _plain_changeset(tmp_path: Path, source_repo: Path) -> Path:
    """A schema-v3 changeset without claim verification (negative-test input)."""
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    commit_in_clone(clone, "b.txt", "hello\n", "add b")
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    return out


def test_verify_changeset_unreadable(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--changeset",
        str(tmp_path / "missing.json"),
        "--agent-id",
        "tester1",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "changeset_unreadable"


def test_verify_changeset_schema_mismatch(tmp_path: Path, source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    manifest_path = tmp_path / "m.json"
    make_manifest(clone, manifest_path)
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(manifest_path),
        "--changeset",
        str(manifest_path),  # a manifest is not a changeset
        "--agent-id",
        "tester1",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "changeset_schema_mismatch"


def test_verify_changeset_digest_mismatch(tmp_path: Path, source_repo: Path):
    changeset_path = _plain_changeset(tmp_path, source_repo)
    with open(changeset_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    stored["changes"].append(
        {"kind": "root_file", "path": "evil.txt", "base_sha": None,
         "candidate_sha": "0" * 40, "ancestry_proven": False}
    )
    with open(changeset_path, "w", encoding="utf-8") as fh:
        json.dump(stored, fh, indent=2, sort_keys=True)
    clone = tmp_path / "clone"
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(tmp_path / "base.json"),
        "--changeset",
        str(changeset_path),
        "--agent-id",
        "tester1",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "changeset_digest_mismatch"


def test_verify_changeset_claims_unverified(tmp_path: Path, source_repo: Path):
    changeset_path = _plain_changeset(tmp_path, source_repo)
    clone = tmp_path / "clone"
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(tmp_path / "base.json"),
        "--changeset",
        str(changeset_path),
        "--agent-id",
        "tester1",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "changeset_claims_unverified"


# ---------------------------------------------------------------------------
# verify-changeset POSITIVE path (hermetic --verify-claims)
# ---------------------------------------------------------------------------


def _make_hermetic_claims_authority(
    tmp_path: Path,
    agent_id: str = "tester1",
    claimed_paths: tuple = ("b.txt",),
) -> Path:
    """Build a self-contained claims authority: local bare remote + work repo.

    Hermetic by construction: origin is a local path (``git ls-remote`` never
    leaves the disk), the policy file binds ``integration_root`` to the repo
    itself, and run files are JSON-compatible ``*.yaml`` so both PyYAML and
    the stdlib-only fallback parse them.  Never touches OS-account paths.
    """
    origin = tmp_path / "claims-origin.git"
    assert git("init", "--bare", str(origin), cwd=tmp_path).returncode == 0
    auth = tmp_path / "authority"
    auth.mkdir()
    assert git("init", "-b", "main", cwd=auth).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=auth).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=auth).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=auth).returncode == 0
    (auth / "a.txt").write_text("v1\n", encoding="utf-8")
    policy_dir = auth / ".omo" / "_truth" / "registry"
    policy_dir.mkdir(parents=True)
    (policy_dir / "swarm-coordination.yaml").write_text(
        f"topology_migration:\n  integration_root: \"{os.path.realpath(auth)}\"\n",
        encoding="utf-8",
    )
    assert git("add", "a.txt", ".omo/_truth/registry/swarm-coordination.yaml", cwd=auth).returncode == 0
    assert git("commit", "-m", "authority with policy", cwd=auth).returncode == 0
    assert git("remote", "add", "origin", str(origin), cwd=auth).returncode == 0
    assert git("push", "-u", "origin", "main", cwd=auth).returncode == 0
    runs = auth / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True)
    run_doc = {
        "actor": "someone-else",
        "claims": [
            {
                "actor": agent_id,
                "claimed_at": "2026-09-17T00:00:00Z",
                "paths": list(claimed_paths),
            }
        ],
        "run_id": "run-1",
        "status": "active",
        "updated_at": "2026-09-17T00:00:00Z",
    }
    (runs / "run-1.yaml").write_text(
        json.dumps(run_doc, sort_keys=True), encoding="utf-8"
    )
    return auth


def _make_claims_changeset(
    tmp_path: Path,
    agent_id: str = "tester1",
    env_extra: dict | None = None,
) -> tuple[Path, Path, Path]:
    """Clone the hermetic authority, commit b.txt, return (clone, baseline, changeset)."""
    auth = _make_hermetic_claims_authority(tmp_path, agent_id=agent_id)
    clone = tmp_path / "clone"
    make_clone(auth, clone, agent_id=agent_id)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    commit_in_clone(clone, "b.txt", "hello\n", "add b")
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--verify-claims",
        "--claims-root",
        str(auth),
        "--json",
        env_extra=env_extra,
    )
    assert proc.returncode == 0, proc.stderr
    return clone, baseline_path, out


def _yaml_blocker_env(tmp_path: Path) -> dict:
    """Env that makes ``import yaml`` fail in the CLI subprocess (stdlib-only proof)."""
    blocker = tmp_path / "no-third-party"
    blocker.mkdir(exist_ok=True)
    (blocker / "yaml.py").write_text(
        'raise ImportError("blocked for hermetic stdlib-only test")\n',
        encoding="utf-8",
    )
    path = str(blocker)
    if os.environ.get("PYTHONPATH"):
        path += os.pathsep + os.environ["PYTHONPATH"]
    return {"PYTHONPATH": path}


def test_verify_changeset_happy_path_with_verify_claims(tmp_path: Path):
    clone, baseline_path, changeset_path = _make_claims_changeset(tmp_path)
    with open(changeset_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["schema"] in {"cross-repo-changeset/v2", "cross-repo-changeset/v3"}
    verification = stored["claim_verification"]
    assert verification["enabled"] is True
    assert verification["all_covered"] is True
    assert verification["violations"] == []
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--changeset",
        str(changeset_path),
        "--agent-id",
        "tester1",
        "--claims-root",
        str(os.path.realpath(tmp_path / "authority")),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["reason"] == "changeset_verified"
    assert result["change_id"] == stored["change_id"]
    assert result["changed_paths"] == ["b.txt"]
    assert result["root_head_sha"] == stored["root_candidate_sha"]


def test_changeset_claims_digest_self_consistent(tmp_path: Path):
    _, _, changeset_path = _make_claims_changeset(tmp_path)
    with open(changeset_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    # change_id covers every authority byte except itself and the timestamped
    # shadow projection sibling.
    recompute = {
        key: value
        for key, value in stored.items()
        if key not in {"change_id", "claims_authority_shadow"}
    }
    assert stored["change_id"] == canonical_digest(recompute, exclude_field="change_id")
    snapshot = stored["claim_verification"]["snapshot"]
    assert snapshot["claims_root"] == os.path.realpath(tmp_path / "authority")
    assert "b.txt" in snapshot["claimed_paths"]


def test_verify_changeset_claims_root_required(tmp_path: Path):
    clone, baseline_path, changeset_path = _make_claims_changeset(tmp_path)
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--changeset",
        str(changeset_path),
        "--agent-id",
        "tester1",
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "claims_root_required"


def test_verify_changeset_happy_path_without_pyyaml(tmp_path: Path):
    """Same positive path with ``import yaml`` blocked: stdlib-only fallback."""
    env = _yaml_blocker_env(tmp_path)
    clone, baseline_path, changeset_path = _make_claims_changeset(
        tmp_path, env_extra=env
    )
    proc = run_cli(
        "verify-changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--changeset",
        str(changeset_path),
        "--agent-id",
        "tester1",
        "--claims-root",
        str(os.path.realpath(tmp_path / "authority")),
        "--json",
        env_extra=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc)["reason"] == "changeset_verified"


# ---------------------------------------------------------------------------
# guard
# ---------------------------------------------------------------------------


def test_guard_human_operation_allowed(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    ir = tmp_path / "integration"
    ir.mkdir()
    proc = run_cli(
        "guard", "--workspace", str(ws), "--integration-root", str(ir), "--json"
    )
    assert proc.returncode == 0
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["state"] == "human"
    assert result["reason"] == "human_operation_allowed"


def test_guard_agent_on_integration_root(tmp_path: Path):
    ir = tmp_path / "integration"
    ir.mkdir()
    ws = ir / "nested"
    ws.mkdir()
    proc = run_cli(
        "guard",
        "--workspace",
        str(ws),
        "--integration-root",
        str(ir),
        "--json",
        env_extra={"AGENT_ID": "tester1"},
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "agent_on_integration_root"


def test_guard_require_clone_without_identity(tmp_path: Path, source_repo: Path):
    ir = tmp_path / "integration"
    ir.mkdir()
    proc = run_cli(
        "guard",
        "--workspace",
        str(source_repo),
        "--integration-root",
        str(ir),
        "--require-clone",
        "--json",
        env_extra={"AGENT_ID": "tester1"},
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "clone_identity_required"


def test_guard_agent_legacy_worktree_allowed(tmp_path: Path, source_repo: Path):
    ir = tmp_path / "integration"
    ir.mkdir()
    proc = run_cli(
        "guard",
        "--workspace",
        str(source_repo),
        "--integration-root",
        str(ir),
        "--json",
        env_extra={"AGENT_ID": "tester1"},
    )
    assert proc.returncode == 0
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["reason"] == "legacy_isolated_worktree_allowed"


def test_guard_verified_clone(tmp_path: Path, hooked_source_repo: Path):
    clone = tmp_path / "clone"
    make_clone(hooked_source_repo, clone)
    ir = tmp_path / "integration"
    ir.mkdir()
    proc = run_cli(
        "guard",
        "--workspace",
        str(clone),
        "--integration-root",
        str(ir),
        "--require-clone",
        "--json",
        env_extra={"AGENT_ID": "tester1"},
    )
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["ok"] is True
    assert result["state"] == "verified_clone"
    assert result["reason"] == "clone_identity_matched"


def test_guard_clone_identity_mismatch_without_hooks(tmp_path: Path, source_repo: Path):
    """An agent clone lacking hook activation is not admitted as verified."""
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    ir = tmp_path / "integration"
    ir.mkdir()
    proc = run_cli(
        "guard",
        "--workspace",
        str(clone),
        "--integration-root",
        str(ir),
        "--require-clone",
        "--json",
        env_extra={"AGENT_ID": "tester1"},
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "clone_identity_mismatch"


# ---------------------------------------------------------------------------
# submodules
# ---------------------------------------------------------------------------


def _make_child_repo(parent: Path) -> tuple[Path, str]:
    child = parent / "child"
    child.mkdir()
    assert git("init", "-b", "main", cwd=child).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=child).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=child).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=child).returncode == 0
    (child / "lib.txt").write_text("lib v1\n", encoding="utf-8")
    assert git("add", "lib.txt", cwd=child).returncode == 0
    assert git("commit", "-m", "child initial", cwd=child).returncode == 0
    return child, git("rev-parse", "HEAD", cwd=child).stdout.strip()


def _make_parent_with_submodule(parent: Path) -> tuple[Path, str]:
    child, child_pin = _make_child_repo(parent)
    repo = parent / "parent"
    repo.mkdir()
    assert git("init", "-b", "main", cwd=repo).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=repo).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=repo).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=repo).returncode == 0
    (repo / "a.txt").write_text("v1\n", encoding="utf-8")
    assert git("add", "a.txt", cwd=repo).returncode == 0
    assert git(
        "-c", "protocol.file.allow=always",
        "submodule", "add", str(child), "sub", cwd=repo,
    ).returncode == 0
    assert git("commit", "-m", "with submodule", cwd=repo).returncode == 0
    return repo, child_pin


def test_create_with_submodule_manifest_verify(tmp_path: Path):
    source, child_pin = _make_parent_with_submodule(tmp_path)
    dest = tmp_path / "clone"
    proc = run_cli(
        "create",
        "--agent-id",
        "tester1",
        "--delivery-attempt-id",
        "att1",
        "--source",
        str(source),
        "--destination",
        str(dest),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = stdout_json(proc)
    assert result["submodules_initialized"] is True
    assert result["initialized_submodules"] == ["sub"]
    manifest_path = tmp_path / "m.json"
    make_manifest(dest, manifest_path)
    with open(manifest_path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert len(stored["repositories"]) == 1
    entry = stored["repositories"][0]
    assert entry["path"] == "sub"
    assert entry["pinned_sha"] == child_pin
    assert entry["initialized"] is True
    assert entry["child_head"] == child_pin
    proc = run_cli("verify", "--clone", str(dest), "--manifest", str(manifest_path), "--json")
    assert proc.returncode == 0, proc.stderr
    assert stdout_json(proc)["reason"] == "verified"


def test_changeset_gitlink_advance(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    source, old_pin = _make_parent_with_submodule(work)
    clone = tmp_path / "clone"
    make_clone(source, clone, extra_args=())
    # Re-run create path with default submodule init for this source.
    # (make_clone uses --no-submodules; rebuild with full init here.)
    import shutil

    shutil.rmtree(clone)
    proc = run_cli(
        "create",
        "--agent-id",
        "tester1",
        "--delivery-attempt-id",
        "att1",
        "--source",
        str(source),
        "--destination",
        str(clone),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    # Advance the child repo, then move the clone's gitlink forward.
    child = work / "child"
    (child / "lib.txt").write_text("lib v2\n", encoding="utf-8")
    assert git("add", "lib.txt", cwd=child).returncode == 0
    assert git("commit", "-m", "child v2", cwd=child).returncode == 0
    new_pin = git("rev-parse", "HEAD", cwd=child).stdout.strip()
    assert new_pin != old_pin
    sub = clone / "sub"
    assert git("-c", "protocol.file.allow=always", "fetch", "origin", cwd=sub).returncode == 0
    assert git("checkout", new_pin, cwd=sub).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=clone).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=clone).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=clone).returncode == 0
    assert git("add", "sub", cwd=clone).returncode == 0
    assert git("commit", "-m", "bump sub", cwd=clone).returncode == 0
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    with open(out, encoding="utf-8") as fh:
        stored = json.load(fh)
    gitlink_changes = [c for c in stored["changes"] if c["kind"] == "gitlink"]
    assert len(gitlink_changes) == 1
    assert gitlink_changes[0]["path"] == "sub"
    assert gitlink_changes[0]["base_sha"] == old_pin
    assert gitlink_changes[0]["candidate_sha"] == new_pin


# ---------------------------------------------------------------------------
# production authority binding (live OS-account ~/Workspace + GitHub origin)
# ---------------------------------------------------------------------------
# Read-only against live origin: only `git ls-remote` probes and `git show`
# reads from the OS-account workspace object store.  Never push / merge /
# mutate refs; the only writes are temp-dir clones and a shallow blobless
# fetch INTO a temp clone.  Tests skip (with evidence) when the account
# workspace or the live network is absent instead of faking a positive.

LIVE_ORIGIN_URL = "https://github.com/starlink-awaken/omostation.git"
PRODUCTION_POLICY = ".omo/_truth/registry/swarm-coordination.yaml"


def _os_account_workspace() -> Path | None:
    root = Path(os.path.expanduser("~/Workspace"))
    if not root.is_dir():
        return None
    return Path(os.path.realpath(root))


def _live_main_sha(origin_url: str) -> str | None:
    """Resolve origin/main read-only; None when the network/probe fails."""
    proc = subprocess.run(
        ["git", "ls-remote", "--exit-code", origin_url, "refs/heads/main"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    rows = [line.split() for line in proc.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != "refs/heads/main":
        return None
    return rows[0][0]


def _yaml_capable_python() -> str | None:
    """An interpreter that can `import yaml`, for the PyYAML-present path."""
    import shutil

    candidates = [
        sys.executable,
        shutil.which("python3"),
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
    ]
    seen: set[str] = set()
    for exe in candidates:
        if not exe or exe in seen:
            continue
        seen.add(exe)
        probe = subprocess.run(
            [exe, "-c", "import yaml"], capture_output=True, check=False
        )
        if probe.returncode == 0:
            return exe
    return None


def run_cli_as(executable: str, *argv: str, env_extra: dict | None = None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [executable, str(AGENT_CLONE), *argv],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _fake_claims_root(tmp_path: Path) -> Path:
    """A non-account workspace carrying the production GitHub origin (config only)."""
    fake = tmp_path / "fake-claims"
    fake.mkdir()
    assert git("init", "-b", "main", cwd=fake).returncode == 0
    assert git("config", "user.name", "D1 Tester", cwd=fake).returncode == 0
    assert git("config", "user.email", "d1@example.com", cwd=fake).returncode == 0
    assert git("config", "commit.gpgsign", "false", cwd=fake).returncode == 0
    (fake / "f.txt").write_text("fake\n", encoding="utf-8")
    assert git("add", "f.txt", cwd=fake).returncode == 0
    assert git("commit", "-m", "fake claims root", cwd=fake).returncode == 0
    # Config-only: no network is touched, but the authority is non-hermetic
    # (https://github.com/...) so the strict OS-account binding applies.
    assert git("remote", "add", "origin", LIVE_ORIGIN_URL, cwd=fake).returncode == 0
    return fake


def test_production_claims_authority_mismatch(tmp_path: Path, source_repo: Path):
    """A GitHub-origin claims root outside the OS account workspace is refused."""
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    fake = _fake_claims_root(tmp_path)
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(tmp_path / "cs.json"),
        "--verify-claims",
        "--claims-root",
        str(fake),
        "--json",
    )
    assert proc.returncode == 1
    result = stdout_json(proc)
    assert result["reason"] == "claims_authority_mismatch"
    assert "OS-account integration workspace" in result["message"]


def test_production_live_main_resolution_degrades_honestly(
    tmp_path: Path, source_repo: Path
):
    """Correct claims root + live ls-remote OK, writer lacks the live object.

    Proves the OS-account binding passes and the exact origin/main revision
    is resolved read-only; the CLI then degrades with the stable reason
    instead of faking authority.
    """
    account_ws = _os_account_workspace()
    if account_ws is None:
        pytest.skip("OS-account ~/Workspace is absent on this host")
    live_sha = _live_main_sha(LIVE_ORIGIN_URL)
    if live_sha is None:
        pytest.skip(f"live origin unreachable via ls-remote: {LIVE_ORIGIN_URL}")
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    baseline = make_manifest(clone, baseline_path)
    assert baseline["root_head_sha"] != live_sha  # unrelated histories
    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(out),
        "--verify-claims",
        "--claims-root",
        str(account_ws),
        "--json",
    )
    assert proc.returncode == 1
    result = stdout_json(proc)
    assert result["reason"] == "claims_authority_revision_unavailable"
    assert "not present in the writer clone" in result["message"]
    assert live_sha in result["message"]
    assert not out.exists()  # authority failure writes no changeset


def test_production_baseline_untrusted_after_shallow_fetch(
    tmp_path: Path, source_repo: Path
):
    """Writer holds the live main object but its baseline is outside that history."""
    account_ws = _os_account_workspace()
    if account_ws is None:
        pytest.skip("OS-account ~/Workspace is absent on this host")
    live_sha = _live_main_sha(LIVE_ORIGIN_URL)
    if live_sha is None:
        pytest.skip(f"live origin unreachable via ls-remote: {LIVE_ORIGIN_URL}")
    clone = tmp_path / "clone"
    make_clone(source_repo, clone)
    baseline_path = tmp_path / "base.json"
    make_manifest(clone, baseline_path)
    # Read-only against origin (fetch INTO the temp clone only, never a push
    # or ref mutation on the authority).  Blobless + depth 1 keeps it small.
    fetch = git(
        "fetch",
        "--depth",
        "1",
        "--filter=blob:none",
        "--no-tags",
        LIVE_ORIGIN_URL,
        live_sha,
        cwd=clone,
    )
    if fetch.returncode != 0:
        pytest.skip(f"shallow blobless fetch of live main failed: {fetch.stderr.strip()[:200]}")
    assert (
        git("cat-file", "-e", f"{live_sha}^{{commit}}", cwd=clone).returncode == 0
    )
    proc = run_cli(
        "changeset",
        "--clone",
        str(clone),
        "--baseline",
        str(baseline_path),
        "--output",
        str(tmp_path / "cs.json"),
        "--verify-claims",
        "--claims-root",
        str(account_ws),
        "--json",
    )
    assert proc.returncode == 1
    assert stdout_json(proc)["reason"] == "claims_authority_baseline_untrusted"
    # Same verdict under a PyYAML-present interpreter: the `yaml is not None`
    # branch traverses the production binding identically (no fallback divergence).
    yaml_exe = _yaml_capable_python()
    if yaml_exe is not None and os.path.realpath(yaml_exe) != os.path.realpath(
        sys.executable
    ):
        rerun = run_cli_as(
            yaml_exe,
            "changeset",
            "--clone",
            str(clone),
            "--baseline",
            str(baseline_path),
            "--output",
            str(tmp_path / "cs-yaml.json"),
            "--verify-claims",
            "--claims-root",
            str(account_ws),
            "--json",
        )
        assert rerun.returncode == 1
        assert stdout_json(rerun)["reason"] == "claims_authority_baseline_untrusted"


def _live_policy_text(tmp_path: Path, account_ws: Path) -> tuple[str, str]:
    """Read-only policy blob at live origin/main; skips when unreachable.

    Immune to local-checkout lag: the blob is fetched (depth-1 commit/tree
    shell, then the single policy blob) INTO a temp repo only.  Live origin
    refs are never pushed/merged/mutated; only ls-remote + fetch (read-only).
    """
    live_sha = _live_main_sha(LIVE_ORIGIN_URL)
    if live_sha is None:
        pytest.skip(f"live origin unreachable via ls-remote: {LIVE_ORIGIN_URL}")
    fetcher = tmp_path / "polfetch"
    fetcher.mkdir()
    assert git("init", "-b", "main", cwd=fetcher).returncode == 0
    shell = git(
        "fetch",
        "--depth",
        "1",
        "--filter=blob:none",
        "--no-tags",
        LIVE_ORIGIN_URL,
        live_sha,
        cwd=fetcher,
    )
    if shell.returncode != 0:
        pytest.skip(f"shallow tree-shell fetch of live main failed: {shell.stderr.strip()[:200]}")
    tree = git("ls-tree", "FETCH_HEAD", "--", PRODUCTION_POLICY, cwd=fetcher)
    fields = tree.stdout.split()
    if tree.returncode != 0 or len(fields) < 3:
        pytest.skip(f"policy path absent at live main {live_sha[:12]}")
    blob_sha = fields[2]
    blob = git("fetch", "--no-tags", LIVE_ORIGIN_URL, blob_sha, cwd=fetcher)
    if blob.returncode != 0:
        pytest.skip(f"policy blob fetch failed: {blob.stderr.strip()[:200]}")
    show = git("cat-file", "-p", blob_sha, cwd=fetcher)
    if show.returncode != 0 or not show.stdout:
        pytest.skip("policy blob unreadable after fetch")
    return live_sha, show.stdout


def test_production_policy_binds_os_account_workspace(tmp_path: Path):
    """Real swarm-coordination.yaml at live origin/main binds the OS account root."""
    account_ws = _os_account_workspace()
    if account_ws is None:
        pytest.skip("OS-account ~/Workspace is absent on this host")
    live_sha, policy_text = _live_policy_text(tmp_path, account_ws)
    assert live_sha and policy_text
    assert 'integration_root: "~/Workspace"' in policy_text
    expanded = os.path.join(os.path.expanduser("~"), "Workspace")
    assert os.path.realpath(expanded) == str(account_ws)


def test_production_policy_requires_pyyaml(tmp_path: Path):
    """The live policy is true YAML (never JSON): production claims need PyYAML."""
    account_ws = _os_account_workspace()
    if account_ws is None:
        pytest.skip("OS-account ~/Workspace is absent on this host")
    _, policy_text = _live_policy_text(tmp_path, account_ws)
    yaml = pytest.importorskip("yaml", reason="PyYAML absent in test env")
    (tmp_path / "policy.yaml").write_text(policy_text, encoding="utf-8")
    document = yaml.safe_load(policy_text)
    assert document["topology_migration"]["integration_root"] == "~/Workspace"
    # Block-mapping YAML is not JSON: the stdlib fallback cannot parse the
    # production policy or the production run files, so the PyYAML-present
    # path is load-bearing on real authorities.
    with pytest.raises(Exception):
        json.loads(policy_text)
