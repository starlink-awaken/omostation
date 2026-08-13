"""Contract tests for the bounded, no-tools Pi worker adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "bin/gac/pi-worker-adapter.py"
SPEC = importlib.util.spec_from_file_location("pi_worker_adapter", SCRIPT)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class FakeProcess:
    def __init__(self, *, stdout: str = "reasoned answer\n", stderr: str = "", returncode: int = 0) -> None:
        self.pid = 43210
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.running = True
        self.wait_calls = 0

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.running = False
        return self.stdout, self.stderr

    def poll(self):
        return None if self.running else self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.running = False
        self.wait_calls += 1
        return self.returncode


class HungProcess(FakeProcess):
    def __init__(self) -> None:
        super().__init__()
        self.communicate_calls = 0

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.communicate_calls += 1
        if self.communicate_calls == 1:
            raise subprocess.TimeoutExpired("pi", timeout)
        self.running = False
        return "", ""

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired("pi", timeout)
        self.running = False
        return self.returncode


def user_pi_home(tmp_path: Path, *, provider_overrides: dict[str, object] | None = None) -> Path:
    home = tmp_path / "user"
    config = home / ".pi" / "agent"
    config.mkdir(parents=True)
    provider: dict[str, object] = {
        "api": "openai-completions",
        "apiKey": "!security find-generic-password -s omlxc -w",
        "authHeader": True,
        "baseUrl": "http://127.0.0.1:9290/v1",
        "models": [{"id": "coding"}],
    }
    provider.update(provider_overrides or {})
    (config / "models.json").write_text(
        json.dumps({"providers": {"omlxc": provider, "other": {"apiKey": "secret"}}}),
        encoding="utf-8",
    )
    for name in ("settings.json", "auth.json", "trust.json"):
        (config / name).write_text("{}", encoding="utf-8")
    return home


def safe_receipt(tmp_path: Path) -> Path:
    return tmp_path / "receipt.json"


def healthy() -> dict[str, str]:
    return {"status": "ok", "service": "aetherforge-openai-proxy"}


def no_marker(_marker: str) -> dict[int, int]:
    return {}


def test_dry_run_never_probes_health_or_starts_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run must not start a process")

    monkeypatch.setattr(adapter.subprocess, "Popen", forbidden)
    result = adapter.run_worker(prompt="hello", execute=False, user_home=user_pi_home(tmp_path))

    assert result["mode"] == "dry-run"
    assert result["command"] == adapter.fixed_argv("hello")


@pytest.mark.parametrize(
    "overrides",
    [
        {"baseUrl": "https://cloud.example/v1"},
        {"api": "anthropic-messages"},
        {"authHeader": False},
        {"models": [{"id": "other"}]},
        {"apiKey": "!sh -c 'curl cloud.example'"},
    ],
)
def test_provider_must_be_audited_local_aetherforge_config(tmp_path: Path, overrides: dict[str, object]):
    with pytest.raises(adapter.AdapterError, match="models_config_rejected"):
        adapter._copy_omlxc_provider(user_pi_home(tmp_path, provider_overrides=overrides), tmp_path / "isolated")


def test_provider_copy_keeps_only_validated_omlxc_provider(tmp_path: Path):
    destination = tmp_path / "isolated"
    adapter._copy_omlxc_provider(user_pi_home(tmp_path), destination)

    copied = json.loads((destination / "models.json").read_text(encoding="utf-8"))
    assert copied == {
        "providers": {
            "omlxc": {
                "api": "openai-completions",
                "apiKey": "!security find-generic-password -s omlxc -w",
                "authHeader": True,
                "baseUrl": "http://127.0.0.1:9290/v1",
                "models": [{"id": "coding"}],
            }
        }
    }


def test_provider_projection_strips_unknown_and_non_coding_model_fields(tmp_path: Path):
    destination = tmp_path / "isolated"
    home = user_pi_home(
        tmp_path,
        provider_overrides={
            "unknown_provider_setting": "must-not-cross-boundary",
            "models": [{"id": "coding", "unknown_model_setting": "must-not-cross-boundary"}, {"id": "other"}],
        },
    )
    adapter._copy_omlxc_provider(home, destination)

    copied = json.loads((destination / "models.json").read_text(encoding="utf-8"))
    assert copied["providers"]["omlxc"] == {
        "api": "openai-completions",
        "apiKey": "!security find-generic-password -s omlxc -w",
        "authHeader": True,
        "baseUrl": "http://127.0.0.1:9290/v1",
        "models": [{"id": "coding"}],
    }


def test_execute_uses_fixed_argv_shell_false_and_scrubbed_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = user_pi_home(tmp_path)
    receipt = safe_receipt(tmp_path)
    captured: dict[str, object] = {}
    child = FakeProcess()
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("HTTP_PROXY", "http://secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/secret")

    def start(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return child

    result = adapter.run_worker(
        prompt="inspect only",
        execute=True,
        receipt_path=receipt,
        user_home=home,
        popen_factory=start,
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "0.84.1",
    )

    assert captured["argv"] == adapter.fixed_argv("inspect only")
    assert captured["shell"] is False
    assert captured["start_new_session"] is True
    env = captured["env"]
    assert env["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    assert any(adapter._is_within(Path(env["PI_CODING_AGENT_DIR"]).resolve(), root) for root in adapter._system_temp_roots())
    assert any(adapter._is_within(Path(env["PI_CODING_AGENT_SESSION_DIR"]).resolve(), root) for root in adapter._system_temp_roots())
    assert env["HOME"] == str(home)
    assert "OPENAI_API_KEY" not in env and "HTTP_PROXY" not in env
    assert "GITHUB_TOKEN" not in env and "SSH_AUTH_SOCK" not in env
    assert result["output"] == "reasoned answer\n"


def test_health_identity_mismatch_fails_closed_without_starting_process(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    called = False

    def start(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("bad health must prevent start")

    with pytest.raises(adapter.AdapterError, match="health_rejected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=start,
            health_probe=lambda: {"status": "ok", "service": "wrong"},
            version_reader=lambda: "0.84.1",
        )

    assert called is False
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["error_code"] == "health_rejected"


def test_success_writes_model_text_only_to_stdout_and_keeps_receipt_redacted(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    model_text = "the private answer from model\n"
    result = adapter.run_worker(
        prompt="private input",
        execute=True,
        receipt_path=receipt,
        user_home=user_pi_home(tmp_path),
        popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout=model_text),
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "0.84.1",
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert result["output"] == model_text
    assert payload["outcome"] == "succeeded"
    assert payload["output_digest"] == adapter.digest_bytes(model_text.encode())
    assert model_text not in json.dumps(payload)
    assert "private input" not in json.dumps(payload)
    assert payload["checks"]["user_config_unchanged"] is True
    assert payload["checks"]["temp_cwd_unchanged"] is True
    assert payload["checks"]["temp_removed"] is True
    assert payload["checks"]["session_persisted"] is False
    assert payload["checks"]["tools_enabled"] is False


def test_transport_can_run_without_persisting_an_adapter_receipt(tmp_path: Path):
    result = adapter.run_worker(
        prompt="transport task",
        execute=True,
        user_home=user_pi_home(tmp_path),
        popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout="transport result\n"),
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "0.84.1",
    )

    assert result["output"] == "transport result\n"
    assert result["receipt"] is None


def test_cli_forwards_successful_model_text_to_stdout(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(adapter, "run_worker", lambda **_kwargs: {"output": "model text\n", "receipt": {}})

    assert adapter.main(["run", "--prompt", "x", "--execute", "--receipt", "/tmp/unused.json"]) == 0
    assert capsys.readouterr().out == "model text\n"


def test_timeout_sends_term_then_kill_and_fails_closed(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    child = HungProcess()
    signals: list[signal.Signals] = []

    def terminate(_pgid: int, value: signal.Signals) -> None:
        signals.append(value)
        if value == signal.SIGKILL:
            child.running = False

    with pytest.raises(adapter.AdapterError, match="timed_out"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=healthy,
            marker_probe=no_marker,
            group_terminator=terminate,
            version_reader=lambda: "0.84.1",
            timeout_seconds=1,
        )

    assert signals == [signal.SIGTERM, signal.SIGKILL]
    assert json.loads(receipt.read_text(encoding="utf-8"))["error_code"] == "timed_out"


def test_detached_marker_child_causes_fail_closed(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    child = FakeProcess()
    calls = 0

    def leaked_marker(_marker: str) -> dict[int, int]:
        nonlocal calls
        calls += 1
        return {9876: 9876} if calls >= 2 else {}

    with pytest.raises(adapter.AdapterError, match="process_leaked"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=healthy,
            marker_probe=leaked_marker,
            version_reader=lambda: "0.84.1",
        )


def test_user_config_drift_fails_closed(tmp_path: Path):
    home = user_pi_home(tmp_path)
    receipt = safe_receipt(tmp_path)

    class Mutating(FakeProcess):
        def communicate(self, timeout=None):
            (home / ".pi" / "agent" / "settings.json").write_text("changed", encoding="utf-8")
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="config_drift"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=home,
            popen_factory=lambda *_args, **_kwargs: Mutating(),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_unknown_user_agent_config_addition_fails_closed(tmp_path: Path):
    home = user_pi_home(tmp_path)

    class Mutating(FakeProcess):
        def communicate(self, timeout=None):
            (home / ".pi" / "agent" / "unknown-config.json").write_text("changed", encoding="utf-8")
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="config_drift"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=home,
            popen_factory=lambda *_args, **_kwargs: Mutating(),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_temp_cwd_write_fails_closed(tmp_path: Path):
    receipt = safe_receipt(tmp_path)

    class Writing(FakeProcess):
        def __init__(self, cwd: str) -> None:
            super().__init__()
            self.cwd = Path(cwd)

        def communicate(self, timeout=None):
            (self.cwd / "unexpected").write_text("no", encoding="utf-8")
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="temp_write_detected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_argv, **kwargs: Writing(kwargs["cwd"]),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_empty_temp_directory_write_fails_closed(tmp_path: Path):
    class WritingEmptyDirectory(FakeProcess):
        def __init__(self, cwd: str) -> None:
            super().__init__()
            self.cwd = Path(cwd)

        def communicate(self, timeout=None):
            (self.cwd / "unexpected-empty-directory").mkdir()
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="temp_write_detected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_argv, **kwargs: WritingEmptyDirectory(kwargs["cwd"]),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_tree_snapshot_detects_symlink_type_and_target(tmp_path: Path):
    before = adapter._trial_tree_digest(tmp_path)
    os.symlink("missing-target", tmp_path / "unexpected-link")

    assert adapter._trial_tree_digest(tmp_path) != before


def test_tree_snapshot_detects_same_path_node_type_change(tmp_path: Path):
    target = tmp_path / "type-changed"
    target.write_text("content", encoding="utf-8")
    before = adapter._trial_tree_digest(tmp_path)
    target.unlink()
    target.mkdir()

    assert adapter._trial_tree_digest(tmp_path) != before


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="platform does not support FIFO")
def test_fifo_temp_write_fails_closed(tmp_path: Path):
    class WritingFifo(FakeProcess):
        def __init__(self, cwd: str) -> None:
            super().__init__()
            self.cwd = Path(cwd)

        def communicate(self, timeout=None):
            os.mkfifo(self.cwd / "unexpected-fifo")
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="temp_write_detected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_argv, **kwargs: WritingFifo(kwargs["cwd"]),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_failed_trial_directory_removal_is_cleanup_unconfirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    receipt = safe_receipt(tmp_path)
    created: list[Path] = []

    def leave_trial(path: Path, **_kwargs) -> None:
        created.append(Path(path))

    monkeypatch.setattr(adapter.shutil, "rmtree", leave_trial)
    with pytest.raises(adapter.AdapterError, match="cleanup_unconfirmed"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )

    assert json.loads(receipt.read_text(encoding="utf-8"))["checks"]["temp_removed"] is False
    monkeypatch.undo()
    for path in created:
        shutil.rmtree(path)


@pytest.mark.parametrize("existing", [False, True])
def test_unsafe_or_overwrite_receipt_path_is_rejected(tmp_path: Path, existing: bool):
    receipt = (Path.cwd() / f"unsafe-pi-receipt-{tmp_path.name}.json") if not existing else safe_receipt(tmp_path)
    if existing:
        receipt.write_text("existing", encoding="utf-8")

    with pytest.raises(adapter.AdapterError, match="unsafe_receipt"):
        adapter.run_worker(prompt="x", execute=True, receipt_path=receipt, user_home=user_pi_home(tmp_path))


def test_exact_marker_mismatch_fails_closed_and_never_persists_stderr_secret(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    secret = "stderr-super-secret"

    with pytest.raises(adapter.AdapterError, match="output_mismatch"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout="wrong\n", stderr=secret),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
            expect_exact="expected",
        )

    assert secret not in receipt.read_text(encoding="utf-8")


def test_receipt_write_failure_is_a_stable_error_without_raw_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(adapter, "_write_receipt", lambda *_args: (_ for _ in ()).throw(OSError("secret write path")))

    with pytest.raises(adapter.AdapterError, match="receipt_write_failed"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_pi_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "0.84.1",
        )


def test_receipt_write_is_exclusive_and_does_not_overwrite(tmp_path: Path):
    receipt = safe_receipt(tmp_path)
    receipt.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError):
        adapter._write_receipt(receipt, {"outcome": "new"})

    assert receipt.read_text(encoding="utf-8") == "original"


def test_marker_probe_uses_absolute_system_ps(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def run(argv, **_kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    assert adapter._default_marker_probe("OMO_PI_TRIAL_ID=x") == {}
    assert captured["argv"][0] == "/bin/ps"


def test_real_subprocess_marker_reaper_removes_detached_descendant():
    marker = f"OMO_PI_TRIAL_ID=real-{time.time_ns()}"
    grandchild = "import time; time.sleep(30)"
    parent_code = (
        "import os, subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}], start_new_session=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", parent_code],
        env={**os.environ, "OMO_PI_TRIAL_ID": marker.split("=", 1)[1]},
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert adapter._reap(process, marker=marker, timeout_seconds=2) is True
    assert adapter._default_marker_probe(marker) == {}
