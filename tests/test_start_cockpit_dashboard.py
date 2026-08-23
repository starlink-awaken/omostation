"""Tests for bin/runtime/start-cockpit-dashboard.sh.

Covers the script's idempotent start/stop/status logic without actually
launching uvicorn (which is too heavy for unit tests). The tests run
against a synthetic WORKSPACE pointing at tmp_path, then exercise the
script's process-management helpers by stubbing `uv` with a `sleep`
binary that exits 0.

Approach: replace the script's `uv` with a fake binary that sleeps in
the foreground, so the script's "is_alive after sleep" check works.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "runtime" / "start-cockpit-dashboard.sh"


def _make_fake_uv(bin_dir: Path) -> Path:
    """Create a fake uv that sleeps forever in foreground.

    The script does `nohup uv ... &` then `sleep 1` then checks if the
    PID is still alive. A sleeping foreground process satisfies this.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/usr/bin/env bash\n"
        "exec sleep 300\n",  # long enough that the script's sleep 1 + is_alive check sees it
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return uv


def _run(script_argv: list[str], *, workdir: Path, env: dict) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(SCRIPT), *script_argv],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc


def _defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fake workspace + PATH that the script will use."""
    bin_dir = tmp_path / "fakebin"
    _make_fake_uv(bin_dir)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["WORKSPACE"] = str(tmp_path)
    env["PORT"] = "18090"  # avoid clashing with any real cockpit on 8090
    return env, bin_dir


def test_status_returns_not_running_when_no_pid_file(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    proc = _run(["status"], workdir=tmp_path, env=env)
    assert proc.returncode == 0
    assert "not running" in proc.stdout


def test_start_writes_pid_file(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    proc = _run(["start"], workdir=tmp_path, env=env)
    assert proc.returncode == 0, proc.stderr
    assert "started" in proc.stdout
    pid_file = tmp_path / "runtime" / "cockpit-dashboard.pid"
    assert pid_file.exists()
    pid = int(pid_file.read_text().strip())
    # the pid must point to a live process
    os.kill(pid, 0)
    # cleanup
    os.kill(pid, 9)
    pid_file.unlink()


def test_start_is_idempotent(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    first = _run(["start"], workdir=tmp_path, env=env)
    assert "started" in first.stdout
    pid_file = tmp_path / "runtime" / "cockpit-dashboard.pid"
    pid = int(pid_file.read_text().strip())

    second = _run(["start"], workdir=tmp_path, env=env)
    assert "already running" in second.stdout
    # pid unchanged
    assert int(pid_file.read_text().strip()) == pid

    os.kill(pid, 9)
    pid_file.unlink()


def test_stop_kills_running_instance(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    start = _run(["start"], workdir=tmp_path, env=env)
    assert "started" in start.stdout
    pid_file = tmp_path / "runtime" / "cockpit-dashboard.pid"
    pid = int(pid_file.read_text().strip())

    stop = _run(["stop"], workdir=tmp_path, env=env)
    assert "stopping" in stop.stdout
    assert stop.returncode == 0
    assert not pid_file.exists()
    # process should be dead
    import errno
    with pytest.raises(OSError) as exc:
        os.kill(pid, 0)
    assert exc.value.errno == errno.ESRCH


def test_stop_when_not_running_is_noop(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    proc = _run(["stop"], workdir=tmp_path, env=env)
    assert proc.returncode == 0
    assert "not running" in proc.stdout


def test_status_after_start_reports_running(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    _run(["start"], workdir=tmp_path, env=env)
    pid_file = tmp_path / "runtime" / "cockpit-dashboard.pid"

    proc = _run(["status"], workdir=tmp_path, env=env)
    assert "running" in proc.stdout
    assert str(pid_file.read_text().strip()) in proc.stdout

    # cleanup
    pid = int(pid_file.read_text().strip())
    os.kill(pid, 9)
    pid_file.unlink()


def test_start_fails_when_port_in_use(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    # Bind a server socket on the same port to simulate it being taken
    import socket

    port = int(env["PORT"])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    try:
        proc = _run(["start"], workdir=tmp_path, env=env)
        assert proc.returncode == 1
        assert "port" in proc.stderr or "in use" in proc.stderr
    finally:
        server.close()


def test_start_without_uv_fails(tmp_path, monkeypatch):
    env = os.environ.copy()
    # Strip uv by using an empty PATH that contains only /usr/bin
    env["PATH"] = "/usr/bin:/bin"
    env["WORKSPACE"] = str(tmp_path)
    env["PORT"] = "18091"
    proc = _run(["start"], workdir=tmp_path, env=env)
    assert proc.returncode == 1
    assert "uv not in PATH" in proc.stderr


def test_unknown_subcommand_fails(tmp_path, monkeypatch):
    env, _ = _defaults(tmp_path, monkeypatch)
    proc = _run(["bogus-cmd"], workdir=tmp_path, env=env)
    assert proc.returncode == 2
    assert "usage" in proc.stderr