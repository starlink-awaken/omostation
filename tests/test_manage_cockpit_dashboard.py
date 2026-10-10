from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "runtime" / "manage-cockpit-dashboard.sh"


def _setup(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state_file = tmp_path / "loaded"
    call_log = tmp_path / "calls"
    launchctl = fake_bin / "launchctl"
    launchctl.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'case "$1" in\n'
        '  print) test -f "$STATE_FILE" ;;\n'
        '  bootstrap) touch "$STATE_FILE" ;;\n'
        '  kickstart) ;;\n'
        '  bootout) rm -f "$STATE_FILE" ;;\n'
        '  *) exit 2 ;;\n'
        'esac\n',
        encoding="utf-8",
    )
    launchctl.chmod(0o755)
    plist = tmp_path / "com.cockpit.dashboard.plist"
    plist.touch()
    generator = tmp_path / "bin" / "mof" / "gen-service-configs.py"
    generator.parent.mkdir(parents=True)
    generator.write_text("raise SystemExit(0)\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CALL_LOG": str(call_log),
            "STATE_FILE": str(state_file),
            "COCKPIT_DASHBOARD_PLIST": str(plist),
            "WORKSPACE": str(tmp_path),
        }
    )
    return env, state_file, call_log


def _run(tmp_path: Path, env: dict[str, str], command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_start_bootstraps_and_kickstarts_launchagent(tmp_path: Path) -> None:
    env, state_file, call_log = _setup(tmp_path)
    result = _run(tmp_path, env, "start")
    assert result.returncode == 0, result.stderr
    assert state_file.exists()
    calls = call_log.read_text(encoding="utf-8")
    assert "bootstrap gui/" in calls
    assert "kickstart gui/" in calls


def test_start_of_loaded_service_does_not_bootstrap_again(tmp_path: Path) -> None:
    env, state_file, call_log = _setup(tmp_path)
    state_file.touch()
    result = _run(tmp_path, env, "start")
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8")
    assert "kickstart gui/" in calls
    assert "bootstrap gui/" not in calls


def test_stop_boots_out_loaded_launchagent(tmp_path: Path) -> None:
    env, state_file, call_log = _setup(tmp_path)
    state_file.touch()
    result = _run(tmp_path, env, "stop")
    assert result.returncode == 0, result.stderr
    assert not state_file.exists()
    assert "bootout gui/" in call_log.read_text(encoding="utf-8")


def test_status_fails_when_launchagent_is_not_loaded(tmp_path: Path) -> None:
    env, _, _ = _setup(tmp_path)
    result = _run(tmp_path, env, "status")
    assert result.returncode == 1
    assert "is not loaded" in result.stdout


def test_status_prints_loaded_launchagent(tmp_path: Path) -> None:
    env, state_file, call_log = _setup(tmp_path)
    state_file.touch()
    result = _run(tmp_path, env, "status")
    assert result.returncode == 0, result.stderr
    assert "print gui/" in call_log.read_text(encoding="utf-8")
