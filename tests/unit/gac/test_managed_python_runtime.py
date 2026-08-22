from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "bin" / "gac" / "managed-python"


def _env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(overrides)
    return env


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


def test_managed_python_probe_emits_replayable_stdlib_receipt() -> None:
    proc = subprocess.run(
        [str(RUNNER), "probe", "--profile", "stdlib", "--json"],
        cwd=ROOT,
        env=_env(OMO_MANAGED_PYTHON=sys.executable, PATH="/usr/bin:/bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt == {
        "schema": "managed-python-runtime-receipt/v1",
        "profile": "stdlib",
        "provider": "explicit",
        "executable": str(Path(sys.executable).resolve()),
        "python_version": list(sys.version_info[:3]),
        "capabilities": ["stdlib"],
    }


def test_managed_python_run_preserves_script_arguments(tmp_path: Path) -> None:
    script = tmp_path / "echo_args.py"
    script.write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(RUNNER),
            "run",
            "--profile",
            "stdlib",
            "--",
            str(script),
            "alpha",
            "two words",
        ],
        cwd=ROOT,
        env=_env(OMO_MANAGED_PYTHON=sys.executable, PATH="/usr/bin:/bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == ["alpha", "two words"]


def test_managed_python_rejects_an_unsupported_explicit_runtime(tmp_path: Path) -> None:
    unsupported = tmp_path / "python3"
    _write_executable(
        unsupported,
        "#!/bin/sh\n"
        "echo '/managed/python|3|9|18|0'\n",
    )

    proc = subprocess.run(
        [str(RUNNER), "probe", "--profile", "stdlib", "--json"],
        cwd=ROOT,
        env=_env(OMO_MANAGED_PYTHON=str(unsupported), PATH="/usr/bin:/bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "Python 3.11+" in proc.stderr


def test_pyyaml_profile_can_use_the_uv_fallback(tmp_path: Path) -> None:
    isolated = tmp_path / "runtime"
    runner = isolated / "bin" / "gac" / "managed-python"
    runner.parent.mkdir(parents=True)
    shutil.copy2(RUNNER, runner)
    fake_bin = tmp_path / "fake-bin"
    _write_executable(
        fake_bin / "uv",
        "#!/bin/sh\n"
        "while [ \"$#\" -gt 0 ] && [ \"$1\" != python ]; do shift; done\n"
        "[ \"$#\" -gt 0 ] && shift\n"
        f"exec {sys.executable!r} \"$@\"\n",
    )

    proc = subprocess.run(
        [str(runner), "probe", "--profile", "pyyaml", "--json"],
        cwd=isolated,
        env=_env(PATH=f"{fake_bin}:/usr/bin:/bin", OMO_MANAGED_PYTHON=""),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["provider"] == "uv"
    assert receipt["capabilities"] == ["stdlib", "pyyaml"]


def test_tracked_hooks_execute_python_calls_through_the_managed_runtime(tmp_path: Path) -> None:
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

    hooks = repo / ".githooks"
    hooks.mkdir()
    shutil.copy2(ROOT / ".githooks" / "pre-commit", hooks / "pre-commit")
    shutil.copy2(ROOT / ".githooks" / "pre-push", hooks / "pre-push")
    log = tmp_path / "managed-python.log"
    _write_executable(
        repo / "bin" / "gac" / "managed-python",
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$MANAGED_PYTHON_LOG\"\n"
        "case \"$*\" in\n"
        "  *check-submodule-pointer-drift.py*)\n"
        "    [ \"${MANAGED_PYTHON_FAIL_DRIFT:-}\" = 1 ] && exit 7\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
    )

    pre_commit_scripts = (
        "bin/gac/agent-clone.py",
        "bin/gac-hygiene-check.py",
        "bin/gac-local-gate.py",
        "bin/ssot-guardian.py",
        "bin/gac-audit-engine.py",
        "bin/gac/mass-deletion-gate.py",
        "bin/ssot/conflict-marker-check.py",
    )
    for relative in pre_commit_scripts:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (repo / "bin/gac-hygiene-check.py").chmod(0o755)

    hook_tmp = tmp_path / "hook-tmp"
    hook_tmp.mkdir()
    env = _env(
        MANAGED_PYTHON_LOG=str(log),
        MANAGED_PYTHON_FAIL_DRIFT="",
        AGENT_ID="managed-runtime-test",
        TMPDIR=str(hook_tmp),
    )
    pre_commit = subprocess.run(
        ["bash", str(hooks / "pre-commit")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pre_commit.returncode == 0, pre_commit.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == len(pre_commit_scripts)
    assert sum("run --profile pyyaml --" in call for call in calls) == 2
    assert sum("run --profile stdlib --" in call for call in calls) == 5

    log.write_text("", encoding="utf-8")
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
    push_line = f"refs/heads/feature {head} refs/heads/feature {head}\n"
    pre_push = subprocess.run(
        ["bash", str(hooks / "pre-push")],
        cwd=repo,
        env=env,
        input=push_line,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pre_push.returncode == 0, pre_push.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 4
    assert sum("run --profile pyyaml --" in call for call in calls) == 1
    assert sum("run --profile stdlib --" in call for call in calls) == 3
    assert any("run --profile pyyaml --" in call and "ci-local-fast.py" in call for call in calls)

    log.write_text("", encoding="utf-8")
    skip_env = {
        **env,
        "CI_LOCAL_SKIP": "1",
        "SWARM_ESCAPE_ID": "managed-runtime-test",
        "MANAGED_PYTHON_FAIL_DRIFT": "1",
    }
    pre_push = subprocess.run(
        ["bash", str(hooks / "pre-push")],
        cwd=repo,
        env=skip_env,
        input=push_line,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pre_push.returncode == 0, pre_push.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 6
    assert sum("run --profile pyyaml --" in call for call in calls) == 1
    assert sum("run --profile stdlib --" in call for call in calls) == 5
    assert any("run --profile stdlib -- - " in call for call in calls)
    assert any("swarm-discipline-cli.py" in call for call in calls)


def test_clone_make_target_executes_the_managed_stdlib_profile(tmp_path: Path) -> None:
    shutil.copy2(ROOT / "Makefile", tmp_path / "Makefile")
    log = tmp_path / "managed-python.log"
    _write_executable(
        tmp_path / "bin" / "gac" / "managed-python",
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$MANAGED_PYTHON_LOG\"\n",
    )

    proc = subprocess.run(
        ["make", "clone-snapshot", "AGENT_ID=probe"],
        cwd=tmp_path,
        env=_env(MANAGED_PYTHON_LOG=str(log), HOME=str(tmp_path / "home")),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    call = log.read_text(encoding="utf-8").strip()
    assert call.startswith("run --profile stdlib -- bin/gac/clone-lifecycle.py snapshot")
