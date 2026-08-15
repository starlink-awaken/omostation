"""Real-repository integration coverage for PASW claim fail-closed behavior."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"
CORE = ROOT / "lib" / "pasw-core.sh"
SUBMODULES = ("modules/alpha", "modules/beta")


def _git(
    path: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "pasw@test.invalid")
    _git(path, "config", "user.name", "PASW test")
    (path / "tracked.txt").write_text("initial\n")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-q", "-m", "initial")


def _make_parent_with_two_submodules(
    tmp_path: Path, submodule_paths: tuple[str, ...] = SUBMODULES
) -> Path:
    parent = tmp_path / "parent"
    parent.mkdir()
    _init_repo(parent)
    (parent / ".gitignore").write_text(".subtrees/\n")
    _git(parent, "add", ".gitignore")
    _git(parent, "commit", "-q", "-m", "ignore PASW worktrees")
    for submodule_path in submodule_paths:
        child = tmp_path / f"child-{submodule_path.replace('/', '-').replace(' ', '-')}"
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
                submodule_path,
            ],
            check=True,
        )
    _git(parent, "commit", "-q", "-am", "add two submodules")
    _git(
        parent,
        "remote",
        "add",
        "origin",
        "https://github.com/starlink-awaken/omostation.git",
    )
    _git(parent, "update-ref", "refs/remotes/origin/main", "HEAD")
    return parent


def _write_git_wrapper(tmp_path: Path) -> Path:
    real_git = shutil.which("git")
    assert real_git
    wrapper_dir = tmp_path / "git-wrapper"
    wrapper_dir.mkdir(exist_ok=True)
    (wrapper_dir / "git").write_text(
        "#!/bin/sh\n"
        'case " $* " in *" fetch "*) exit 0 ;; esac\n'
        'if [ "${PASW_FAIL_SUBMODULE_INIT:-}" = "1" ] && [ "$1" = "submodule" ] && [ "$2" = "update" ] && [ "$3" = "--init" ]; then\n'
        '  echo "injected bulk submodule failure" >&2\n'
        "  exit 73\n"
        "fi\n"
        'if [ "${PASW_FAIL_BETA_ONCE:-}" = "1" ] && [ "$1" = "worktree" ] && [ "$2" = "add" ] && [ "$(basename "$PWD")" = "beta" ] && [ ! -e "${PASW_FAILURE_MARKER:?}" ]; then\n'
        '  : > "$PASW_FAILURE_MARKER"\n'
        '  echo "injected beta PASW failure" >&2\n'
        "  exit 74\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n',
    )
    (wrapper_dir / "git").chmod(0o755)
    return wrapper_dir


def _make_bump_fast_repo(
    tmp_path: Path,
) -> tuple[Path, Path, str, str]:
    parent = tmp_path / "bump-parent"
    child = tmp_path / "bump-child"
    parent.mkdir()
    child.mkdir()
    _init_repo(parent)
    _init_repo(child)
    old_sha = _git(child, "rev-parse", "HEAD").stdout.strip()

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
    _git(
        parent,
        "config",
        "--file",
        ".gitmodules",
        "submodule.modules/alpha.url",
        "https://github.com/example/alpha.git",
    )
    registry = parent / "docs" / "project-registry.yaml"
    registry.parent.mkdir()
    registry.write_text(
        'projects:\n  alpha:\n    layer: "L2"\n    version: "1.0.0"\n',
        encoding="utf-8",
    )
    _git(parent, "add", ".gitmodules", "modules/alpha", "docs/project-registry.yaml")
    _git(parent, "commit", "-q", "-m", "pin alpha")

    (child / "tracked.txt").write_text("remote main\n", encoding="utf-8")
    _git(child, "add", "tracked.txt")
    _git(child, "commit", "-q", "-m", "advance main")
    new_sha = _git(child, "rev-parse", "HEAD").stdout.strip()
    return parent, child, old_sha, new_sha


def _write_bump_fast_wrappers(tmp_path: Path) -> Path:
    real_git = shutil.which("git")
    assert real_git
    wrapper_dir = tmp_path / "bump-wrappers"
    wrapper_dir.mkdir()
    (wrapper_dir / "git").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "ls-remote" ]; then\n'
        '  [ "${BUMP_FAIL_LS_REMOTE:-0}" = "1" ] && exit 71\n'
        '  printf "%s\\trefs/heads/main\\n" "${BUMP_REMOTE_TIP:?}"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "update-index" ] && [ "${BUMP_FAIL_UPDATE:-0}" = "1" ]; then\n'
        "  exit 72\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8",
    )
    (wrapper_dir / "git").chmod(0o755)
    (wrapper_dir / "gh").write_text(
        "#!/bin/sh\n"
        '[ "${BUMP_FAIL_GH:-0}" = "1" ] && exit 73\n'
        'case "$*" in\n'
        '  *pyproject.toml*) printf "%s\\n" "${BUMP_PYPROJECT_B64:?}" ;;\n'
        "  *) exit 74 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    (wrapper_dir / "gh").chmod(0o755)
    return wrapper_dir


def _run_bump_fast(
    parent: Path,
    tmp_path: Path,
    new_sha: str,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], float]:
    wrapper_dir = _write_bump_fast_wrappers(tmp_path)
    encoded_pyproject = base64.b64encode(
        b'[project]\nname = "alpha"\nversion = "2.0.0"\n'
    ).decode()
    env = {
        **os.environ,
        "WS_ROOT": str(parent),
        "WS_PARENT": str(tmp_path),
        "PATH": f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}",
        "BUMP_REMOTE_TIP": new_sha,
        "BUMP_PYPROJECT_B64": encoded_pyproject,
        **(extra_env or {}),
    }
    started = time.monotonic()
    result = subprocess.run(
        ["bash", str(SCRIPT), "bump-fast", "modules/alpha", *args],
        cwd=parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result, time.monotonic() - started


def _index_sha(parent: Path, path: str = "modules/alpha") -> str:
    return _git(parent, "ls-files", "-s", "--", path).stdout.split()[1]


def _run_claim(
    parent: Path,
    tmp_path: Path,
    session: str,
    *,
    extra_env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    non_repo_cwd = tmp_path / "not-a-repository"
    non_repo_cwd.mkdir(exist_ok=True)
    wrapper_dir = _write_git_wrapper(tmp_path)
    env = {
        **os.environ,
        "WS_ROOT": str(parent),
        "WS_PARENT": str(tmp_path / "worktrees"),
        "PATH": f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}",
        "GIT_ALLOW_PROTOCOL": "file",
        **(extra_env or {}),
    }
    Path(env["WS_PARENT"]).mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(SCRIPT), "claim", session],
        cwd=cwd or parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _run_release(
    parent: Path, tmp_path: Path, session: str
) -> subprocess.CompletedProcess[str]:
    wrapper_dir = _write_git_wrapper(tmp_path)
    env = {
        **os.environ,
        "WS_ROOT": str(parent),
        "WS_PARENT": str(tmp_path / "worktrees"),
        "PATH": f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}",
        "GIT_ALLOW_PROTOCOL": "file",
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "release", session],
        cwd=parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _run_list(parent: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    wrapper_dir = _write_git_wrapper(tmp_path)
    env = {
        **os.environ,
        "WS_ROOT": str(parent),
        "WS_PARENT": str(tmp_path / "worktrees"),
        "PATH": f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}",
        "GIT_ALLOW_PROTOCOL": "file",
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "list"],
        cwd=parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _worktree(tmp_path: Path, session: str) -> Path:
    return tmp_path / "worktrees" / f"ws-{session}"


def _init_root_worktree(parent: Path, wt: Path, session: str) -> None:
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
    subprocess.run(
        [
            "git",
            "-C",
            str(wt),
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--init",
        ],
        check=True,
    )


def _pasw_path(wt: Path, submodule: str) -> Path:
    return wt / ".subtrees" / Path(submodule).name


def _create_pasw(wt: Path, submodule: str, session: str) -> Path:
    pasw = _pasw_path(wt, submodule)
    pasw.parent.mkdir(exist_ok=True)
    sha = _git(wt / submodule, "rev-parse", "HEAD").stdout.strip()
    subprocess.run(
        [
            "git",
            "-C",
            str(wt / submodule),
            "worktree",
            "add",
            "-b",
            f"agent/{session}-{Path(submodule).name}",
            str(pasw),
            sha,
        ],
        check=True,
    )
    return pasw


def _assert_complete_pasw(
    parent: Path, wt: Path, submodule_paths: tuple[str, ...] = SUBMODULES
) -> None:
    for submodule in submodule_paths:
        pasw = _pasw_path(wt, submodule)
        assert pasw.is_dir(), f"missing PASW worktree: {pasw}"
        registrations = _git(wt / submodule, "worktree", "list", "--porcelain").stdout
        assert f"worktree {pasw}" in registrations
        expected = _git(parent, "rev-parse", f"HEAD:{submodule}").stdout.strip()
        assert _git(wt / submodule, "rev-parse", "HEAD").stdout.strip() == expected
        assert _git(pasw, "rev-parse", "HEAD").stdout.strip() == expected


def _worktree_git_dir(path: Path) -> Path:
    git_dir = Path(_git(path, "rev-parse", "--git-common-dir").stdout.strip())
    return git_dir if git_dir.is_absolute() else (path / git_dir).resolve()


def test_existing_root_worktree_is_repaired_with_all_pasw(tmp_path: Path) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)
    wt = _worktree(tmp_path, "existing")
    _init_root_worktree(parent, wt, "existing")

    result = _run_claim(parent, tmp_path, "existing")

    assert result.returncode == 0, result.stderr
    _assert_complete_pasw(parent, wt)


def test_partial_pasw_layout_is_repaired_on_claim(tmp_path: Path) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)
    wt = _worktree(tmp_path, "partial")
    _init_root_worktree(parent, wt, "partial")
    _create_pasw(wt, "modules/alpha", "partial")

    result = _run_claim(parent, tmp_path, "partial")

    assert result.returncode == 0, result.stderr
    _assert_complete_pasw(parent, wt)


def test_bulk_submodule_init_failure_fails_without_pasw(tmp_path: Path) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)

    result = _run_claim(
        parent, tmp_path, "bulk-fail", extra_env={"PASW_FAIL_SUBMODULE_INIT": "1"}
    )

    assert result.returncode != 0
    assert not (_worktree(tmp_path, "bulk-fail") / ".subtrees").exists()


def test_complete_claim_registers_matching_pasw_from_non_repo_cwd(
    tmp_path: Path,
) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)

    result = _run_claim(parent, tmp_path, "complete", cwd=tmp_path / "not-a-repository")
    wt = _worktree(tmp_path, "complete")

    assert result.returncode == 0, result.stderr
    _assert_complete_pasw(parent, wt)
    assert _git(wt, "status", "--porcelain").stdout == ""

    retry = _run_claim(parent, tmp_path, "complete", cwd=tmp_path / "not-a-repository")

    assert retry.returncode == 0, retry.stderr
    _assert_complete_pasw(parent, wt)


def test_claim_preserves_submodule_paths_with_spaces(tmp_path: Path) -> None:
    submodule_paths = ("modules/alpha", "modules/space alpha")
    parent = _make_parent_with_two_submodules(tmp_path, submodule_paths)

    result = _run_claim(parent, tmp_path, "space-path")
    wt = _worktree(tmp_path, "space-path")

    assert result.returncode == 0, result.stderr
    _assert_complete_pasw(parent, wt, submodule_paths)
    assert _git(wt, "status", "--porcelain").stdout == ""


def test_release_removes_spaced_pasw_worktree_and_registration(tmp_path: Path) -> None:
    submodule_paths = ("modules/alpha", "modules/space alpha")
    parent = _make_parent_with_two_submodules(tmp_path, submodule_paths)
    session = "space-release"
    claim = _run_claim(parent, tmp_path, session)
    wt = _worktree(tmp_path, session)
    pasw = _pasw_path(wt, "modules/space alpha")
    git_dir = _worktree_git_dir(wt / "modules/space alpha")
    registrations_before = _git(
        wt / "modules/space alpha", "worktree", "list", "--porcelain"
    ).stdout

    assert claim.returncode == 0, claim.stderr
    assert f"worktree {pasw}" in registrations_before
    release = _run_release(parent, tmp_path, session)

    assert release.returncode == 0, release.stderr + release.stdout
    assert not wt.exists()
    assert not pasw.exists()
    assert not git_dir.exists(), "PASW registration metadata must be removed"


def test_release_refuses_dirty_spaced_pasw_and_retains_worktree(tmp_path: Path) -> None:
    submodule_paths = ("modules/alpha", "modules/space alpha")
    parent = _make_parent_with_two_submodules(tmp_path, submodule_paths)
    session = "space-dirty"
    claim = _run_claim(parent, tmp_path, session)
    wt = _worktree(tmp_path, session)
    pasw = _pasw_path(wt, "modules/space alpha")
    (pasw / "untracked.txt").write_text("must remain\n")

    assert claim.returncode == 0, claim.stderr
    release = _run_release(parent, tmp_path, session)

    assert release.returncode != 0
    assert "拒绝释放" in release.stderr
    assert "PASW modules/space alpha has changes" in release.stderr
    assert wt.exists()
    assert (pasw / "untracked.txt").exists()


def test_pasw_core_has_no_legacy_destructive_cleanup() -> None:
    source = CORE.read_text()

    assert "pasw_cleanup()" not in source
    assert 'rm -rf "$sub_wt"' not in source


def test_list_displays_spaced_pasw_worktree(tmp_path: Path) -> None:
    submodule_paths = ("modules/alpha", "modules/space alpha")
    parent = _make_parent_with_two_submodules(tmp_path, submodule_paths)
    session = "space-list"
    claim = _run_claim(parent, tmp_path, session)

    assert claim.returncode == 0, claim.stderr
    listed = _run_list(parent, tmp_path)

    assert listed.returncode == 0, listed.stderr
    assert f"ws-{session}: alpha space alpha" in listed.stdout


def test_retry_repairs_pasw_after_a_partial_worktree_add_failure(
    tmp_path: Path,
) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)
    marker = tmp_path / "beta-failure-used"

    first = _run_claim(
        parent,
        tmp_path,
        "retry",
        extra_env={"PASW_FAIL_BETA_ONCE": "1", "PASW_FAILURE_MARKER": str(marker)},
    )
    wt = _worktree(tmp_path, "retry")
    assert first.returncode != 0
    assert marker.exists()
    assert _pasw_path(wt, "modules/alpha").is_dir()
    assert not _pasw_path(wt, "modules/beta").exists()

    retry = _run_claim(parent, tmp_path, "retry")

    assert retry.returncode == 0, retry.stderr
    _assert_complete_pasw(parent, wt)


def test_skip_submodule_init_is_explicit_root_only_degraded_mode(
    tmp_path: Path,
) -> None:
    parent = _make_parent_with_two_submodules(tmp_path)

    result = _run_claim(
        parent, tmp_path, "fast", extra_env={"SKIP_SUBMODULE_INIT": "1"}
    )
    wt = _worktree(tmp_path, "fast")

    assert result.returncode == 0, result.stderr
    assert not (wt / ".subtrees").exists()
    assert not (wt / "modules" / "alpha" / ".git").exists()
    assert "root worktree only" in result.stdout.lower()
    assert "pasw isolation not established" in result.stdout.lower()


def test_bump_fast_updates_only_root_index_and_registry_under_two_seconds(
    tmp_path: Path,
) -> None:
    parent, _child, old_sha, new_sha = _make_bump_fast_repo(tmp_path)
    child_head_before = _git(
        parent / "modules/alpha", "rev-parse", "HEAD"
    ).stdout.strip()

    result, elapsed = _run_bump_fast(parent, tmp_path, new_sha, "--latest-main")

    assert result.returncode == 0, result.stderr + result.stdout
    assert elapsed < 2, f"bump-fast local deterministic path took {elapsed:.3f}s"
    assert _index_sha(parent) == new_sha
    assert old_sha != new_sha
    assert (
        _git(parent / "modules/alpha", "rev-parse", "HEAD").stdout.strip()
        == child_head_before
    )
    assert 'version: "2.0.0"' in (parent / "docs/project-registry.yaml").read_text(
        encoding="utf-8"
    )
    assert "不替代 D2/D3" in result.stdout


def test_bump_fast_explicit_unreachable_sha_fails_without_mutation(
    tmp_path: Path,
) -> None:
    parent, _child, old_sha, new_sha = _make_bump_fast_repo(tmp_path)
    registry_before = (parent / "docs/project-registry.yaml").read_text(
        encoding="utf-8"
    )
    unreachable = "0" * 40

    result, _elapsed = _run_bump_fast(parent, tmp_path, new_sha, "--sha", unreachable)

    assert result.returncode != 0
    assert "远端 main 不可达" in result.stderr
    assert _index_sha(parent) == old_sha
    assert (parent / "docs/project-registry.yaml").read_text(
        encoding="utf-8"
    ) == registry_before


def test_bump_fast_version_lookup_failure_is_fail_closed(tmp_path: Path) -> None:
    parent, _child, old_sha, new_sha = _make_bump_fast_repo(tmp_path)
    registry_before = (parent / "docs/project-registry.yaml").read_text(
        encoding="utf-8"
    )

    result, _elapsed = _run_bump_fast(
        parent,
        tmp_path,
        new_sha,
        "--latest-main",
        extra_env={"BUMP_FAIL_GH": "1"},
    )

    assert result.returncode != 0
    assert "registry 与指针将保持未变" in result.stderr
    assert _index_sha(parent) == old_sha
    assert (parent / "docs/project-registry.yaml").read_text(
        encoding="utf-8"
    ) == registry_before


def test_bump_fast_explicit_current_tip_is_accepted(tmp_path: Path) -> None:
    parent, _child, _old_sha, new_sha = _make_bump_fast_repo(tmp_path)

    result, _elapsed = _run_bump_fast(parent, tmp_path, new_sha, "--sha", new_sha)

    assert result.returncode == 0, result.stderr + result.stdout
    assert _index_sha(parent) == new_sha
