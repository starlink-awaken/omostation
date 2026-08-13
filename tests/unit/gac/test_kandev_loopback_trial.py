"""Safety contract tests for the Kandev loopback trial runner."""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "bin/gac/kandev-loopback-trial.py"
SPEC = importlib.util.spec_from_file_location("kandev_loopback_trial", SCRIPT)
assert SPEC and SPEC.loader
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 43210
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return 0 if self.terminated or self.killed else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return 0


def safe_home(tmp_path: Path) -> Path:
    home = tmp_path / "isolated-kandev-home"
    home.mkdir()
    return home


def fake_tree(child: FakeProcess):
    return lambda: "" if child.poll() is not None else f"{child.pid} 1 {child.pid}\n"


def stop_fake(child: FakeProcess):
    return lambda _group, _signal: child.terminate()


def test_default_cli_is_dry_run_and_never_starts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    home = safe_home(tmp_path)
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("default dry run must not start a child")

    monkeypatch.setattr(trial.subprocess, "Popen", forbidden)
    code = trial.main(["run-smoke", "--package-version", "1.2.3", "--home", str(home), "--port", "43123"])

    assert code == 0
    assert called is False
    assert json.loads(capsys.readouterr().out)["mode"] == "dry-run"


def test_macos_system_python_can_run_help_and_dry_run(tmp_path: Path):
    """The checked-in CLI uses macOS system Python, not pytest's uv runtime."""
    system_python = Path("/usr/bin/python3")
    if not system_python.exists():
        pytest.skip("macOS system Python is unavailable")
    help_result = subprocess.run(
        [str(system_python), str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    home = safe_home(tmp_path)
    dry_run = subprocess.run(
        [
            str(system_python),
            str(SCRIPT),
            "run-smoke",
            "--package-version",
            "0.87.1",
            "--home",
            str(home),
            "--port",
            "43123",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert help_result.returncode == 0, help_result.stderr
    assert dry_run.returncode == 0, dry_run.stderr
    assert json.loads(dry_run.stdout)["mode"] == "dry-run"


def test_npx_resolution_and_child_path_are_absolute_and_controlled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(trial.shutil, "which", lambda _name: "/opt/homebrew/bin/npx")
    assert trial.resolve_npx() == "/opt/homebrew/bin/npx"
    path_entries = trial._controlled_path("/opt/homebrew/bin/npx").split(":")
    assert path_entries[0] == "/opt/homebrew/bin"
    assert "/Users/xiamingxing/.local/bin" not in path_entries


@pytest.mark.parametrize("version", ["latest", "^1.2.3", "1.2", "", "1.2.3;rm"])
def test_unpinned_or_illegal_package_versions_are_rejected(version: str):
    with pytest.raises(trial.TrialError):
        trial.validate_package_version(version)


def test_timeout_larger_than_cold_download_bound_is_rejected(tmp_path: Path):
    with pytest.raises(trial.TrialError, match="600"):
        trial.run_smoke(
            package_version="1.2.3",
            home=safe_home(tmp_path),
            port=43123,
            receipt_path=tmp_path / "too-long.json",
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            startup_timeout_seconds=601,
        )


def test_cleanup_timeout_is_bounded_and_configurable(tmp_path: Path):
    with pytest.raises(trial.TrialError, match="cleanup timeout"):
        trial.run_smoke(
            package_version="1.2.3",
            home=safe_home(tmp_path),
            port=43123,
            receipt_path=tmp_path / "too-slow-cleanup.json",
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            cleanup_timeout_seconds=61,
        )


def test_workspace_or_user_home_is_rejected(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bad_workspace_home = workspace / "trial"
    bad_workspace_home.mkdir()
    user_home = tmp_path / "user"
    user_home.mkdir()
    bad_user_home = user_home / ".kandev"
    bad_user_home.mkdir()

    with pytest.raises(trial.TrialError):
        trial.validate_trial_home(bad_workspace_home, workspace_root=workspace, user_home=user_home)
    with pytest.raises(trial.TrialError):
        trial.validate_trial_home(bad_user_home, workspace_root=workspace, user_home=user_home)


def test_home_must_be_explicit_empty_directory(tmp_path: Path):
    missing = tmp_path / "missing"
    with pytest.raises(trial.TrialError):
        trial.validate_trial_home(missing, workspace_root=tmp_path / "workspace", user_home=tmp_path / "user")

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "state").write_text("no", encoding="utf-8")
    with pytest.raises(trial.TrialError):
        trial.validate_trial_home(nonempty, workspace_root=tmp_path / "workspace", user_home=tmp_path / "user")


def test_non_loopback_listener_is_rejected():
    with pytest.raises(trial.TrialError):
        trial.assert_loopback_listener("TCP *:43123 (LISTEN)", 43123)


def test_health_probe_uses_proxy_free_opener(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HTTP_PROXY", "http://must-not-use")
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-use")
    captured: dict[str, object] = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Opener:
        def open(self, url: str, *, timeout: float):
            captured["url"] = url
            captured["timeout"] = timeout
            return Response()

    def factory(handler):
        captured["handler"] = handler
        return Opener()

    assert trial._default_health_probe(43123, opener_factory=factory) is True
    assert captured["url"] == "http://127.0.0.1:43123/health"
    assert captured["handler"].proxies == {}


def test_health_failure_writes_redacted_failed_receipt(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "receipt.json"
    child = FakeProcess()

    with pytest.raises(trial.TrialError, match="health"):
        trial.run_smoke(
            package_version="1.2.3",
            home=home,
            port=43123,
            receipt_path=receipt,
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=lambda *_args: False,
            listener_probe=lambda _port: "",
            group_terminator=stop_fake(child),
            process_tree_probe=fake_tree(child),
            startup_timeout_seconds=0.01,
            sleeper=lambda _seconds: None,
        )

    result = json.loads(receipt.read_text(encoding="utf-8"))
    assert result["outcome"] == "failed"
    assert child.terminated and child.wait_calls
    assert "raw_logs" not in result
    assert "token" not in json.dumps(result).lower()


def test_timeout_reaps_child_and_never_leaks_raw_output(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "timeout.json"
    child = FakeProcess()
    ticks = itertools.chain([0.0, 0.0, 1.0], itertools.repeat(1.0))

    with pytest.raises(trial.TrialError, match="timed out"):
        trial.run_smoke(
            package_version="1.2.3",
            home=home,
            port=43123,
            receipt_path=receipt,
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=lambda *_args: False,
            listener_probe=lambda _port: "",
            group_terminator=stop_fake(child),
            process_tree_probe=fake_tree(child),
            startup_timeout_seconds=0.5,
            monotonic=lambda: next(ticks),
            sleeper=lambda _seconds: None,
        )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["checks"]["child_reaped"] is True
    assert "stderr" not in payload and "stdout" not in payload


def test_success_emits_canonical_safe_receipt_and_uses_isolated_child_cwd(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "success.json"
    child = FakeProcess()
    captured: dict[str, object] = {}
    listener_outputs = iter(["", "TCP 127.0.0.1:43123 (LISTEN)", ""])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    user_home = tmp_path / "user"
    user_home.mkdir()
    workspace_sentinel = workspace / "must-not-change"
    user_config_sentinel = user_home / ".kandev-config"
    workspace_sentinel.write_text("workspace-before", encoding="utf-8")
    user_config_sentinel.write_text("user-config-before", encoding="utf-8")

    def start(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return child

    result = trial.run_smoke(
        package_version="1.2.3",
        home=home,
        port=43123,
        receipt_path=receipt,
        workspace_root=workspace,
        user_home=user_home,
        popen_factory=start,
        health_probe=lambda *_args: True,
        listener_probe=lambda _port: next(listener_outputs),
        group_terminator=stop_fake(child),
        listener_owner_probe=lambda _output, _process: True,
        process_tree_probe=fake_tree(child),
    )

    raw = receipt.read_text(encoding="utf-8")
    assert raw == json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    assert captured["argv"] == [trial.resolve_npx(), "-y", "kandev@1.2.3", "--headless", "--port", "43123"]
    assert captured["shell"] is False
    assert captured["cwd"] == str(home)
    environment = captured["env"]
    assert environment["KANDEV_HOME_DIR"] == str(home)
    assert environment["KANDEV_SERVER_HOST"] == "127.0.0.1"
    assert environment["KANDEV_NO_BROWSER"] == "1"
    assert environment["OMO_KANDEV_TRIAL_ID"]
    assert environment["HOME"] == str(home)
    assert environment["XDG_CONFIG_HOME"].startswith(str(home))
    assert environment["NPM_CONFIG_CACHE"].startswith(str(home))
    assert environment["NPM_CONFIG_AUDIT"] == "false"
    assert environment["NPM_CONFIG_FUND"] == "false"
    assert environment["NPM_CONFIG_UPDATE_NOTIFIER"] == "false"
    assert result["outcome"] == "succeeded"
    assert result["assertions"] == {
        "agent_spawned": False,
        "model_called": False,
        "task_created": False,
        "workspace_written": False,
    }
    assert result["checks"]["child_reaped"] is True
    assert result["checks"]["listener_released"] is True
    assert result["checks"]["owned_processes_released"] is True
    assert result["started_at"].endswith("Z") and result["completed_at"].endswith("Z")
    assert result["duration_seconds"] >= 0
    assert str(home) not in raw
    assert "@" not in raw and "token" not in raw.lower()
    assert "OMO_KANDEV_TRIAL_ID" not in raw
    assert workspace_sentinel.read_text(encoding="utf-8") == "workspace-before"
    assert user_config_sentinel.read_text(encoding="utf-8") == "user-config-before"


def test_child_environment_drops_sensitive_parent_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = safe_home(tmp_path)
    receipt = tmp_path / "safe.json"
    child = FakeProcess()
    captured: dict[str, object] = {}
    listener_outputs = iter(["", "TCP 127.0.0.1:43123 (LISTEN)"])
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("HTTP_PROXY", "http://must-not-leak")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/must-not-leak.sock")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "must-not-leak")

    def start(_argv, **kwargs):
        captured.update(kwargs)
        return child

    trial.run_smoke(
        package_version="1.2.3",
        home=home,
        port=43123,
        receipt_path=receipt,
        workspace_root=tmp_path / "workspace",
        user_home=tmp_path / "user",
        popen_factory=start,
        health_probe=lambda *_args: True,
        listener_probe=lambda _port: next(listener_outputs),
        listener_released_probe=lambda _port: True,
        group_terminator=stop_fake(child),
        listener_owner_probe=lambda _output, _process: True,
        process_tree_probe=fake_tree(child),
    )

    environment = captured["env"]
    assert "OPENAI_API_KEY" not in environment
    assert "HTTP_PROXY" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert "SSH_AUTH_SOCK" not in environment
    assert "AWS_SESSION_TOKEN" not in environment
    assert set(environment).isdisjoint(
        {"OPENAI_API_KEY", "HTTP_PROXY", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "AWS_SESSION_TOKEN"}
    )


def test_preexisting_listener_is_rejected_before_start(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "preexisting.json"

    with pytest.raises(trial.TrialError, match="already active"):
        trial.run_smoke(
            package_version="1.2.3",
            home=home,
            port=43123,
            receipt_path=receipt,
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            popen_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
            listener_probe=lambda _port: "TCP 127.0.0.1:43123 (LISTEN)",
        )

    assert json.loads(receipt.read_text(encoding="utf-8"))["failure_code"] == "listener_rejected"


def test_receipt_path_inside_workspace_user_home_or_trial_home_is_rejected(tmp_path: Path):
    home = safe_home(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    user_home = tmp_path / "user"
    user_home.mkdir()

    for receipt in (workspace / "receipt.json", user_home / "receipt.json", home / "receipt.json"):
        with pytest.raises(trial.TrialError, match="receipt"):
            trial.run_smoke(
                package_version="1.2.3",
                home=home,
                port=43123,
                receipt_path=receipt,
                workspace_root=workspace,
                user_home=user_home,
                popen_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
            )


def test_process_group_is_terminated_then_listener_must_be_released(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "group.json"
    child = FakeProcess()
    signals: list[tuple[int, signal.Signals]] = []
    listener_outputs = iter(["", "TCP 127.0.0.1:43123 (LISTEN)"])

    with pytest.raises(trial.TrialError, match="listener remained"):
        trial.run_smoke(
            package_version="1.2.3",
            home=home,
            port=43123,
            receipt_path=receipt,
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=lambda *_args: True,
            listener_probe=lambda _port: next(listener_outputs),
            listener_released_probe=lambda _port: False,
            group_terminator=lambda group, value: (signals.append((group, value)), child.terminate()),
            listener_owner_probe=lambda _output, _process: True,
            process_tree_probe=fake_tree(child),
        )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert signals == [(43210, signal.SIGTERM)]
    assert payload["outcome"] == "failed"
    assert payload["checks"]["child_reaped"] is False
    assert payload["checks"]["listener_released"] is False
    assert payload["failure_code"] == "cleanup_unconfirmed"


def test_group_kill_follows_timeout_when_term_does_not_reap():
    child = FakeProcess()
    signals: list[signal.Signals] = []
    state = {"killed": False}

    def tree():
        return "" if state["killed"] else f"{child.pid} 1 {child.pid}\n43211 {child.pid} 43211\n"

    def terminate(_group: int, value: signal.Signals):
        signals.append(value)
        if value is signal.SIGKILL:
            state["killed"] = True
            child.terminate()

    ticks = itertools.chain([0.0, 16.0], itertools.repeat(16.0))
    assert trial._reap(child, terminate, tree, monotonic=lambda: next(ticks), sleeper=lambda _seconds: None) is True
    assert signals == [signal.SIGTERM, signal.SIGTERM, signal.SIGKILL, signal.SIGKILL]


def test_marker_orphan_is_killed_when_launcher_snapshot_is_empty(tmp_path: Path):
    """A re-parented marked backend is still attributable after the root exits."""
    home = safe_home(tmp_path)
    receipt = tmp_path / "orphan.json"
    child = FakeProcess()
    child.terminated = True
    marker = "OMO_KANDEV_TRIAL_ID=fixed-marker"
    state = {"live": True}
    signals: list[tuple[int, signal.Signals]] = []
    listener_outputs = iter(["", "TCP 127.0.0.1:43123 (LISTEN)"])

    def marker_probe(value: str):
        assert value == marker
        return {54321: (1, 54321)} if state["live"] else {}

    def terminate(group: int, value: signal.Signals):
        signals.append((group, value))
        state["live"] = False

    result = trial.run_smoke(
        package_version="1.2.3",
        home=home,
        port=43123,
        receipt_path=receipt,
        workspace_root=tmp_path / "workspace",
        user_home=tmp_path / "user",
        popen_factory=lambda *_args, **_kwargs: child,
        health_probe=lambda *_args: True,
        listener_probe=lambda _port: next(listener_outputs),
        listener_released_probe=lambda _port: True,
        listener_owner_probe=lambda _output, owned: 54321 in owned,
        process_tree_probe=lambda: "",
        marker_factory=lambda: "fixed-marker",
        marker_probe=marker_probe,
        group_terminator=terminate,
    )

    assert signals == [(54321, signal.SIGTERM)]
    assert result["checks"]["child_reaped"] is True
    assert result["checks"]["owned_processes_released"] is True


def test_marker_probe_failure_prevents_cleanup_success(tmp_path: Path):
    home = safe_home(tmp_path)
    receipt = tmp_path / "marker-failed.json"
    child = FakeProcess()
    listener_outputs = iter(["", "TCP 127.0.0.1:43123 (LISTEN)"])

    with pytest.raises(trial.TrialError, match="marker unavailable"):
        trial.run_smoke(
            package_version="1.2.3",
            home=home,
            port=43123,
            receipt_path=receipt,
            workspace_root=tmp_path / "workspace",
            user_home=tmp_path / "user",
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=lambda *_args: True,
            listener_probe=lambda _port: next(listener_outputs),
            listener_released_probe=lambda _port: True,
            process_tree_probe=fake_tree(child),
            marker_probe=lambda _marker: (_ for _ in ()).throw(trial.TrialError("marker unavailable")),
        )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["checks"]["child_reaped"] is False
    assert payload["checks"]["owned_processes_released"] is False


def test_real_detached_descendant_tree_and_loopback_listener_are_fully_reaped():
    """A real parent -> setsid child -> listener grandchild cannot survive cleanup."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    marker = "OMO_KANDEV_TRIAL_ID=real-detached-marker"

    grandchild_code = """
import socket
import sys
import time
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('127.0.0.1', int(sys.argv[1])))
server.listen()
time.sleep(60)
"""
    child_code = (
        "import os, subprocess, sys, time\n"
        "os.setsid()\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild_code!r}, sys.argv[1]])\n"
        "time.sleep(60)\n"
    )
    parent_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, sys.argv[1]])\n"
        "time.sleep(60)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code, str(port)],
        env={**os.environ, "OMO_KANDEV_TRIAL_ID": marker.split("=", 1)[1]},
        start_new_session=True,
    )

    def listening() -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                return True
        except OSError:
            return False

    try:
        deadline = time.monotonic() + 5
        while not listening() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert listening()
        owned_before = trial._owned_processes(parent.pid, trial._default_process_tree_probe())
        assert len(owned_before) >= 3
        assert trial._default_marker_probe(marker)
        assert trial._reap(parent, trial._default_group_terminator, trial_marker=marker, timeout_seconds=2) is True
        deadline = time.monotonic() + 2
        while listening() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not listening()
        live_after = set(trial._parse_process_tree(trial._default_process_tree_probe()))
        assert not set(owned_before).intersection(live_after)
    finally:
        if parent.poll() is None:
            trial._reap(parent, trial._default_group_terminator, timeout_seconds=2)
