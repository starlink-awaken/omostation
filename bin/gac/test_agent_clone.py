"""Real-repository tests for bin/gac/agent-clone.py (BET-Y1Q1-T1-05 D1 pilot).

Every test builds real temporary git repositories (source, bare remote,
submodule) and drives the CLI via subprocess.  No source-string assertions.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "bin" / "gac" / "agent-clone.py"

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
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, env=e, check=False
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd} (rc={proc.returncode}):\n{proc.stderr}"
        )
    return proc


def run_cli(
    *argv: str, env: dict | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    if env:
        e.update(env)
    else:
        # never leak an ambient AGENT_ID from the host into guard tests
        e.pop("AGENT_ID", None)
    proc = subprocess.run(
        [sys.executable, str(TOOL), *argv], capture_output=True, text=True, env=e, check=False
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"agent-clone {' '.join(argv)} failed (rc={proc.returncode}):\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def parse_json(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


def sha256_canonical(obj: dict, exclude: str | None = None) -> str:
    if exclude is not None:
        obj = {k: v for k, v in obj.items() if k != exclude}
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def make_source(
    base: Path, submodule_name: str = "childmod", with_hooks: bool = False
) -> tuple[Path, Path, Path]:
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
    git(src, "add", "README.md")
    git(src, "-c", "protocol.file.allow=always", "submodule", "add", str(child), submodule_name)
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
    git(child, "-c", "protocol.file.allow=always", "submodule", "add", str(nested), "grandchild")
    git(child, "commit", "-m", "add nested")
    git(src / "childmod", "fetch", "origin")
    git(src / "childmod", "checkout", git(child, "rev-parse", "HEAD").stdout.strip())
    git(src, "add", "childmod")
    git(src, "commit", "-m", "advance child pointer")
    git(src, "push", "origin", "main")
    return bare, nested


def create_clone(tmp: Path, bare: Path, name: str = "clone", **extra: object) -> Path:
    dest = tmp / name
    argv = ["create", "--json", "--agent-id", "agent-1", "--source", str(bare), "--destination", str(dest)]
    for flag, value in extra.items():
        argv.append(f"--{flag.replace('_', '-')}")
        if value is not True:
            argv.append(str(value))
    proc = run_cli(*argv, check=False)
    assert proc.returncode == 0, proc.stderr
    assert parse_json(proc)["reason"] == "clone_created"
    return dest


def write_manifest(tmp: Path, clone: Path, name: str = "manifest.json") -> Path:
    out = tmp / name
    proc = run_cli("manifest", "--clone", str(clone), "--output", str(out), "--json")
    assert parse_json(proc)["reason"] == "manifest_generated"
    return out


def tamper_manifest(path: Path, mutate, recompute: bool = True) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    if recompute:
        data["manifest_digest"] = sha256_canonical(data, exclude="manifest_digest")
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# create + independence
# ---------------------------------------------------------------------------


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
    assert identity["working_branch"] == "agent/agent-1"
    assert git(dest, "branch", "--show-current").stdout.strip() == "agent/agent-1"

    # no persistent alternates anywhere in the clone
    assert not (dest / ".git" / "objects" / "info" / "alternates").exists()
    assert not (
        dest / ".git" / "modules" / "childmod" / "objects" / "info" / "alternates"
    ).exists()

    # cloned independently: removing the source leaves the clone fully functional
    bare_contents = git(tmp_path / "source-bare.git", "rev-parse", "HEAD").stdout.strip()
    shutil.rmtree(tmp_path / "source-bare.git")
    assert git(dest, "rev-parse", "HEAD").stdout.strip() == bare_contents


def test_create_initializes_only_root_gitlinks(tmp_path):
    bare, _nested = make_nested_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    assert (dest / "childmod" / ".git").exists()
    assert not (dest / "childmod" / "grandchild" / ".git").exists()


def test_create_refuses_existing_path(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    empty = tmp_path / "empty-dir"
    empty.mkdir()
    proc = run_cli(
        "create", "--agent-id", "agent-1", "--source", str(bare),
        "--destination", str(empty), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "destination_collision"
    assert os.listdir(empty) == []


def test_create_with_revision(tmp_path):
    src, _child, bare = make_source(tmp_path)
    (src / "README.md").write_text("v2\n")
    git(src, "add", "README.md")
    git(src, "commit", "-m", "m2")
    git(src, "push", "origin", "main")
    m1_sha = git(src, "rev-parse", "HEAD~1").stdout.strip()

    dest = tmp_path / "clone"
    proc = run_cli(
        "create", "--agent-id", "agent-1", "--source", str(bare),
        "--destination", str(dest), "--revision", m1_sha, "--json",
    )
    assert parse_json(proc)["reason"] == "clone_created"
    assert git(dest, "rev-parse", "HEAD").stdout.strip() == m1_sha
    identity = json.loads((dest / ".git" / "agent-clone-identity.json").read_text())
    assert identity["frozen_root_sha"] == m1_sha
    assert git(dest, "branch", "--show-current").stdout.strip() == "agent/agent-1"


def test_create_no_submodules_manifest_uninitialized(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = tmp_path / "clone"
    proc = run_cli(
        "create", "--agent-id", "agent-1", "--source", str(bare),
        "--destination", str(dest), "--no-submodules", "--json",
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
            "create", "--agent-id", bad, "--source", str(bare),
            "--destination", str(tmp_path / "c"), "--json", check=False,
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
    assert data["schema"] == "agent-clone-manifest/v1"
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


def test_dirty_root_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    (dest / "untracked.txt").write_text("x\n")
    proc = run_cli(
        "manifest", "--clone", str(dest), "--output", str(tmp_path / "m.json"),
        "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "root_dirty"


def test_dirty_child_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    (dest / "childmod" / "dirty.txt").write_text("x\n")
    proc = run_cli(
        "manifest", "--clone", str(dest), "--output", str(tmp_path / "m.json"),
        "--json", check=False,
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
    m = write_manifest(tmp_path, dest, "m.json")
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
        "verify", "--clone", str(dest), "--manifest", str(manifest),
        "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "origin_drift"


def test_child_origin_drift_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    manifest = write_manifest(tmp_path, dest, "m.json")
    git(dest / "childmod", "remote", "set-url", "origin", str(tmp_path / "child-other.git"))
    proc = run_cli(
        "verify", "--clone", str(dest), "--manifest", str(manifest),
        "--json", check=False,
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
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(out), "--json",
    )
    assert parse_json(proc)["reason"] == "changeset_generated"
    data = json.loads(out.read_text())
    assert data["schema"] == "cross-repo-changeset/v1"
    assert data["no_change"] is True
    assert data["changes"] == []
    assert data["root_base_sha"] == data["root_candidate_sha"]
    assert data["baseline_manifest_digest"] == json.loads(baseline.read_text())["manifest_digest"]


def test_changeset_fast_forward_accepted(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    _new_root = _advance_source(src, child)
    _ff_clone(dest)

    out = tmp_path / "cs.json"
    proc = run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(out), "--json",
    )
    assert parse_json(proc)["reason"] == "changeset_generated"
    data = json.loads(out.read_text())
    assert data["no_change"] is False
    assert len(data["changes"]) == 1
    change = data["changes"][0]
    assert change["path"] == "childmod"
    assert change["ancestry_proven"] is True
    assert data["root_candidate_sha"] == git(dest, "rev-parse", "HEAD").stdout.strip()


def test_changeset_rejects_child_head_gitlink_mismatch(tmp_path):
    src, child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    _advance_source(src, child)
    _ff_clone(dest)
    git(dest / "childmod", "checkout", "HEAD~1")
    git(dest, "config", "submodule.childmod.ignore", "all")

    proc = run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
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
        "changeset", "--clone", str(dest), "--baseline", str(baseline2),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
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
        "changeset", "--clone", str(other), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
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
        "changeset", "--clone", str(dest), "--baseline", str(baseline2),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_rewind_or_diverged"


def test_changeset_dirty_candidate_rejected(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    (dest / "untracked.txt").write_text("x\n")
    proc = run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "candidate_dirty"


def test_changeset_baseline_digest_validation(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    tamper_manifest(baseline, lambda d: d.__setitem__("root_head_sha", "0" * 40), recompute=False)
    proc = run_cli(
        "changeset", "--clone", str(dest), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
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
        "guard", "--workspace", str(integration),
        "--integration-root", str(integration), "--json",
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "human"

    # AGENT_ID on the integration root: denied
    proc = run_cli(
        "guard", "--workspace", str(integration),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "agent-1"}, check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"

    # matching clone identity: verified clone
    proc = run_cli(
        "guard", "--workspace", str(dest),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "agent-1"},
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "verified_clone"

    # mismatched clone identity: denied
    proc = run_cli(
        "guard", "--workspace", str(dest),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "other-agent"}, check=False,
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
        "guard", "--workspace", str(legacy),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "agent-1"},
    )
    out = parse_json(proc)
    assert out["ok"] is True and out["state"] == "legacy_isolated_worktree"


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
        "create", "--agent-id", "agent-1", "--source", str(bare),
        "--destination", str(occupied), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "destination_collision"
    assert (occupied / "keep.txt").read_text() == "x\n"

    # clone failure (missing source): fail closed, destination left absent
    proc = run_cli(
        "create", "--agent-id", "agent-1", "--source", str(tmp_path / "missing"),
        "--destination", str(tmp_path / "bad"), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "clone_failed"
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
        "changeset", "--clone", str(dest), "--baseline", str(m),
        "--output", str(out), "--json",
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
        "guard", "--workspace", str(dest),
        "--integration-root", str(tmp_path / "integration"), "--json",
        env={"AGENT_ID": "agent-1"}, check=False,
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
        "manifest", "--clone", str(dest), "--output", str(tmp_path / "m.json"),
        "--json", check=False,
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
        "changeset", "--clone", str(clone_b), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
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
        "changeset", "--clone", str(clone_a), "--baseline", str(baseline),
        "--output", str(tmp_path / "cs.json"), "--json", check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "child_rewind_or_diverged"


def test_changeset_change_id_deterministic(tmp_path):
    _src, _child, bare = make_source(tmp_path)
    dest = create_clone(tmp_path, bare)
    baseline = write_manifest(tmp_path, dest, "baseline.json")
    out1 = tmp_path / "cs1.json"
    out2 = tmp_path / "cs2.json"
    run_cli("changeset", "--clone", str(dest), "--baseline", str(baseline), "--output", str(out1))
    run_cli("changeset", "--clone", str(dest), "--baseline", str(baseline), "--output", str(out2))
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
        "guard", "--workspace", str(nested / "cl"),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "agent-1"}, check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"

    link = tmp_path / "ws-link"
    os.symlink(integration, link)
    proc = run_cli(
        "guard", "--workspace", str(link),
        "--integration-root", str(integration), "--json",
        env={"AGENT_ID": "agent-1"}, check=False,
    )
    assert proc.returncode == 1
    assert parse_json(proc)["reason"] == "agent_on_integration_root"
