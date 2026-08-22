from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _write_executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _policy_fixture(tmp_path: Path, *, shim: bool) -> tuple[Path, dict[str, str], Path]:
    repo = tmp_path / ("shim-repo" if shim else "swarm-repo")
    script_name = "git-shim" if shim else "swarm-git"
    script = repo / "bin/gac" / script_name
    script.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "bin/gac" / script_name, script)

    fake_bin = tmp_path / ("shim-bin" if shim else "swarm-bin")
    log = tmp_path / ("shim-git.log" if shim else "swarm-git.log")
    _write_executable(
        fake_bin / "git",
        "#!/bin/sh\n"
        "original=$*\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -C|-c|--git-dir|--work-tree|--namespace|--config-env) shift 2 ;;\n"
        "    --git-dir=*|--work-tree=*|--namespace=*|--config-env=*|--exec-path=*|--bare|--no-pager|--paginate|--literal-pathspecs|--glob-pathspecs|--noglob-pathspecs|--icase-pathspecs|--no-optional-locks|--no-replace-objects) shift ;;\n"
        "    --) shift ;;\n"
        "    -*) shift ;;\n"
        "    *) break ;;\n"
        "  esac\n"
        "done\n"
        "case \"${1:-} ${2:-}\" in\n"
        "  'rev-parse --show-toplevel') printf '%s\\n' \"$FAKE_GIT_ROOT\"; exit 0 ;;\n"
        "  'rev-parse --abbrev-ref') printf '%s\\n' \"$FAKE_GIT_BRANCH\"; exit 0 ;;\n"
        "esac\n"
        "if [ \"${1:-}\" = config ] && [ \"${2:-}\" = --get ] && "
        "[ \"${3:-}\" = \"alias.${FAKE_GIT_ALIAS_NAME:-}\" ]; then\n"
        "  printf '%s\\n' '!git merge origin/main'\n"
        "  exit 0\n"
        "fi\n"
        "printf '%s\\n' \"$original\" >> \"$FAKE_GIT_LOG\"\n"
        "exit 0\n",
    )
    env = os.environ.copy()
    env.update(
        {
            "AGENT_ID": "actor-1" if shim else "",
            "FAKE_GIT_BRANCH": "agent/actor-1/attempt-1",
            "FAKE_GIT_LOG": str(log),
            "FAKE_GIT_ROOT": str(repo),
            "HOME": str(tmp_path / "home"),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SWARM_GIT_DEPTH": "0",
        }
    )
    return script, env, log


def _run(script: Path, env: dict[str, str], *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *argv],
        cwd=script.parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("shim", [False, True], ids=["swarm-git", "git-shim-fallback"])
def test_immutable_writer_blocks_history_rewrites_and_upstream_merges(
    tmp_path: Path,
    shim: bool,
) -> None:
    script, env, _ = _policy_fixture(tmp_path, shim=shim)
    blocked = (
        ("rebase", "origin/main"),
        ("merge", "origin/main"),
        ("pull", "origin", "main"),
        ("push", "--force", "origin", "HEAD"),
        ("push", "-f", "origin", "HEAD"),
        ("push", "--force-with-lease", "origin", "HEAD"),
        ("push", "--force-with-lease=agent/actor-1/attempt-1", "origin", "HEAD"),
        ("-C", ".", "merge", "origin/main"),
        ("-c", "advice.detachedHead=false", "pull", "origin", "main"),
        ("--git-dir=.git", "push", "--force", "origin", "HEAD"),
    )

    for argv in blocked:
        proc = _run(script, env, *argv)
        assert proc.returncode != 0, (argv, proc.stdout, proc.stderr)
        assert "immutable" in proc.stderr.lower(), (argv, proc.stderr)


@pytest.mark.parametrize("shim", [False, True], ids=["swarm-git", "git-shim-fallback"])
def test_immutable_writer_allows_abort_and_read_only_recovery(
    tmp_path: Path,
    shim: bool,
) -> None:
    script, env, log = _policy_fixture(tmp_path, shim=shim)

    for argv in (
        ("rebase", "--abort"),
        ("merge", "--abort"),
        ("-C", ".", "rebase", "--abort"),
        ("--git-dir=.git", "merge", "--abort"),
        ("status",),
    ):
        proc = _run(script, env, *argv)
        assert proc.returncode == 0, (argv, proc.stdout, proc.stderr)

    calls = log.read_text(encoding="utf-8").splitlines()
    assert "rebase --abort" in calls
    assert "merge --abort" in calls
    assert "-C . rebase --abort" in calls
    assert "--git-dir=.git merge --abort" in calls
    assert "status" in calls


@pytest.mark.parametrize("shim", [False, True], ids=["swarm-git", "git-shim-fallback"])
def test_legacy_work_branch_keeps_non_rewriting_merge_and_pull(
    tmp_path: Path,
    shim: bool,
) -> None:
    script, env, log = _policy_fixture(tmp_path, shim=shim)
    env["FAKE_GIT_BRANCH"] = "work/legacy"

    for argv in (("merge", "origin/main"), ("pull", "--ff-only", "origin", "main")):
        proc = _run(script, env, *argv)
        assert proc.returncode == 0, (argv, proc.stdout, proc.stderr)

    calls = log.read_text(encoding="utf-8").splitlines()
    assert "merge origin/main" in calls
    assert "pull --ff-only origin main" in calls


def test_human_git_shim_preserves_circuit_breaker_for_writer_branch(tmp_path: Path) -> None:
    script, env, log = _policy_fixture(tmp_path, shim=True)
    env.pop("AGENT_ID")

    for argv in (("merge", "origin/main"), ("push", "--force", "origin", "HEAD")):
        proc = _run(script, env, *argv)
        assert proc.returncode == 0, (argv, proc.stdout, proc.stderr)

    calls = log.read_text(encoding="utf-8").splitlines()
    assert "merge origin/main" in calls
    assert "push --force origin HEAD" in calls


@pytest.mark.parametrize("shim", [False, True], ids=["swarm-git", "git-shim-fallback"])
def test_immutable_writer_blocks_inline_and_configured_alias_dispatch(
    tmp_path: Path,
    shim: bool,
) -> None:
    script, env, _ = _policy_fixture(tmp_path, shim=shim)

    inline = _run(
        script,
        env,
        "-c",
        "alias.unsafe=!git merge origin/main",
        "unsafe",
    )
    assert inline.returncode != 0, (inline.stdout, inline.stderr)
    assert "immutable" in inline.stderr.lower()

    env["ALIAS_BODY"] = "!git merge origin/main"
    config_env = _run(
        script,
        env,
        "--config-env=alias.unsafe=ALIAS_BODY",
        "unsafe",
    )
    assert config_env.returncode != 0, (config_env.stdout, config_env.stderr)
    assert "immutable" in config_env.stderr.lower()

    env["FAKE_GIT_ALIAS_NAME"] = "unsafe"
    configured = _run(script, env, "unsafe")
    assert configured.returncode != 0, (configured.stdout, configured.stderr)
    assert "immutable" in configured.stderr.lower()
