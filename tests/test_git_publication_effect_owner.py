"""Wave B2: prove six local entrypoints cannot reach publication writers."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAC_WORKTREE = ROOT / "bin" / "gac" / "gac-worktree.sh"
GIT_RETRY = ROOT / "bin" / "gac" / "git-retry.sh"
GH_API_PUSH = ROOT / "bin" / "gac" / "gh-api-push.sh"
GIT_SHIM = ROOT / "bin" / "gac" / "git-shim"
SWARM_GIT = ROOT / "bin" / "gac" / "swarm-git"
GITLINK_DRIFT = ROOT / "bin" / "gac" / "gitlink-drift-protect.py"
SYNC_SUBMODULES = ROOT / "bin" / "sync-submodules.sh"
SYNC_SUBMODULES_PUSH = ROOT / "bin" / "ssot" / "sync-submodules-push.sh"
WAIT_AND_BUMP = ROOT / "scripts" / "wait-and-bump-cockpit.sh"

PROPOSAL_KEYS = (
    "MANAGED_SUCCESSOR_REQUIRED",
    "source_commit=",
    "base_commit=",
    "patch_digest=",
    "changed_path_digest=",
)


def _git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "effect-owner@test.invalid")
    _git(path, "config", "user.name", "Effect Owner")
    (path / "tracked.txt").write_text("initial\n", encoding="utf-8")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-q", "-m", "initial")


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class PublicationEffectHarness:
    """PATH wrappers that record forbidden publication effects."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "effect-harness"
        self.bin = self.root / "bin"
        self.log = self.root / "effects.log"
        self.bin.mkdir(parents=True)
        self.log.write_text("", encoding="utf-8")
        self.real_git = shutil.which("git")
        assert self.real_git
        self._install_git_wrapper()
        self._install_gh_wrapper()

    def _install_git_wrapper(self) -> None:
        _write_exec(
            self.bin / "git",
            textwrap.dedent(
                f"""\
                #!/bin/sh
                LOG="{self.log}"
                REAL_GIT="{self.real_git}"
                case " $* " in
                  *" push "*)
                    echo "git-push:$*" >> "$LOG"
                    case " $* " in *"--no-verify"*) echo "no-verify:$*" >> "$LOG" ;; esac
                    echo "fake git: push blocked by harness" >&2
                    exit 97
                    ;;
                esac
                for arg in "$@"; do
                  if [ "$arg" = "--no-verify" ]; then
                    echo "no-verify:$*" >> "$LOG"
                  fi
                done
                exec "$REAL_GIT" "$@"
                """
            ),
        )

    def _install_gh_wrapper(self) -> None:
        _write_exec(
            self.bin / "gh",
            textwrap.dedent(
                f"""\
                #!/bin/sh
                LOG="{self.log}"
                echo "gh:$*" >> "$LOG"
                case " $* " in
                  *" pr create "*)
                    echo "gh-pr-create:$*" >> "$LOG"
                    echo "https://example.test/pr/1"
                    exit 0
                    ;;
                  *" api "*)
                    echo "gh-api:$*" >> "$LOG"
                    case "$*" in
                      *git/refs*|*git/data*|*git/commits*|*git/trees*|*git/blobs*)
                        echo "git-data-api:$*" >> "$LOG"
                        ;;
                    esac
                    # read-only validate may call gh pr view
                    echo '{{"state":"MERGED","title":"feat(cockpit): extend decide commands for HITL proposal awareness"}}'
                    exit 0
                    ;;
                esac
                exit 0
                """
            ),
        )

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_ALLOW_PROTOCOL": "file",
        }
        if extra:
            env.update(extra)
        return env

    def events(self) -> str:
        return self.log.read_text(encoding="utf-8")

    def assert_no_publication_effects(self) -> None:
        text = self.events()
        assert "git-push:" not in text
        assert "gh-pr-create:" not in text
        assert "git-data-api:" not in text
        assert "no-verify:" not in text


def _make_parent_with_submodule(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    parent.mkdir()
    _init_repo(parent)
    child = tmp_path / "child"
    child.mkdir()
    _init_repo(child)
    subprocess.run(
        [
            "git",
            "-C",
            str(parent),
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(child),
            "modules/alpha",
        ],
        check=True,
    )
    _git(parent, "commit", "-q", "-am", "add submodule")
    _git(parent, "remote", "add", "origin", "https://github.com/starlink-awaken/omostation.git")
    _git(parent, "update-ref", "refs/remotes/origin/main", "HEAD")
    return parent


def _assert_complete_proposal(output: str) -> None:
    for key in PROPOSAL_KEYS:
        assert key in output, f"missing proposal field {key} in:\n{output}"
    assert "clone-lifecycle integrate" not in output.lower() or "replay" in output.lower()
    # must not invoke integrate as a command
    assert "clone-lifecycle.py integrate" not in output
    assert re.search(r"source_commit=[0-9a-f]{40}", output)
    assert re.search(r"base_commit=[0-9a-f]{40}", output)
    assert re.search(r"patch_digest=[0-9a-f]{64}", output)
    assert re.search(r"changed_path_digest=[0-9a-f]{64}", output)


def test_red_worktree_submit_emits_successor_proposal_only(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    parent = _make_parent_with_submodule(tmp_path)
    ws_parent = tmp_path / "worktrees"
    ws_parent.mkdir()
    session = "effect-submit"
    wt = ws_parent / f"ws-{session}"
    subprocess.run(
        [
            "git",
            "-C",
            str(parent),
            "worktree",
            "add",
            "-b",
            f"work/{session}",
            str(wt),
            "origin/main",
        ],
        check=True,
    )
    (wt / "tracked.txt").write_text("submit-change\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(GAC_WORKTREE), "submit", session],
        cwd=wt,
        env=harness.env({"WS_ROOT": str(parent), "WS_PARENT": str(ws_parent)}),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode == 2, combined
    _assert_complete_proposal(combined)
    assert "MANAGED_SUCCESSOR_REQUIRED" in combined
    assert "gh pr create" not in combined
    harness.assert_no_publication_effects()
    assert "clone-lifecycle" not in harness.events()


def test_git_retry_push_rejects_before_git(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    repo = tmp_path / "retry-repo"
    repo.mkdir()
    _init_repo(repo)

    result = subprocess.run(
        ["bash", str(GIT_RETRY), "push", "origin", "main"],
        cwd=repo,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode != 0
    assert "PUBLICATION_OWNER_REQUIRED" in combined
    harness.assert_no_publication_effects()


def test_gh_api_push_rejects_before_any_gh_call(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    payload = tmp_path / "payload.txt"
    payload.write_text("proposed change\n", encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            str(GH_API_PUSH),
            "example-owner",
            "example-repo",
            "agent/example--attempt-1",
            "main",
            "chore: propose change",
            str(payload),
        ],
        cwd=ROOT,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode != 0, combined
    assert "PUBLICATION_OWNER_REQUIRED" in combined
    assert harness.events() == ""
    harness.assert_no_publication_effects()


def test_git_wrappers_reject_every_push_form_before_git(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    branch = "agent/example--attempt-1"
    head = "a" * 40
    push_forms = (
        ("push", "origin", "HEAD"),
        ("push", "-f", "origin", "HEAD"),
        ("push", "--force", "origin", "HEAD"),
        ("push", "--force-with-lease", "origin", "HEAD"),
        (
            "push",
            "--porcelain",
            f"--force-with-lease=refs/heads/{branch}:",
            "origin",
            f"{head}:refs/heads/{branch}",
        ),
        ("push", "--no-verify", "origin", "HEAD"),
        ("-C", str(ROOT), "push", "origin", "HEAD"),
        ("-c", "push.default=current", "push", "origin", "HEAD"),
        ("--git-dir=.git", "push", "origin", "HEAD"),
    )

    for script in (GIT_SHIM, SWARM_GIT):
        for argv in push_forms:
            result = subprocess.run(
                ["bash", str(script), *argv],
                cwd=ROOT,
                env=harness.env({"AGENT_ID": "publication-test"}),
                capture_output=True,
                text=True,
                check=False,
            )
            combined = result.stdout + "\n" + result.stderr
            assert result.returncode != 0, (script.name, argv, combined)
            assert "PUBLICATION_OWNER_REQUIRED" in combined, (script.name, argv, combined)
    harness.assert_no_publication_effects()


def test_gitlink_drift_fix_emits_proposal_without_push(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    fixture = tmp_path / "drift-repo"
    fixture.mkdir()
    _init_repo(fixture)
    child = tmp_path / "drift-child"
    child.mkdir()
    _init_repo(child)
    subprocess.run(
        [
            "git",
            "-C",
            str(fixture),
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(child),
            "modules/alpha",
        ],
        check=True,
    )
    _git(fixture, "commit", "-q", "-am", "add submodule")
    # Advance submodule HEAD beyond the recorded gitlink to create "+" drift.
    sub = fixture / "modules" / "alpha"
    (sub / "tracked.txt").write_text("drifted\n", encoding="utf-8")
    _git(sub, "add", "tracked.txt")
    _git(sub, "commit", "-q", "-m", "drift commit")
    head = _git(sub, "rev-parse", "HEAD").stdout.strip()
    base = _git(sub, "rev-parse", "HEAD~1").stdout.strip()
    _git(sub, "update-ref", "refs/remotes/origin/main", base)

    # Point the script's REPO at the fixture via a thin runner.
    runner = tmp_path / "run_drift.py"
    runner.write_text(
        textwrap.dedent(
            f"""\
            import sys
            from pathlib import Path
            source = Path(r"{GITLINK_DRIFT}").read_text()
            source = source.replace(
                "REPO = Path(__file__).resolve().parents[2]",
                "REPO = Path(r'{fixture}')",
            )
            ns = {{"__name__": "__main__", "__file__": r"{GITLINK_DRIFT}"}}
            sys.argv = ["gitlink-drift-protect.py", "--fix", "--json"]
            exec(compile(source, r"{GITLINK_DRIFT}", "exec"), ns)
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python3", str(runner)],
        cwd=fixture,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    combined = result.stdout + "\n" + result.stderr
    harness.assert_no_publication_effects()
    assert "managed_remediation_entrypoint" in result.stdout, combined
    assert "current_oid" in result.stdout
    assert "target_oid" in result.stdout
    assert "bin/gac/clone-lifecycle.py integrate" in result.stdout
    assert head[:7] in result.stdout or head in result.stdout
    assert "clone-lifecycle.py integrate" not in harness.events()


def test_sync_submodules_detection_only_no_push(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    parent = _make_parent_with_submodule(tmp_path)
    # Create an unpushed commit inside the submodule checkout.
    sub = parent / "modules" / "alpha"
    (sub / "tracked.txt").write_text("ahead\n", encoding="utf-8")
    _git(sub, "add", "tracked.txt")
    _git(sub, "commit", "-q", "-m", "ahead local")
    # Point a fake origin/main behind HEAD so detection sees unpushed commits.
    head = _git(sub, "rev-parse", "HEAD").stdout.strip()
    parent_commit = _git(sub, "rev-parse", "HEAD~1").stdout.strip()
    _git(sub, "update-ref", "refs/remotes/origin/main", parent_commit)
    assert head != parent_commit

    # Copy script into fixture? Script resolves WORKSPACE_ROOT from its own location.
    # Invoke production script with cwd=parent by temporarily using env and a wrapper
    # that cds — simplest: run via bash -c with rewritten root by copying script.
    script_copy = tmp_path / "sync-submodules.sh"
    text = SYNC_SUBMODULES.read_text(encoding="utf-8")
    # Force WORKSPACE_ROOT to parent for isolation.
    text = text.replace(
        'WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"',
        f'WORKSPACE_ROOT="{parent}"',
    )
    script_copy.write_text(text, encoding="utf-8")

    result = subprocess.run(
        ["bash", str(script_copy)],
        cwd=parent,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode != 0, combined
    assert "未推送" in combined or "unpushed" in combined.lower() or "未推" in combined
    harness.assert_no_publication_effects()


def test_sync_submodules_push_verification_only_no_push(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)
    parent = _make_parent_with_submodule(tmp_path)
    sub = parent / "modules" / "alpha"
    # Ensure submodule is on a named branch with upstream behind HEAD.
    branch = _git(sub, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch == "HEAD":
        _git(sub, "checkout", "-q", "-B", "main")
        branch = "main"
    (sub / "tracked.txt").write_text("ahead-push-script\n", encoding="utf-8")
    _git(sub, "add", "tracked.txt")
    _git(sub, "commit", "-q", "-m", "ahead for sync-push")
    parent_commit = _git(sub, "rev-parse", "HEAD~1").stdout.strip()
    _git(sub, "update-ref", f"refs/remotes/origin/{branch}", parent_commit)
    _git(sub, "branch", f"--set-upstream-to=origin/{branch}", branch)

    result = subprocess.run(
        ["bash", str(SYNC_SUBMODULES_PUSH)],
        cwd=parent,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode != 0, combined
    assert "verification-only" in combined or "不 push" in combined or "pending=" in combined
    harness.assert_no_publication_effects()


def test_wait_and_bump_cockpit_validate_readonly_and_default_blocked(tmp_path: Path) -> None:
    harness = PublicationEffectHarness(tmp_path)

    validate = subprocess.run(
        ["bash", str(WAIT_AND_BUMP), "--validate"],
        cwd=ROOT,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert "validate" in (validate.stdout + validate.stderr).lower()
    harness.assert_no_publication_effects()

    blocked = subprocess.run(
        ["bash", str(WAIT_AND_BUMP)],
        cwd=ROOT,
        env=harness.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined = blocked.stdout + "\n" + blocked.stderr
    assert blocked.returncode != 0
    assert "PUBLICATION_OWNER_REQUIRED" in combined
    harness.assert_no_publication_effects()


def test_none_of_six_sources_invoke_integrate_or_push_writers() -> None:
    surfaces = [
        GAC_WORKTREE,
        GIT_RETRY,
        GITLINK_DRIFT,
        SYNC_SUBMODULES,
        SYNC_SUBMODULES_PUSH,
        WAIT_AND_BUMP,
    ]
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        # Must not shell-out to integrate. Quoted entrypoint constants / replay text are OK.
        for line in text.splitlines():
            stripped = line.strip()
            if "clone-lifecycle" not in stripped or stripped.startswith("#"):
                continue
            allowed = (
                "MANAGED_REMEDIATION_ENTRYPOINT" in stripped
                or "entrypoint" in stripped.lower()
                or "instruction=" in stripped
                or "replay" in stripped.lower()
                or re.search(r'''['"].*clone-lifecycle.*['"]''', stripped)
            )
            assert allowed, f"unexpected clone-lifecycle invocation in {path.name}: {stripped}"
        if path == GAC_WORKTREE:
            assert "gh pr create" not in text
            assert "git-retry.sh\" push" not in text
            assert 'git-retry.sh" push' not in text
            assert "git rebase origin/main" not in text
            assert "MANAGED_SUCCESSOR_REQUIRED" in text
        if path in {SYNC_SUBMODULES, SYNC_SUBMODULES_PUSH}:
            assert "git push" not in text
            assert "--no-verify" not in text
        if path == GIT_RETRY:
            assert "PUBLICATION_OWNER_REQUIRED" in text
        if path == WAIT_AND_BUMP:
            assert "PUBLICATION_OWNER_REQUIRED" in text
            assert "--validate" in text
            assert "git push" not in text
        if path == GITLINK_DRIFT:
            assert "try_auto_push" not in text
            assert "MANAGED_REMEDIATION_ENTRYPOINT" in text
