from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "bin" / "gac" / "heartbeat-wrapper.sh"
OPERATING_RHYTHM = REPO_ROOT / ".omo" / "cron" / "operating-rhythm-crontab"
ROOT_GUARD_PREFIX = (
    'test -n "$OMO_WORKSPACE_ROOT" '
    '&& test "${OMO_WORKSPACE_ROOT#/}" != "$OMO_WORKSPACE_ROOT" '
    '&& test -d "$OMO_WORKSPACE_ROOT/.omo" '
    '&& cd "$OMO_WORKSPACE_ROOT" '
    "&& "
)


def _run_wrapper(
    workspace: Path,
    *command: str,
    job_name: str = "agent-workflow-status",
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    (workspace / ".omo").mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(workspace / "decoy-home"),
        "OMO_WORKSPACE_ROOT": str(workspace),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(WRAPPER), job_name, *command],
        cwd=cwd or workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _heartbeat(workspace: Path, job_name: str = "agent-workflow-status") -> dict:
    heartbeat = workspace / ".omo" / "state" / "heartbeats" / f"{job_name}.json"
    return json.loads(heartbeat.read_text(encoding="utf-8"))


def test_wrapper_records_success_under_explicit_workspace_root(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, "/bin/sh", "-c", "exit 0")

    assert result.returncode == 0, result.stderr
    payload = _heartbeat(tmp_path)
    assert payload["job"] == "agent-workflow-status"
    assert payload["exit_code"] == 0
    assert payload["ok"] is True
    assert payload["started_at"].endswith("Z")
    assert payload["last_run"].endswith("Z")


def test_wrapper_preserves_command_failure_and_records_it(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, "/bin/sh", "-c", "exit 7")

    assert result.returncode == 7
    payload = _heartbeat(tmp_path)
    assert payload["exit_code"] == 7
    assert payload["ok"] is False


def test_wrapper_defaults_to_current_directory_not_home(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".omo").mkdir()
    env = {
        **os.environ,
        "HOME": str(tmp_path / "decoy-home"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("OMO_WORKSPACE_ROOT", None)

    result = subprocess.run(
        ["bash", str(WRAPPER), "cwd-probe", "/bin/sh", "-c", "exit 0"],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert _heartbeat(workspace, "cwd-probe")["ok"] is True
    assert not (tmp_path / "decoy-home" / "Workspace").exists()


def test_wrapper_rejects_unsafe_job_name_without_writing(tmp_path: Path) -> None:
    result = _run_wrapper(
        tmp_path,
        "/bin/sh",
        "-c",
        "exit 0",
        job_name="../escape",
    )

    assert result.returncode == 64
    assert "invalid job name" in result.stderr
    assert not (tmp_path / ".omo" / "state" / "heartbeats").exists()


def test_wrapper_uses_atomic_final_file_without_temp_residue(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, "/bin/sh", "-c", "exit 0")

    assert result.returncode == 0, result.stderr
    heartbeat_dir = tmp_path / ".omo" / "state" / "heartbeats"
    assert [item.name for item in heartbeat_dir.iterdir()] == [
        "agent-workflow-status.json"
    ]


def test_wrapper_rejects_missing_command_and_invalid_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".omo").mkdir(parents=True)
    base_env = {**os.environ, "HOME": str(tmp_path / "decoy-home")}

    missing_command = subprocess.run(
        ["bash", str(WRAPPER), "job-only"],
        cwd=workspace,
        env={**base_env, "OMO_WORKSPACE_ROOT": str(workspace)},
        capture_output=True,
        text=True,
        check=False,
    )
    relative_root = subprocess.run(
        ["bash", str(WRAPPER), "job", "/bin/true"],
        cwd=workspace,
        env={**base_env, "OMO_WORKSPACE_ROOT": "relative/root"},
        capture_output=True,
        text=True,
        check=False,
    )
    missing_root = subprocess.run(
        ["bash", str(WRAPPER), "job", "/bin/true"],
        cwd=workspace,
        env={**base_env, "OMO_WORKSPACE_ROOT": str(tmp_path / "missing")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert missing_command.returncode == 64
    assert relative_root.returncode == 64
    assert missing_root.returncode == 66
    assert not (workspace / ".omo" / "state" / "heartbeats").exists()


def _failing_tool_directory(tmp_path: Path, tool_name: str) -> Path:
    tool_dir = tmp_path / f"failing-{tool_name}"
    tool_dir.mkdir()
    executable = tool_dir / tool_name
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    executable.chmod(0o755)
    return tool_dir


def test_wrapper_faults_are_observable_and_preserve_failed_command(
    tmp_path: Path,
) -> None:
    for tool_name in ("python3", "mv"):
        workspace = tmp_path / tool_name
        failing_tools = _failing_tool_directory(tmp_path, tool_name)
        fault_env = {"PATH": f"{failing_tools}:{os.environ['PATH']}"}

        successful_command = _run_wrapper(
            workspace,
            "/bin/sh",
            "-c",
            "exit 0",
            extra_env=fault_env,
        )
        failed_command = _run_wrapper(
            workspace,
            "/bin/sh",
            "-c",
            "exit 7",
            job_name="failed-command",
            extra_env=fault_env,
        )

        assert successful_command.returncode == 74
        assert failed_command.returncode == 7
        heartbeat_dir = workspace / ".omo" / "state" / "heartbeats"
        assert list(heartbeat_dir.iterdir()) == []


def test_concurrent_writers_leave_one_complete_atomic_receipt(tmp_path: Path) -> None:
    (tmp_path / ".omo").mkdir()
    env = {
        **os.environ,
        "HOME": str(tmp_path / "decoy-home"),
        "OMO_WORKSPACE_ROOT": str(tmp_path),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    processes = [
        subprocess.Popen(
            [
                "bash",
                str(WRAPPER),
                "concurrent-job",
                "/bin/sh",
                "-c",
                f"sleep {delay}; exit 0",
            ],
            cwd=tmp_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for delay in ("0.05", "0")
    ]

    results = [process.communicate(timeout=5) for process in processes]

    assert [process.returncode for process in processes] == [0, 0], results
    payload = _heartbeat(tmp_path, "concurrent-job")
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    heartbeat_dir = tmp_path / ".omo" / "state" / "heartbeats"
    assert [item.name for item in heartbeat_dir.iterdir()] == ["concurrent-job.json"]


def _operating_rhythm_jobs() -> list[str]:
    return [
        line
        for line in OPERATING_RHYTHM.read_text(encoding="utf-8").splitlines()
        if line
        and not line.startswith("#")
        and not line.startswith(("SHELL=", "PATH=", "OMO_WORKSPACE_ROOT="))
    ]


def _operating_rhythm_commands() -> list[str]:
    return [job.split(maxsplit=5)[5] for job in _operating_rhythm_jobs()]


def test_operating_rhythm_template_binds_every_job_to_explicit_root() -> None:
    content = OPERATING_RHYTHM.read_text(encoding="utf-8")
    jobs = _operating_rhythm_jobs()
    commands = _operating_rhythm_commands()

    assert "OMO_WORKSPACE_ROOT=" in content.splitlines()
    assert "$HOME/Workspace" not in content
    assert len(jobs) == 12
    assert all(command.startswith(ROOT_GUARD_PREFIX) for command in commands)
    assert sum("heartbeat-wrapper.sh agent-workflow-status" in job for job in jobs) == 1
    assert all(not ("meta-doctor.py" in job and "--json" in job) for job in jobs)


def test_operating_rhythm_root_guard_rejects_ambiguous_roots(tmp_path: Path) -> None:
    relative_decoy = tmp_path / "relative-decoy"
    valid_root = tmp_path / "valid-root"
    (relative_decoy / ".omo").mkdir(parents=True)
    (valid_root / ".omo").mkdir(parents=True)
    actual_prefix = _operating_rhythm_commands()[0][: len(ROOT_GUARD_PREFIX)]
    assert actual_prefix == ROOT_GUARD_PREFIX
    command = f"{actual_prefix}/bin/pwd"
    cases = (
        ("", False),
        (".", False),
        (str(tmp_path / "absolute-missing"), False),
        (str(valid_root), True),
    )

    for root, expected_ok in cases:
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=relative_decoy,
            env={**os.environ, "OMO_WORKSPACE_ROOT": root},
            capture_output=True,
            text=True,
            check=False,
        )

        assert (result.returncode == 0) is expected_ok, (root, result)
        if expected_ok:
            assert Path(result.stdout.strip()).resolve() == valid_root.resolve()
