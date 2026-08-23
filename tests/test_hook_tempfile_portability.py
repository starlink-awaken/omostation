from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _write_executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _bsd_mktemp_shim(path: Path) -> None:
    """Emulate BSD mktemp: only a trailing X run is a template."""
    _write_executable(
        path,
        "#!/bin/sh\n"
        "set -eu\n"
        "template=$1\n"
        "case \"$template\" in\n"
        "  *XXXXXX) path=\"${template%XXXXXX}$$\" ;;\n"
        "  *) path=$template ;;\n"
        "esac\n"
        "if ! (set -C; : > \"$path\") 2>/dev/null; then exit 1; fi\n"
        "printf '%s\\n' \"$path\" >> \"$MKTEMP_LOG\"\n"
        "printf '%s\\n' \"$path\"\n",
    )


def _assert_two_unique_cleaned_paths(log: Path) -> None:
    paths = [Path(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(paths) == 2
    assert len(set(paths)) == 2
    assert all(not path.exists() for path in paths)


def _communicate(
    processes: list[subprocess.Popen[str]],
) -> list[tuple[int, str, str]]:
    results = []
    for proc in processes:
        stdout, stderr = proc.communicate(timeout=15)
        results.append((proc.returncode, stdout, stderr))
    return results


def _release_barrier(barrier: Path, *, expected: int = 2) -> int:
    deadline = time.monotonic() + 2
    arrivals = 0
    while time.monotonic() < deadline:
        arrivals = sum(path.name != "release" for path in barrier.iterdir())
        if arrivals >= expected:
            break
        time.sleep(0.01)
    (barrier / "release").touch()
    return arrivals


def test_pre_push_failure_receipts_are_concurrency_safe_on_bsd_mktemp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "feature")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "tracked.txt").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "base")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", head)

    hook = repo / ".githooks" / "pre-push"
    hook.parent.mkdir()
    shutil.copy2(ROOT / ".githooks" / "pre-push", hook)
    _write_executable(repo / "bin/ssot/sync-submodules-push.sh", "#!/bin/sh\nexit 0\n")
    for relative in (
        "bin/ssot/submodule-reachability-gate.py",
        "bin/gac/ci-local-fast.py",
        "bin/gac/check-submodule-pointer-drift.py",
        "bin/gac/swarm-discipline-cli.py",
        "bin/gac/mass-deletion-gate.py",
    ):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    _write_executable(
        repo / "bin/gac/managed-python",
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *ci-local-fast.py*)\n"
        "    : > \"$BARRIER_DIR/$$\"\n"
        "    while [ ! -f \"$BARRIER_DIR/release\" ]; do sleep 0.01; done\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
    )

    fake_bin = tmp_path / "fake-bin"
    _bsd_mktemp_shim(fake_bin / "mktemp")
    hook_tmp = tmp_path / "hook-tmp"
    hook_tmp.mkdir()
    barrier = tmp_path / "barrier"
    barrier.mkdir()
    log = tmp_path / "mktemp.log"
    env = os.environ.copy()
    env.update(
        {
            "AGENT_ID": "",
            "BARRIER_DIR": str(barrier),
            "MKTEMP_LOG": str(log),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "TMPDIR": str(hook_tmp),
        }
    )
    push_line = f"refs/heads/feature {head} refs/heads/feature {head}\n"
    push_input = tmp_path / "push-input"
    push_input.write_text(push_line, encoding="utf-8")

    with push_input.open(encoding="utf-8") as first_stdin, push_input.open(
        encoding="utf-8"
    ) as second_stdin:
        first = subprocess.Popen(
            ["bash", str(hook)],
            cwd=repo,
            env=env,
            stdin=first_stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        second = subprocess.Popen(
            ["bash", str(hook)],
            cwd=repo,
            env=env,
            stdin=second_stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        arrivals = _release_barrier(barrier)
        results = _communicate([first, second])

    assert arrivals == 2, results
    assert all(result[0] == 0 for result in results), results
    _assert_two_unique_cleaned_paths(log)


def test_swarm_git_failure_receipts_are_concurrency_safe_on_bsd_mktemp(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    wrapper = repo / "bin/gac/swarm-git"
    wrapper.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "bin/gac/swarm-git", wrapper)
    (repo / "bin/gac/ci-local-fast.py").touch()
    (repo / "bin/gac/swarm-discipline-cli.py").touch()

    fake_bin = tmp_path / "fake-bin"
    _bsd_mktemp_shim(fake_bin / "mktemp")
    _write_executable(
        fake_bin / "git",
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = rev-parse ] && [ \"${2:-}\" = --show-toplevel ]; then\n"
        "  printf '%s\\n' \"$FAKE_GIT_ROOT\"\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        fake_bin / "python3",
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *ci-local-fast.py*)\n"
        "    : > \"$BARRIER_DIR/$$\"\n"
        "    while [ ! -f \"$BARRIER_DIR/release\" ]; do sleep 0.01; done\n"
        "    exit 0\n"
        "    ;;\n"
        "  *swarm-discipline-cli.py*) echo '{\"ok\": true}'; exit 0 ;;\n"
        "esac\n"
        "exit 0\n",
    )

    hook_tmp = tmp_path / "hook-tmp"
    hook_tmp.mkdir()
    barrier = tmp_path / "barrier"
    barrier.mkdir()
    log = tmp_path / "mktemp.log"
    env = os.environ.copy()
    env.update(
        {
            "AGENT_ID": "",
            "BARRIER_DIR": str(barrier),
            "FAKE_GIT_ROOT": str(repo),
            "HOME": str(tmp_path / "home"),
            "MKTEMP_LOG": str(log),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SWARM_GIT_DEPTH": "0",
            "TMPDIR": str(hook_tmp),
        }
    )

    first = subprocess.Popen(
        ["bash", str(wrapper), "push", "--no-verify"],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        ["bash", str(wrapper), "push", "--no-verify"],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    arrivals = _release_barrier(barrier)
    results = _communicate([first, second])

    assert arrivals == 2, results
    assert all(result[0] == 0 for result in results), results
    _assert_two_unique_cleaned_paths(log)
