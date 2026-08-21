"""G-CONV.7 / ADR-0220: unit tests drive real swarm_discipline helpers."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run an isolated real-git fixture command and retain failure output."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {repo} (rc={result.returncode}):\n{result.stderr}"
        )
    return result


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")


def _install_submodule_hook(repo: Path) -> None:
    hook_source = ROOT / ".githooks" / "pre-commit"
    hook_dest = repo / ".git" / "hooks" / "pre-commit"
    hook_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(hook_source, hook_dest)
    os.chmod(hook_dest, 0o755)


def _child_repo(tmp_path: Path) -> tuple[Path, str, str]:
    child = tmp_path / "child-repository"
    _init_repo(child)
    (child / "payload.txt").write_text("base\n", encoding="utf-8")
    _git(child, "add", "payload.txt")
    _git(child, "commit", "-m", "base")
    base_sha = _git(child, "rev-parse", "HEAD").stdout.strip()
    (child / "payload.txt").write_text("fast-forward\n", encoding="utf-8")
    _git(child, "add", "payload.txt")
    _git(child, "commit", "-m", "fast-forward")
    advanced_sha = _git(child, "rev-parse", "HEAD").stdout.strip()
    return child, base_sha, advanced_sha


def _root_with_agora_submodule(tmp_path: Path, child: Path, base_sha: str) -> Path:
    root = tmp_path / "root with spaces"
    _init_repo(root)
    (root / "README.md").write_text("root\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "root base")
    _git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(child), "projects/agora")
    _git(root / "projects" / "agora", "checkout", base_sha)
    _git(root, "add", "projects/agora")
    _git(root, "commit", "-m", "add agora")
    _install_submodule_hook(root)
    return root


def _stage_gitlink(root: Path, sha: str, *, ref: str = "main") -> None:
    submodule = root / "projects" / "agora"
    _git(submodule, "fetch", "origin", ref)
    _git(submodule, "checkout", sha)
    _git(root, "add", "projects/agora")


def test_submodule_guard_accepts_child_fast_forward_when_root_lacks_child_object(tmp_path):
    """The root object DB must not reject a valid child-repository fast-forward."""
    child, base_sha, advanced_sha = _child_repo(tmp_path)
    root = _root_with_agora_submodule(tmp_path, child, base_sha)
    _stage_gitlink(root, advanced_sha)

    # A gitlink records the SHA but does not import that child commit object.
    assert _git(root, "cat-file", "-e", f"{advanced_sha}^{{commit}}", check=False).returncode != 0
    assert _git(root / "projects" / "agora", "merge-base", "--is-ancestor", base_sha, advanced_sha).returncode == 0

    commit = _git(root, "commit", "-m", "advance agora", check=False)
    assert commit.returncode == 0, commit.stdout + commit.stderr


def test_submodule_guard_rejects_child_divergence(tmp_path):
    """A child commit from a sibling branch remains a hard failure."""
    child, base_sha, _advanced_sha = _child_repo(tmp_path)
    _git(child, "branch", "divergent", base_sha)
    _git(child, "checkout", "divergent")
    (child / "payload.txt").write_text("divergent\n", encoding="utf-8")
    _git(child, "add", "payload.txt")
    _git(child, "commit", "-m", "divergent")
    divergent_sha = _git(child, "rev-parse", "HEAD").stdout.strip()
    _git(child, "checkout", "main")
    root = _root_with_agora_submodule(tmp_path, child, _advanced_sha)
    _stage_gitlink(root, divergent_sha, ref="divergent")

    commit = _git(root, "commit", "-m", "diverge agora", check=False)
    assert commit.returncode != 0
    assert "不是 fast-forward" in commit.stderr


def test_submodule_guard_rejects_missing_child_object(tmp_path):
    """An initialized child repository with an unknown staged SHA fails closed."""
    child, base_sha, _advanced_sha = _child_repo(tmp_path)
    root = _root_with_agora_submodule(tmp_path, child, base_sha)
    missing_sha = "a" * 40
    _git(root, "update-index", "--cacheinfo", f"160000,{missing_sha},projects/agora")

    commit = _git(root, "commit", "-m", "missing agora object", check=False)
    assert commit.returncode != 0
    assert "不是 fast-forward" in commit.stderr


def test_submodule_guard_rejects_uninitialized_child_directory(tmp_path):
    """A staged gitlink without a checked-out child repository fails closed."""
    child, base_sha, advanced_sha = _child_repo(tmp_path)
    root = tmp_path / "uninitialized root"
    _init_repo(root)
    (root / "README.md").write_text("root\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "root base")
    _git(root, "update-index", "--add", "--cacheinfo", f"160000,{base_sha},projects/agora")
    _git(root, "commit", "-m", "add uninitialized gitlink")
    _install_submodule_hook(root)
    _git(root, "update-index", "--cacheinfo", f"160000,{advanced_sha},projects/agora")

    commit = _git(root, "commit", "-m", "advance uninitialized gitlink", check=False)
    assert commit.returncode != 0
    assert "子模块未初始化" in commit.stderr


def _load():
    path = ROOT / "bin/gac/swarm_discipline.py"
    spec = importlib.util.spec_from_file_location("swarm_discipline", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_registry_present_and_has_four_gates():
    reg_path = ROOT / ".omo/_truth/registry/swarm-coordination.yaml"
    assert reg_path.is_file()
    text = reg_path.read_text(encoding="utf-8")
    for key in (
        "d1_adr_atomic_claim",
        "d2_branch_occupancy",
        "d3_shared_worktree_claim",
        "d4_escape_hatch",
    ):
        assert key in text
    assert "escape_hatch_exemptions" in text


def test_d1_adr_claim_atomic_and_second_session_blocked(tmp_path):
    m = _load()
    # minimal registry for delivery paths (use defaults under tmp root)
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\ndelivery: {}\nescape_hatch_exemptions: []\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_knowledge/decisions").mkdir(parents=True)
    # seed existing ADR so next is predictable
    (tmp_path / ".omo/_knowledge/decisions/0001-seed.md").write_text("# x\n", encoding="utf-8")

    ok1, r1 = m.acquire_adr_claim(tmp_path, "agent-a")
    assert ok1, r1
    n = r1["number"]
    ok2, r2 = m.acquire_adr_claim(tmp_path, "agent-b", number=n)
    assert not ok2, r2
    assert "claimed" in str(r2.get("error", "")).lower() or "session" in str(r2)


def test_d1_adr_write_requires_claim(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text("version: 1\n", encoding="utf-8")
    (tmp_path / ".omo/_knowledge/decisions").mkdir(parents=True)
    ok, reason = m.check_adr_write_authorized(tmp_path, ".omo/_knowledge/decisions/0099-new.md", "s1")
    assert not ok
    assert "claim" in reason.lower()


def test_d1_empty_session_cannot_use_foreign_claim(tmp_path):
    """Skeptic: empty session must not inherit holder claim."""
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text("version: 1\n", encoding="utf-8")
    (tmp_path / ".omo/_knowledge/decisions").mkdir(parents=True)
    ok, r = m.acquire_adr_claim(tmp_path, "owner-sess")
    assert ok
    n = r["number"]
    path = f".omo/_knowledge/decisions/{n:04d}-x.md"
    ok_empty, reason = m.check_adr_write_authorized(tmp_path, path, "")
    assert not ok_empty, reason
    assert "session" in reason.lower()
    ok_match, _ = m.check_adr_write_authorized(tmp_path, path, "owner-sess")
    assert ok_match


def test_d2_branch_occupancy_blocks_second_session(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text("version: 1\n", encoding="utf-8")
    ok1, r1 = m.acquire_branch_lock(tmp_path, "sess-a", "work/sess-a")
    assert ok1, r1
    ok2, r2 = m.acquire_branch_lock(tmp_path, "sess-b", "work/sess-a")
    assert not ok2, r2
    assert "occupied" in str(r2.get("error", "")).lower() or "sess-a" in str(r2)


def test_d3_shared_worktree_unclaimed_fails_isolated_ok(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\nshared_worktree_allow_path_globs: ['runtime/**']\n",
        encoding="utf-8",
    )
    ok, viol = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="main",
        claimed_paths=[],
    )
    assert not ok
    assert viol

    ok2, viol2 = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="work/gconv7",
        claimed_paths=[],
    )
    assert ok2
    assert not viol2

    ok3, _ = m.check_shared_worktree_writes(
        tmp_path,
        ["docs/foo.md"],
        branch="main",
        claimed_paths=["docs/"],
    )
    assert ok3


def test_d4_escape_requires_allowlisted_id(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        """
version: 1
escape_hatch_exemptions:
  - id: submodule-reachability-partial-worktree
    allow: [ci_local_skip, no_verify_push, no_verify_commit]
    active: true
    reason: test
""",
        encoding="utf-8",
    )
    ok, reason = m.check_escape_hatch(tmp_path, flag="ci_local_skip", escape_id=None)
    assert not ok
    ok2, _ = m.check_escape_hatch(
        tmp_path,
        flag="ci_local_skip",
        escape_id="submodule-reachability-partial-worktree",
        agent_id="",
    )
    assert ok2
    log_dir = tmp_path / ".omo/_delivery/swarm-escape"
    written = list(log_dir.glob("*.json"))
    assert written, "allowlisted skip must write an audit record"
    rec = json.loads(written[0].read_text(encoding="utf-8"))
    assert rec.get("surface")
    assert rec.get("check_id")
    assert rec.get("signature")
    reason_only = {"ts", "flag", "escape_id", "reason"}
    assert not set(rec.keys()) <= reason_only
    assert rec["signature"] != rec.get("reason")
    ok3, _ = m.check_escape_hatch(tmp_path, flag="ci_local_skip", escape_id="not-a-real-id")
    assert not ok3


def _write_exemptions(tmp_path, body: str) -> None:
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        body,
        encoding="utf-8",
    )


def test_d4_human_hotfix_denied_when_agent_id_set(tmp_path):
    m = _load()
    _write_exemptions(
        tmp_path,
        """
version: 1
escape_solidification:
  mode: shadow
escape_hatch_exemptions:
  - id: emergency-human-hotfix
    allow: [ci_local_skip, no_verify_push, no_verify_commit]
    active: true
    requires_human: true
    reason: human
""",
    )
    ok, reason = m.check_escape_hatch(
        tmp_path,
        flag="ci_local_skip",
        escape_id="emergency-human-hotfix",
        agent_id="grok-agent",
    )
    assert not ok
    assert "human" in reason.lower() or "agent" in reason.lower()


def test_d4_human_hotfix_allowed_when_agent_id_empty(tmp_path):
    m = _load()
    _write_exemptions(
        tmp_path,
        """
version: 1
escape_hatch_exemptions:
  - id: emergency-human-hotfix
    allow: [ci_local_skip]
    active: true
    requires_human: true
    reason: human
""",
    )
    ok, _ = m.check_escape_hatch(
        tmp_path,
        flag="ci_local_skip",
        escape_id="emergency-human-hotfix",
        agent_id="",
    )
    assert ok


def test_d4_partial_worktree_cannot_skip_generic_gac_fingerprint(tmp_path):
    m = _load()
    _write_exemptions(
        tmp_path,
        """
version: 1
escape_hatch_exemptions:
  - id: partial-worktree
    allow: [ci_local_skip]
    surfaces: [ci-local-fast]
    fingerprint_allow: ["uninitialized-submodule:*"]
    active: true
    reason: uninit only
""",
    )
    fp = {
        "surface": "ci-local-fast",
        "check_id": "gac",
        "signature": "deadbeef",
        "kind": "preflight",
        "producer": "gac",
    }
    ok, reason = m.check_escape_hatch(
        tmp_path,
        flag="ci_local_skip",
        escape_id="partial-worktree",
        fingerprints=[fp],
        agent_id="",
    )
    assert not ok
    assert "cannot skip" in reason or "fingerprint" in reason


def test_d4_overheat_helper_requires_sink_after_threshold(tmp_path):
    m = _load()
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 8, 29, tzinfo=UTC)
    key = "ci-local-fast|gac|abcd"
    records = [
        {
            "ts": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "escape_id": "local-preflight-preexisting",
            "fingerprint_key": key,
            "surface": "ci-local-fast",
            "check_id": "gac",
            "signature": "abcd",
        }
        for _ in range(3)
    ]
    heat = m.overheat_signal(
        records,
        key,
        now=now,
        threshold=3,
        window_days=7,
        shadow_ended_flag=True,
        escape_id="local-preflight-preexisting",
    )
    assert heat["overheat"] is True
    assert heat["count"] == 3
    assert heat["sink_required"] is True
    heat_shadow = m.overheat_signal(
        records,
        key,
        now=now,
        threshold=3,
        window_days=7,
        shadow_ended_flag=False,
    )
    assert heat_shadow["overheat"] is True
    assert heat_shadow["sink_required"] is False


def test_d4_no_verify_argv_gate(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        """
version: 1
escape_hatch_exemptions:
  - id: write-owner-repair-draft
    allow: [no_verify_commit]
    active: true
    reason: test
""",
        encoding="utf-8",
    )
    ok, _ = m.check_git_argv_escape(tmp_path, ["commit", "-m", "x"], None)
    assert ok  # no --no-verify
    ok2, reason = m.check_git_argv_escape(tmp_path, ["commit", "--no-verify", "-m", "x"], None)
    assert not ok2
    ok3, _ = m.check_git_argv_escape(
        tmp_path,
        ["commit", "--no-verify", "-m", "x"],
        "write-owner-repair-draft",
    )
    assert ok3


def test_conflict_window_status_open_until_72h(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\nobservation:\n  window_hours: 72\n",
        encoding="utf-8",
    )
    meta = m.start_conflict_window(tmp_path)
    assert "window_start" in meta
    # disable orphan git scan in tiny tmp (no real git history needed)
    status = m.conflict_window_status(tmp_path, scan_orphans=False)
    assert status["m1_conflict_zero_verdict"] == "window_open"
    assert status["conflict_count"] == 0
    m.emit_conflict_event(tmp_path, "branch_hijack", {"branch": "work/x"})
    status2 = m.conflict_window_status(tmp_path, scan_orphans=False)
    assert status2["conflict_count"] == 1
    assert status2["m1_conflict_zero_verdict"] == "window_open"


def test_scan_orphan_commits_dedupes_and_shapes(tmp_path):
    m = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text("version: 1\n", encoding="utf-8")
    # no git repo → empty list, must not raise
    hits = m.scan_orphan_commits(tmp_path, None, emit=False)
    assert hits == []


def test_wired_entrypoints_reference_gates():
    """Structural: real entrypoints call into swarm discipline (no orphan registry)."""
    wt = (ROOT / "bin/gac/gac-worktree.sh").read_text(encoding="utf-8")
    assert "branch-claim" in wt
    assert "swarm-discipline-cli" in wt
    pre = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "swarm-claim-check" in pre
    # install-hooks path must include D3 (skeptic: not only pre-commit framework)
    githook_pre = (ROOT / ".githooks/pre-commit").read_text(encoding="utf-8")
    # D3 shared-worktree claim retired 2026-08-19; clone-guard remains the writer gate.
    assert "clone-guard" in githook_pre or "agent-clone.py" in githook_pre
    push = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "escape-check" in push
    assert "--failures-file" in push or "--failures-json" in push
    swarm_git = (ROOT / "bin/gac/swarm-git").read_text(encoding="utf-8")
    assert "escape-check" in swarm_git
    assert "emergency-human-hotfix" in swarm_git or "SWARM_ESCAPE_TOKEN" in swarm_git
    adr = (ROOT / "bin/adr/next-adr-id.py").read_text(encoding="utf-8")
    assert "acquire_adr_claim" in adr or "swarm_discipline" in adr
    assert (ROOT / "bin/gac/swarm-git").is_file()
    foundry = (ROOT / "bin/gac/knowledge-foundry-cron.py").read_text(encoding="utf-8")
    assert "5:50-swarm-window" in foundry
    assert "window-status" in foundry


def test_d3_real_pre_commit_hook_blocks_unclaimed_main(tmp_path):
    """Drive real git commit through installed .githooks/pre-commit (install-hooks path)."""
    import os
    import shutil
    import subprocess
    import textwrap

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

    # Minimal tree: hooks + swarm CLI + registry + core module
    (repo / "bin/gac").mkdir(parents=True)
    (repo / ".omo/_truth/registry").mkdir(parents=True)
    (repo / ".githooks").mkdir()
    shutil.copy(ROOT / "bin/gac/swarm_discipline.py", repo / "bin/gac/swarm_discipline.py")
    shutil.copy(
        ROOT / "bin/gac/swarm-discipline-cli.py",
        repo / "bin/gac/swarm-discipline-cli.py",
    )
    (repo / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        textwrap.dedent(
            """
            version: 1
            shared_worktree_allow_path_globs: []
            escape_hatch_exemptions: []
            delivery: {}
            """
        ),
        encoding="utf-8",
    )
    # Slim pre-commit: only D3 (full gate is slow / needs monorepo)
    (repo / ".githooks/pre-commit").write_text(
        textwrap.dedent(
            """
            #!/bin/bash
            set -euo pipefail
            ROOT="$(git rev-parse --show-toplevel)"
            _d3_out="$(python3 "$ROOT/bin/gac/swarm-discipline-cli.py" claim-check --staged 2>&1)" || _d3_rc=$?
            _d3_rc="${_d3_rc:-0}"
            printf '%s\\n' "$_d3_out" >&2
            if [ "$_d3_rc" -ne 0 ]; then
              echo "[swarm-d3] blocked" >&2
              exit 1
            fi
            exit 0
            """
        ).lstrip(),
        encoding="utf-8",
    )
    # install-hooks path
    hooks = repo / ".git/hooks"
    hooks.mkdir(exist_ok=True)
    shutil.copy(repo / ".githooks/pre-commit", hooks / "pre-commit")
    os.chmod(hooks / "pre-commit", 0o755)

    # Bootstrap first commit with hook temporarily disabled (unborn main has branch=HEAD)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    os.chmod(hooks / "pre-commit", 0o644)  # disable
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    os.chmod(hooks / "pre-commit", 0o755)  # re-enable install-hooks path

    (repo / "docs").mkdir()
    (repo / "docs/secret.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/secret.md"], cwd=repo, check=True)
    # On main, unclaimed → must fail
    r = subprocess.run(
        ["git", "commit", "-m", "unclaimed"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, r.stdout + r.stderr
    blob = (r.stdout + r.stderr).lower()
    assert "swarm" in blob or "claim" in blob or "unclaimed" in blob

    # Switch to isolated work branch → allow
    subprocess.run(["git", "checkout", "-b", "work/probe"], cwd=repo, check=True)
    r2 = subprocess.run(
        ["git", "commit", "-m", "isolated ok"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_b3_branch_release_purges_orphan_claims(tmp_path):
    """B3 (ADR-0367): branch-release 兜底删除分支已不存在的孤儿 claim."""
    m = _load()
    # tmp 作为 git 仓库, for-each-ref 可查分支
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "it@test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "it"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "checkout", "-q", "-b", "work/alive"], check=True)

    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\ndelivery: {}\nescape_hatch_exemptions: []\n",
        encoding="utf-8",
    )
    claims_dir = tmp_path / ".omo/_delivery/branch-claims"
    claims_dir.mkdir(parents=True)
    (claims_dir / "alive-session.json").write_text(
        json.dumps({"branch": "work/alive", "session": "alive-session"}),
        encoding="utf-8",
    )
    (claims_dir / "dead-session.json").write_text(
        json.dumps({"branch": "work/dead", "session": "dead-session"}), encoding="utf-8"
    )
    (claims_dir / "no-branch.json").write_text(json.dumps({"session": "no-branch"}), encoding="utf-8")

    m.release_branch_lock(tmp_path, "alive-session", purge_orphans=True)

    remaining = {p.name for p in claims_dir.glob("*.json") if p.name != ".lock"}
    # 自己的 claim 释放 + work/dead 孤儿清除; 无 branch 字段的保留
    assert remaining == {"no-branch.json"}, remaining
