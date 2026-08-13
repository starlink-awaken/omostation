"""Contract tests for the bounded, no-tools OMP worker adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "bin/gac/omp-worker-adapter.py"
SPEC = importlib.util.spec_from_file_location("omp_worker_adapter", SCRIPT)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: str = "reasoned answer\n",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
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
    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        raise subprocess.TimeoutExpired("omp", timeout)

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired("omp", timeout)
        self.running = False
        return self.returncode


def user_omp_home(
    tmp_path: Path,
    *,
    provider_overrides: dict[str, object] | None = None,
    json_overrides: dict[str, object] | None = None,
    include_json: bool = True,
) -> Path:
    home = tmp_path / "user"
    config = home / ".omp" / "agent"
    config.mkdir(parents=True)
    provider: dict[str, object] = {
        "api": "openai-completions",
        "apiKey": "!security find-generic-password -s aetherforge-gateway -w",
        "authHeader": True,
        "baseUrl": "http://127.0.0.1:9290/v1",
        "compat": {
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": False,
        },
        "models": [
            {
                "id": "coding",
                "name": "omlxc Coding",
                "input": ["text"],
                "reasoning": False,
                "supportsTools": True,
            }
        ],
    }
    provider.update(provider_overrides or {})
    (config / "models.yml").write_text(_provider_yaml(provider), encoding="utf-8")
    if include_json:
        json_provider = dict(provider)
        json_provider.update(json_overrides or {})
        (config / "models.json").write_text(
            json.dumps(
                {"providers": {"omlxc": json_provider, "other": {"apiKey": "secret"}}}
            ),
            encoding="utf-8",
        )
    (config / "settings.json").write_text("{}", encoding="utf-8")
    return home


def _yaml_scalar(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value)
    raise TypeError(f"unsupported test YAML scalar: {value!r}")


def _provider_yaml(provider: dict[str, object]) -> str:
    lines = ["providers:", "  omlxc:"]
    for key, value in provider.items():
        if isinstance(value, dict):
            lines.append(f"    {key}:")
            lines.extend(
                f"      {child_key}: {_yaml_scalar(child_value)}"
                for child_key, child_value in value.items()
            )
        elif isinstance(value, list):
            lines.append(f"    {key}:")
            for item in value:
                assert isinstance(item, dict) and item
                first_key, first_value = next(iter(item.items()))
                lines.append(f"      - {first_key}: {_yaml_scalar(first_value)}")
                for child_key, child_value in list(item.items())[1:]:
                    if isinstance(child_value, list):
                        lines.append(f"        {child_key}:")
                        lines.extend(
                            f"          - {_yaml_scalar(member)}"
                            for member in child_value
                        )
                    else:
                        lines.append(
                            f"        {child_key}: {_yaml_scalar(child_value)}"
                        )
        else:
            lines.append(f"    {key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def healthy() -> dict[str, str]:
    return {"status": "ok", "service": "aetherforge-openai-proxy"}


def no_marker(_marker: str) -> dict[int, int]:
    return {}


def safe_receipt(tmp_path: Path) -> Path:
    return tmp_path / "receipt.json"


def test_dry_run_is_fixed_no_tools_and_never_starts_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run must not start a process or probe health")

    monkeypatch.setattr(adapter.subprocess, "Popen", forbidden)
    result = adapter.run_worker(
        prompt="hello",
        execute=False,
        user_home=user_omp_home(tmp_path),
        health_probe=forbidden,
    )

    assert result == {
        "command": adapter.fixed_argv("hello", timeout_seconds=120),
        "mode": "dry-run",
        "tools_enabled": False,
    }
    argv = result["command"]
    assert argv[0] == str(Path.home() / ".bun/bin/omp")
    for flag in (
        "--print",
        "--no-session",
        "--no-tools",
        "--no-lsp",
        "--no-pty",
        "--no-extensions",
        "--no-skills",
        "--no-rules",
        "--no-title",
    ):
        assert flag in argv
    assert "--approval-mode" in argv
    assert argv[argv.index("--approval-mode") + 1] == "always-ask"
    assert argv[argv.index("--model") + 1] == "omlxc/coding"
    assert argv[argv.index("--max-time") + 1] == "120"
    assert "--auto-approve" not in argv


def test_symlinked_user_config_root_is_rejected_before_launch(tmp_path: Path) -> None:
    real_home = user_omp_home(tmp_path / "real")
    linked_home = tmp_path / "linked"
    (linked_home / ".omp").mkdir(parents=True)
    os.symlink(real_home / ".omp" / "agent", linked_home / ".omp" / "agent")
    called = False

    def start(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("linked config must reject before launch")

    with pytest.raises(adapter.AdapterError, match="config_root_rejected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            user_home=linked_home,
            popen_factory=start,
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
        )

    assert called is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"baseUrl": "https://cloud.example/v1"},
        {"api": "anthropic-messages"},
        {"authHeader": False},
        {"models": [{"id": "other"}]},
        {"apiKey": "!sh -c 'curl cloud.example'"},
        {"compat": {"unknown": True}},
    ],
)
def test_provider_must_be_audited_local_aetherforge_config(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    with pytest.raises(adapter.AdapterError, match="models_config_rejected"):
        adapter._copy_omlxc_provider(
            user_omp_home(tmp_path, provider_overrides=overrides),
            tmp_path / "isolated",
        )


def test_authoritative_models_yml_works_without_legacy_json(tmp_path: Path) -> None:
    home = user_omp_home(tmp_path, include_json=False)
    destination = tmp_path / "isolated"

    adapter._copy_omlxc_provider(
        home,
        destination,
        api_key_resolver=lambda _command: "temporary-api-key",
    )

    copied = json.loads((destination / "models.json").read_text(encoding="utf-8"))
    assert copied["providers"]["omlxc"]["models"][0]["name"] == "omlxc Coding"


@pytest.mark.parametrize(
    "json_overrides",
    [
        {"baseUrl": "http://127.0.0.1:9999/v1"},
        {"api": "anthropic-messages"},
        {"apiKey": "!security find-generic-password -s other -w"},
        {"authHeader": False},
        {
            "compat": {
                "supportsDeveloperRole": True,
                "supportsReasoningEffort": False,
            }
        },
        {
            "models": [
                {
                    "id": "coding",
                    "name": "drifted",
                    "input": ["text"],
                    "reasoning": False,
                    "supportsTools": True,
                }
            ]
        },
    ],
)
def test_models_json_audited_drift_from_authoritative_yaml_is_rejected(
    tmp_path: Path, json_overrides: dict[str, object]
) -> None:
    def forbidden(_command: str) -> str:
        raise AssertionError("credential lookup must follow config consistency checks")

    with pytest.raises(adapter.AdapterError, match="models_config_rejected"):
        adapter._copy_omlxc_provider(
            user_omp_home(tmp_path, json_overrides=json_overrides),
            tmp_path / "isolated",
            api_key_resolver=forbidden,
        )


@pytest.mark.parametrize("service", ["omlxc", "aetherforge", "other-service"])
def test_keychain_reference_requires_exact_aetherforge_gateway_service(
    tmp_path: Path, service: str
) -> None:
    with pytest.raises(adapter.AdapterError, match="models_config_rejected"):
        adapter._copy_omlxc_provider(
            user_omp_home(
                tmp_path,
                provider_overrides={
                    "apiKey": (f"!security find-generic-password -s {service} -w")
                },
            ),
            tmp_path / "isolated",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


def test_exact_aetherforge_env_identity_is_accepted_and_projected_as_trial_env(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "isolated"
    resolved: list[str] = []

    adapter._copy_omlxc_provider(
        user_omp_home(
            tmp_path,
            provider_overrides={"apiKey": "AETHERFORGE_API_KEY"},
        ),
        destination,
        api_key_resolver=lambda identity: resolved.append(identity) or "env-secret",
    )

    projected = (destination / "models.json").read_text(encoding="utf-8")
    assert resolved == ["AETHERFORGE_API_KEY"]
    assert "OMP_OMLXC_API_KEY" in projected
    assert "AETHERFORGE_API_KEY" not in projected
    assert "env-secret" not in projected


@pytest.mark.parametrize(
    "identity",
    [
        "OPENAI_API_KEY",
        "AETHERFORGE_KEY",
        "${AETHERFORGE_API_KEY}",
        "env-secret",
        "!/usr/bin/security find-generic-password -s aetherforge-gateway -w",
        "!security  find-generic-password -s aetherforge-gateway -w",
    ],
)
def test_other_environment_or_literal_credential_identity_is_rejected(
    tmp_path: Path, identity: str
) -> None:
    with pytest.raises(adapter.AdapterError, match="models_config_rejected"):
        adapter._copy_omlxc_provider(
            user_omp_home(tmp_path, provider_overrides={"apiKey": identity}),
            tmp_path / "isolated",
            api_key_resolver=lambda _identity: "must-not-resolve",
        )


def test_provider_projection_keeps_only_omp_required_allowlist(tmp_path: Path) -> None:
    destination = tmp_path / "isolated"
    home = user_omp_home(
        tmp_path,
        provider_overrides={
            "unknownProvider": "drop",
            "models": [
                {
                    "id": "coding",
                    "name": "omlxc Coding",
                    "input": ["text"],
                    "reasoning": False,
                    "supportsTools": True,
                    "unknownModel": "drop",
                },
                {"id": "other"},
            ],
        },
    )

    resolved: list[str] = []

    def resolve(command: str) -> str:
        resolved.append(command)
        return "temporary-api-key"

    adapter._copy_omlxc_provider(home, destination, api_key_resolver=resolve)

    copied = json.loads((destination / "models.json").read_text(encoding="utf-8"))
    assert copied == {
        "providers": {
            "omlxc": {
                "api": "openai-completions",
                "apiKey": "OMP_OMLXC_API_KEY",
                "authHeader": True,
                "baseUrl": "http://127.0.0.1:9290/v1",
                "compat": {
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
                "models": [
                    {
                        "id": "coding",
                        "name": "omlxc Coding",
                        "input": ["text"],
                        "reasoning": False,
                        "supportsTools": True,
                    }
                ],
            }
        }
    }
    assert stat.S_IMODE((destination / "models.json").stat().st_mode) == 0o600
    assert resolved == ["!security find-generic-password -s aetherforge-gateway -w"]
    assert "temporary-api-key" not in (destination / "models.json").read_text()


def test_execute_uses_isolated_home_fixed_argv_and_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = user_omp_home(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("HTTP_PROXY", "http://secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/secret")

    def start(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return FakeProcess()

    result = adapter.run_worker(
        prompt="inspect only",
        execute=True,
        user_home=home,
        popen_factory=start,
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "16.1.16",
        api_key_resolver=lambda _command: "temporary-api-key",
    )

    assert captured["argv"] == adapter.fixed_argv("inspect only", timeout_seconds=120)
    assert captured["shell"] is False
    assert captured["start_new_session"] is True
    env = captured["env"]
    trial_root = Path(captured["cwd"])
    assert Path(env["HOME"]).is_relative_to(trial_root)
    assert Path(env["PI_CODING_AGENT_DIR"]).is_relative_to(trial_root)
    assert Path(env["PI_CODING_AGENT_SESSION_DIR"]).is_relative_to(trial_root)
    assert "OPENAI_API_KEY" not in env and "HTTP_PROXY" not in env
    assert "GITHUB_TOKEN" not in env and "SSH_AUTH_SOCK" not in env
    assert env["OMP_OMLXC_API_KEY"] == "temporary-api-key"
    assert result["output"] == "reasoned answer\n"


def test_health_identity_mismatch_fails_before_process_start(tmp_path: Path) -> None:
    called = False

    def start(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("health rejection must precede process launch")

    with pytest.raises(adapter.AdapterError, match="health_rejected"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_omp_home(tmp_path),
            popen_factory=start,
            health_probe=lambda: {"status": "ok", "service": "wrong"},
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )

    assert called is False


@pytest.mark.parametrize(
    ("process", "error_code"),
    [
        (FakeProcess(returncode=7), "nonzero_exit"),
        (FakeProcess(stdout=" \n"), "empty_output"),
    ],
)
def test_worker_process_failure_is_stable(
    tmp_path: Path, process: FakeProcess, error_code: str
) -> None:
    with pytest.raises(adapter.AdapterError, match=error_code):
        adapter.run_worker(
            prompt="x",
            execute=True,
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: process,
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


def test_worker_launch_failure_is_stable(tmp_path: Path) -> None:
    def fail_launch(*_args, **_kwargs):
        raise OSError("launch denied")

    with pytest.raises(adapter.AdapterError, match="launch_failed"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            user_home=user_omp_home(tmp_path),
            popen_factory=fail_launch,
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


@pytest.mark.parametrize("timeout_seconds", [0, 121])
@pytest.mark.parametrize("execute", [False, True])
def test_worker_timeout_must_stay_in_admitted_range(
    tmp_path: Path, timeout_seconds: int, execute: bool
) -> None:
    with pytest.raises(adapter.AdapterError, match="timeout_rejected"):
        adapter.run_worker(
            prompt="x",
            execute=execute,
            timeout_seconds=timeout_seconds,
            user_home=tmp_path / "not-read",
        )


def test_success_returns_model_text_but_receipt_contains_only_digest(
    tmp_path: Path,
) -> None:
    receipt = safe_receipt(tmp_path)
    home = user_omp_home(tmp_path, provider_overrides={"apiKey": "AETHERFORGE_API_KEY"})
    model_text = "private model answer\n"
    credential = "receipt-must-not-contain-this-secret"
    launch: dict[str, str] = {}

    def start(*_args, **kwargs):
        launch["cwd"] = kwargs["cwd"]
        launch["marker"] = kwargs["env"]["OMO_OMP_TRIAL_ID"]
        return FakeProcess(stdout=model_text)

    result = adapter.run_worker(
        prompt="private prompt",
        execute=True,
        receipt_path=receipt,
        user_home=home,
        popen_factory=start,
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "16.1.16",
        api_key_resolver=lambda _command: credential,
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert result["output"] == model_text
    assert payload["worker"] == "oh-my-pi"
    assert payload["omp_version"] == "16.1.16"
    assert payload["provider"] == "omlxc"
    assert payload["model"] == "coding"
    assert payload["route_ref"] == "bos://compute/aetherforge/infer"
    assert payload["output_digest"] == adapter.digest_bytes(model_text.encode())
    assert model_text not in json.dumps(payload)
    assert "private prompt" not in json.dumps(payload)
    serialized = json.dumps(payload)
    assert credential not in serialized
    assert str(home) not in serialized
    assert str(Path.home()) not in serialized
    assert launch["marker"] not in serialized
    assert launch["cwd"] not in serialized
    assert "OMO_OMP_TRIAL_ID" not in serialized
    assert "omo-omp-trial" not in serialized
    assert "/Users/" not in serialized
    assert "/private/" not in serialized
    assert payload["checks"] == {
        "aetherforge_health": True,
        "child_reaped": True,
        "session_persisted": False,
        "temp_removed": True,
        "tools_enabled": False,
        "user_config_unchanged": True,
    }


def test_transport_can_run_without_adapter_receipt(tmp_path: Path) -> None:
    result = adapter.run_worker(
        prompt="transport",
        execute=True,
        user_home=user_omp_home(tmp_path),
        popen_factory=lambda *_args, **_kwargs: FakeProcess(
            stdout="transport result\n"
        ),
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "16.1.16",
        api_key_resolver=lambda _command: "temporary-api-key",
    )

    assert result == {"output": "transport result\n", "receipt": None}


def test_timeout_reaps_process_and_fails_closed(tmp_path: Path) -> None:
    child = HungProcess()
    signals: list[signal.Signals] = []

    def terminate(_group: int, value: signal.Signals) -> None:
        signals.append(value)
        if value == signal.SIGKILL:
            child.running = False

    with pytest.raises(adapter.AdapterError, match="timed_out"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            timeout_seconds=1,
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: child,
            health_probe=healthy,
            marker_probe=no_marker,
            group_terminator=terminate,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )

    assert signals == [signal.SIGTERM, signal.SIGKILL]


def test_marker_probe_unavailable_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args, **_kwargs):
        raise OSError("ps unavailable")

    monkeypatch.setattr(adapter.subprocess, "run", unavailable)

    assert adapter._default_marker_probe("OMO_OMP_TRIAL_ID=opaque") is None


def test_reap_probe_failure_only_signals_known_safe_child_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = FakeProcess()
    groups: list[int] = []
    monkeypatch.setattr(adapter.os, "getpgrp", lambda: 54321)

    def terminate(group: int, _value: signal.Signals) -> None:
        groups.append(group)
        child.running = False

    reaped = adapter._reap(
        child,
        marker="OMO_OMP_TRIAL_ID=opaque",
        timeout_seconds=1,
        marker_probe=lambda _marker: None,
        group_terminator=terminate,
    )

    assert reaped is False
    assert groups == [child.pid]
    assert 0 not in groups and 1 not in groups and 54321 not in groups


def test_reap_never_signals_zero_one_or_current_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = FakeProcess()
    child.running = False
    current_group = 54321
    signaled: list[int] = []
    monkeypatch.setattr(adapter.os, "getpgrp", lambda: current_group)

    reaped = adapter._reap(
        child,
        marker="OMO_OMP_TRIAL_ID=opaque",
        timeout_seconds=1,
        marker_probe=lambda _marker: {10: 0, 11: 1, 12: current_group},
        group_terminator=lambda group, _value: signaled.append(group),
    )

    assert reaped is False
    assert signaled == []


def test_default_group_terminator_guards_dangerous_process_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signaled: list[tuple[int, signal.Signals]] = []
    current_group = 54321
    monkeypatch.setattr(adapter.os, "getpgrp", lambda: current_group)
    monkeypatch.setattr(
        adapter.os,
        "killpg",
        lambda group, value: signaled.append((group, value)),
    )

    for group in (0, 1, current_group, 9876):
        adapter._default_group_terminator(group, signal.SIGTERM)

    assert signaled == [(9876, signal.SIGTERM)]


def test_detached_marker_child_is_fail_closed(tmp_path: Path) -> None:
    calls = 0

    def leaked_marker(_marker: str) -> dict[int, int]:
        nonlocal calls
        calls += 1
        return {9876: 9876} if calls >= 2 else {}

    with pytest.raises(adapter.AdapterError, match="process_leaked"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(),
            health_probe=healthy,
            marker_probe=leaked_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


def test_user_omp_config_drift_is_fail_closed(tmp_path: Path) -> None:
    home = user_omp_home(tmp_path)

    class Mutating(FakeProcess):
        def communicate(self, timeout=None):
            (home / ".omp" / "agent" / "settings.json").write_text(
                "changed", encoding="utf-8"
            )
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
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


def test_session_file_is_detected_even_inside_ephemeral_trial(tmp_path: Path) -> None:
    class PersistingSession(FakeProcess):
        def __init__(self, env: dict[str, str]) -> None:
            super().__init__()
            self.session_dir = Path(env["PI_CODING_AGENT_SESSION_DIR"])

        def communicate(self, timeout=None):
            (self.session_dir / "session.jsonl").write_text("{}", encoding="utf-8")
            return super().communicate(timeout)

    with pytest.raises(adapter.AdapterError, match="session_persisted"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **kwargs: PersistingSession(kwargs["env"]),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )


def test_trial_allows_ephemeral_omp_sqlite_state_then_removes_it(
    tmp_path: Path,
) -> None:
    class Caching(FakeProcess):
        def __init__(self, env: dict[str, str]) -> None:
            super().__init__()
            self.agent_dir = Path(env["PI_CODING_AGENT_DIR"])

        def communicate(self, timeout=None):
            for name in ("agent.db", "models.db", "history.db"):
                (self.agent_dir / name).write_bytes(b"ephemeral")
            return super().communicate(timeout)

    result = adapter.run_worker(
        prompt="x",
        execute=True,
        receipt_path=safe_receipt(tmp_path),
        user_home=user_omp_home(tmp_path),
        popen_factory=lambda *_args, **kwargs: Caching(kwargs["env"]),
        health_probe=healthy,
        marker_probe=no_marker,
        version_reader=lambda: "16.1.16",
        api_key_resolver=lambda _command: "temporary-api-key",
    )

    assert result["receipt"]["checks"]["temp_removed"] is True


def test_failed_trial_removal_is_cleanup_unconfirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[Path] = []

    def leave_trial(path: Path, **_kwargs) -> None:
        created.append(Path(path))

    monkeypatch.setattr(adapter.shutil, "rmtree", leave_trial)
    with pytest.raises(adapter.AdapterError, match="cleanup_unconfirmed"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=safe_receipt(tmp_path),
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )

    monkeypatch.undo()
    for path in created:
        shutil.rmtree(path)


@pytest.mark.parametrize("existing", [False, True])
def test_unsafe_or_existing_receipt_is_rejected(tmp_path: Path, existing: bool) -> None:
    receipt = (
        safe_receipt(tmp_path)
        if existing
        else Path.cwd() / f"unsafe-omp-receipt-{tmp_path.name}.json"
    )
    if existing:
        receipt.write_text("existing", encoding="utf-8")

    with pytest.raises(adapter.AdapterError, match="unsafe_receipt"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            user_home=user_omp_home(tmp_path),
        )


def test_output_mismatch_never_persists_stderr_secret(tmp_path: Path) -> None:
    receipt = safe_receipt(tmp_path)
    secret = "stderr-super-secret"

    with pytest.raises(adapter.AdapterError, match="output_mismatch"):
        adapter.run_worker(
            prompt="x",
            execute=True,
            receipt_path=receipt,
            expect_exact="expected",
            user_home=user_omp_home(tmp_path),
            popen_factory=lambda *_args, **_kwargs: FakeProcess(
                stdout="wrong\n", stderr=secret
            ),
            health_probe=healthy,
            marker_probe=no_marker,
            version_reader=lambda: "16.1.16",
            api_key_resolver=lambda _command: "temporary-api-key",
        )

    assert secret not in receipt.read_text(encoding="utf-8")


def test_version_reader_accepts_only_pinned_bun_omp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        adapter, "_binary_digest", lambda _path: adapter.EXPECTED_OMP_SHA256
    )
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [adapter.OMP_EXECUTABLE, "--version"],
            0,
            stdout="omp/16.1.16",
            stderr="",
        ),
    )

    assert adapter._default_version_reader() == "16.1.16"


@pytest.mark.parametrize(
    ("version", "digest"),
    [
        (
            "omp/17.2.15",
            "0b690fc3cbf940aa86723f029c0206ddfba152dfa6aa180b891b8923c35f5c96",
        ),
        ("omp/16.1.16", "0" * 64),
    ],
)
def test_version_or_sha_drift_is_rejected(
    version: str, digest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adapter, "_binary_digest", lambda _path: digest)
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [adapter.OMP_EXECUTABLE, "--version"], 0, stdout=version, stderr=""
        ),
    )

    with pytest.raises(adapter.AdapterError, match="version_unavailable"):
        adapter._default_version_reader()


def test_keychain_reference_is_resolved_shell_free_in_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def run(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="temporary-key\n", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", run)

    assert (
        adapter._resolve_keychain_api_key(
            "!security find-generic-password -s aetherforge-gateway -w"
        )
        == "temporary-key"
    )
    assert captured["argv"] == [
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        "aetherforge-gateway",
        "-w",
    ]
    assert captured["shell"] is False


def test_exact_aetherforge_env_identity_reads_parent_secret_without_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AETHERFORGE_API_KEY", "parent-env-secret")
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("present env secret must not invoke Keychain")
        ),
    )

    assert (
        adapter._resolve_keychain_api_key("AETHERFORGE_API_KEY") == "parent-env-secret"
    )


def test_missing_aetherforge_env_identity_falls_back_to_fixed_keychain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.delenv("AETHERFORGE_API_KEY", raising=False)

    def run(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            argv, 0, stdout="keychain-secret\n", stderr=""
        )

    monkeypatch.setattr(adapter.subprocess, "run", run)

    assert adapter._resolve_keychain_api_key("AETHERFORGE_API_KEY") == "keychain-secret"
    assert captured["argv"] == [
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        "aetherforge-gateway",
        "-w",
    ]
    assert captured["shell"] is False


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(1, "ignored\n"), (0, " \n")],
)
def test_keychain_nonzero_or_empty_is_credential_unavailable(
    returncode: int,
    stdout: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv, returncode, stdout=stdout, stderr=""
        ),
    )

    with pytest.raises(adapter.AdapterError, match="credential_unavailable"):
        adapter._resolve_keychain_api_key(
            "!security find-generic-password -s aetherforge-gateway -w"
        )


def test_keychain_launch_failure_is_credential_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("security unavailable")

    monkeypatch.setattr(adapter.subprocess, "run", fail)

    with pytest.raises(adapter.AdapterError, match="credential_unavailable"):
        adapter._resolve_keychain_api_key(
            "!security find-generic-password -s aetherforge-gateway -w"
        )


def test_cli_only_forwards_successful_model_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        adapter,
        "run_worker",
        lambda **_kwargs: {"output": "model text\n", "receipt": None},
    )

    assert adapter.main(["run", "--prompt", "x", "--execute"]) == 0
    assert capsys.readouterr().out == "model text\n"
