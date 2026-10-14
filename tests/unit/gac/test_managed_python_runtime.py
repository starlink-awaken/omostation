from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import venv
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
        "executable": sys.executable,
        "python_version": list(sys.version_info[:3]),
        "capabilities": ["stdlib"],
    }


def test_workspace_venv_receipt_and_run_preserve_the_invocation_context(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    runner = root / "bin" / "gac" / "managed-python"
    runner.parent.mkdir(parents=True)
    shutil.copy2(RUNNER, runner)
    runtime = root / ".venv"
    venv.EnvBuilder(with_pip=False, symlinks=True, system_site_packages=True).create(runtime)
    executable = runtime / "bin" / "python"
    assert executable.is_symlink(), "regression requires a real virtualenv symlink"
    purelib = subprocess.run(
        [str(executable), "-B", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    Path(purelib, "yaml.py").write_text("# selector capability fixture\n", encoding="utf-8")
    Path(purelib, "managed_python_venv_dependency.py").write_text(
        "VALUE = 'venv-only-managed-python-dependency'\n", encoding="utf-8"
    )

    probe = subprocess.run(
        [str(runner), "probe", "--profile", "pyyaml", "--json"],
        cwd=root,
        env=_env(PATH="/usr/bin:/bin", OMO_MANAGED_PYTHON=""),
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
    receipt = json.loads(probe.stdout)
    assert receipt["provider"] == "workspace-venv"
    assert receipt["executable"] == str(executable)
    replay = subprocess.run(
        [
            str(runner), "run", "--profile", "pyyaml", "--", "-B", "-c",
            "import managed_python_venv_dependency as dep; print(dep.VALUE)",
        ],
        cwd=root,
        env=_env(PATH="/usr/bin:/bin", OMO_MANAGED_PYTHON=""),
        capture_output=True,
        text=True,
        check=False,
    )
    assert replay.returncode == 0, replay.stderr
    assert replay.stdout.strip() == "venv-only-managed-python-dependency"
    control = subprocess.run(
        [str(executable.resolve(strict=True)), "-B", "-c", "import managed_python_venv_dependency"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert control.returncode != 0
    assert "ModuleNotFoundError" in control.stderr


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
        "  *check-submodule-rewind.py*)\n"
        "    [ \"${MANAGED_PYTHON_FAIL_REWIND:-}\" = 1 ] && exit 7\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
    )
    shutil.copy2(ROOT / "bin" / "gac" / "hook-runner.sh", repo / "bin" / "gac" / "hook-runner.sh")
    hook_manifest = repo / ".omo" / "_truth" / "registry" / "hook-manifest.yaml"
    hook_manifest.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".omo" / "_truth" / "registry" / "hook-manifest.yaml", hook_manifest)

    pre_commit_scripts = (
        "bin/gac/agent-clone.py",
        "bin/gac/check-branch-naming.py",
        "bin/gac/check-conflict-markers.py",
        "bin/gac/mass-deletion-gate.py",
        "bin/gac/check-runtime-artifacts.py",
        "bin/gac/debt-directory-guard.py",
        "bin/gac/submodule-guard.py",
        "bin/gac/gac-hygiene-check.py",
    )
    for relative in pre_commit_scripts:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (repo / "bin/gac/gac-hygiene-check.py").chmod(0o755)

    hook_tmp = tmp_path / "hook-tmp"
    hook_tmp.mkdir()
    env = _env(
        MANAGED_PYTHON_LOG=str(log),
        MANAGED_PYTHON_FAIL_REWIND="",
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
    assert sum("run --profile pyyaml --" in call for call in calls) == 1
    assert sum("run --profile stdlib --" in call for call in calls) == 7

    log.write_text("", encoding="utf-8")
    _write_executable(repo / "bin/gac/pre-push-network-check.sh", "#!/bin/sh\nexit 0\n")
    _write_executable(repo / "bin/ssot/sync-submodules-push.sh", "#!/bin/sh\nexit 0\n")
    for relative in (
        "bin/ssot/submodule-reachability-gate.py",
        "bin/gac/guard-direct-push-main.py",
        "bin/gac/check-submodule-rewind.py",
        "bin/gac/remote-hygiene-check.py",
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
    assert len(calls) == 6
    assert sum("run --profile pyyaml --" in call for call in calls) == 2
    assert sum("run --profile stdlib --" in call for call in calls) == 4
    assert any("run --profile pyyaml --" in call and "check-submodule-rewind.py" in call for call in calls)

    log.write_text("", encoding="utf-8")
    fail_env = {
        **env,
        "MANAGED_PYTHON_FAIL_REWIND": "1",
    }
    pre_push = subprocess.run(
        ["bash", str(hooks / "pre-push")],
        cwd=repo,
        env=fail_env,
        input=push_line,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pre_push.returncode == 1
    assert "[gitlink-ancestry] failed" in pre_push.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 6
    assert sum("run --profile pyyaml --" in call for call in calls) == 2
    assert sum("run --profile stdlib --" in call for call in calls) == 4
    assert any("run --profile pyyaml --" in call and "check-submodule-rewind.py" in call for call in calls)


def test_clone_make_target_executes_the_managed_stdlib_profile(tmp_path: Path) -> None:
    shutil.copy2(ROOT / "Makefile", tmp_path / "Makefile")
    log = tmp_path / "managed-python.log"
    _write_executable(
        tmp_path / "bin" / "gac" / "managed-python",
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$MANAGED_PYTHON_LOG\"\n",
    )

    proc = subprocess.run(
        [
            "make",
            "clone-snapshot",
            "AGENT_ID=probe",
            "DELIVERY_ATTEMPT_ID=managed-python-test-01",
        ],
        cwd=tmp_path,
        env=_env(MANAGED_PYTHON_LOG=str(log), HOME=str(tmp_path / "home")),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    call = log.read_text(encoding="utf-8").strip()
    assert call.startswith("run --profile stdlib -- bin/gac/clone-lifecycle.py snapshot")
