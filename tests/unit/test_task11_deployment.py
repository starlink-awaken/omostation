"""Task 11 deployment blocker contracts."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import httpx
import pytest
from typer.testing import CliRunner

import omlxc.cli as cli_module
from omlxc.adapters import LmStudioAdapter, TailscaleAdapter, TailscaleNodePolicy
from omlxc.adapters.process import ProcessOutput, ProcessOutputDecodeError, decode_process_output
from omlxc.cli import app
from omlxc.config import AppConfig, BackendConfig, DaemonConfig, NodeConfig, StorageConfig
from omlxc.domain import BackendKind
from omlxc.domain.protocols import BackendAdapter, OperationStatus
from omlxc.service import LaunchdController, LaunchdFailure, LaunchdPaths


class RecordingRunner:
    def __init__(self, outputs: list[ProcessOutput] | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], float]] = []
        self.outputs = list(outputs or [])

    async def __call__(self, argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        self.calls.append((argv, timeout))
        return self.outputs.pop(0) if self.outputs else ProcessOutput(0, "ok", "")


@pytest.mark.asyncio
async def test_launchd_controller_uses_exact_user_domain_argv_and_preserves_uninstall_backup(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    paths = LaunchdPaths.for_home(home)
    paths.executable.parent.mkdir(parents=True)
    paths.executable.write_text("binary", encoding="utf-8")
    paths.executable.chmod(0o700)
    runner = RecordingRunner(
        [
            ProcessOutput(0, "", ""),
            ProcessOutput(0, "", ""),
            ProcessOutput(0, "", ""),
            ProcessOutput(0, "", ""),
            ProcessOutput(0, "", ""),
            ProcessOutput(3, "", "Boot-out failed: 3: No such process"),
        ]
    )
    controller = LaunchdController(paths, uid=501, process_runner=runner)

    installed = await controller.install()
    assert installed.plist_path == paths.plist_path
    assert runner.calls[0][0] == (
        "/bin/launchctl",
        "bootstrap",
        "gui/501",
        str(paths.plist_path),
    )
    await controller.status()
    await controller.start()
    await controller.stop()
    await controller.restart()
    removed = await controller.uninstall()

    assert [call[0] for call in runner.calls[1:]] == [
        ("/bin/launchctl", "print", "gui/501/com.omlxc.daemon"),
        ("/bin/launchctl", "bootstrap", "gui/501", str(paths.plist_path)),
        ("/bin/launchctl", "bootout", "gui/501/com.omlxc.daemon"),
        ("/bin/launchctl", "kickstart", "-k", "gui/501/com.omlxc.daemon"),
        ("/bin/launchctl", "bootout", "gui/501/com.omlxc.daemon"),
    ]
    assert removed.backup_path is not None and removed.backup_path.read_bytes()
    assert not paths.plist_path.exists()
    assert paths.log_directory.exists() and paths.data_directory.exists()


@pytest.mark.asyncio
async def test_launchd_failure_is_typed_and_sanitized(tmp_path: Path) -> None:
    runner = RecordingRunner([ProcessOutput(5, "secret-status", "private-detail")])
    controller = LaunchdController(LaunchdPaths.for_home(tmp_path), uid=501, process_runner=runner)

    with pytest.raises(LaunchdFailure) as captured:
        await controller.status()

    assert captured.value.code == "E200"
    assert "secret-status" not in str(captured.value)
    assert "private-detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_uninstall_does_not_swallow_unrelated_launchctl_exit_three(tmp_path: Path) -> None:
    paths = LaunchdPaths.for_home(tmp_path)
    paths.plist_path.parent.mkdir(parents=True)
    paths.plist_path.write_text("private plist", encoding="utf-8")
    runner = RecordingRunner([ProcessOutput(3, "", "Boot-out failed: permission denied")])
    controller = LaunchdController(paths, uid=501, process_runner=runner)

    with pytest.raises(LaunchdFailure) as captured:
        await controller.uninstall()

    assert captured.value.code == "E500"
    assert paths.plist_path.read_text(encoding="utf-8") == "private plist"
    assert not tuple(paths.plist_path.parent.glob("*.uninstalled-*"))


def test_cli_daemon_apply_requires_r2_gate_before_lifecycle_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    class FakeController:
        async def install(self) -> object:
            calls.append("install")
            return type("Result", (), {"plist_path": tmp_path / "x", "snapshot_path": None})()

    monkeypatch.setattr(cli_module, "_launchd_controller", lambda _home=None: FakeController())
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False)
    runner = CliRunner()

    refused = runner.invoke(app, ["daemon", "install", "--apply", "--yes", "--json"])
    accepted = runner.invoke(
        app,
        ["daemon", "install", "--apply", "--yes", "--confirm-impact", "--json"],
    )

    assert refused.exit_code == 7 and calls == ["install"]
    assert accepted.exit_code == 0
    assert json.loads(accepted.stdout.splitlines()[-1])["data"]["status"] == "installed"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b'{"models":[]}', '{"models":[]}'),
        (b"\xff\xfe" + '{"models":[]}'.encode("utf-16-le"), '{"models":[]}'),
        (b"\xfe\xff" + '{"models":[]}'.encode("utf-16-be"), '{"models":[]}'),
    ],
)
def test_windows_process_output_decodes_utf8_and_utf16(payload: bytes, expected: str) -> None:
    assert decode_process_output(payload) == expected


@pytest.mark.parametrize(
    "payload",
    [
        b"#< CLIXML\r\n<Objs><S>private-remote-detail</S></Objs>",
        b"\xff\x00\xfe\x00\x80",
    ],
)
def test_windows_process_output_rejects_clixml_or_invalid_bytes_without_leak(
    payload: bytes,
) -> None:
    with pytest.raises(ProcessOutputDecodeError) as captured:
        decode_process_output(payload)
    assert "private-remote-detail" not in str(captured.value)
    assert "private-remote-detail" not in repr(captured.value)


def test_tailscale_schema_round_trip_and_security_policy(tmp_path: Path) -> None:
    executable = tmp_path / "tailscale"
    config = AppConfig.model_validate(
        {
            "schema_version": 1,
            "daemon": {"socket_path": tmp_path / "daemon.sock"},
            "storage": {"database_path": tmp_path / "state.db"},
            "tailscale": {
                "executable": executable,
                "snapshot_ttl_seconds": 45,
            },
            "nodes": [
                {
                    "id": "remote",
                    "display_name": "Remote",
                    "platform": "windows",
                    "tailscale": {
                        "peer_id": "peer_identifier_123456",
                        "public_key": "nodekey:abcdefghijklmnopqrstuvwxyz1234",
                        "magic_dns_name": "remote.example.ts.net",
                        "allowed_ips": ["100.64.0.10"],
                        "allowed_http_ports": [1234, 11434],
                        "allowed_ssh_users": ["operator"],
                    },
                }
            ],
        }
    )

    payload = config.model_dump(mode="json")
    restored = AppConfig.model_validate(payload)
    assert restored == config
    assert restored.tailscale.snapshot_ttl_seconds == 45
    assert restored.nodes[0].tailscale is not None
    assert restored.nodes[0].tailscale.allowed_http_ports == (1234, 11434)


def test_user_config_loader_reads_default_file_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import omlxc.config.loading as loading_module

    target = tmp_path / "config.toml"
    target.write_text(
        "schema_version = 1\n[storage]\nretention_days = 77\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(loading_module, "default_config_path", lambda: target)

    loaded = loading_module.load_user_config(env={}, base_directory=tmp_path)

    assert loaded.storage.retention_days == 77


def test_lm_remote_control_config_requires_known_hosts_pair(tmp_path: Path) -> None:
    common = {
        "id": "lm",
        "node_id": "remote",
        "kind": BackendKind.LM_STUDIO,
        "base_url": "http://remote.example.ts.net:1234",
        "control_endpoint": "operator@remote.example.ts.net",
    }
    with pytest.raises(ValueError, match="known_hosts"):
        BackendConfig(**common)

    backend = BackendConfig(
        **common,
        known_hosts_file=tmp_path / "known_hosts",
        lms_platform="windows",
        probe_model_id="model-a",
    )
    assert backend.known_hosts_file == tmp_path / "known_hosts"
    assert backend.lms_platform == "windows"


def test_production_lm_factory_passes_remote_control_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import omlxc.daemon.composition as composition_module

    captured: dict[str, object] = {}

    class FakeLmStudio:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    known_hosts = tmp_path / "known_hosts"
    config = AppConfig(
        daemon=DaemonConfig(socket_path=tmp_path / "daemon.sock"),
        storage=StorageConfig(database_path=tmp_path / "state.db"),
        nodes=(NodeConfig(id="remote", display_name="Remote", platform="windows"),),
        backends=(
            BackendConfig(
                id="lm",
                node_id="remote",
                kind=BackendKind.LM_STUDIO,
                base_url="http://127.0.0.1:1234",
                control_endpoint="operator@remote.example.ts.net",
                known_hosts_file=known_hosts,
                lms_platform="windows",
                probe_model_id="model-a",
            ),
        ),
    )
    monkeypatch.setattr(composition_module, "LmStudioAdapter", FakeLmStudio)

    adapters = composition_module.build_configured_adapters(config)

    assert set(adapters) == {"lm"}
    assert captured["ssh_target"] == "operator@remote.example.ts.net"
    assert captured["known_hosts_file"] == known_hosts
    assert str(captured["platform"]) == "windows"
    assert captured["probe_model_id"] == "model-a"


@pytest.mark.asyncio
async def test_production_lm_factory_binds_per_control_tailscale_authorizer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import omlxc.daemon.composition as composition_module

    captured: dict[str, object] = {}
    authorization_calls: list[tuple[str, str]] = []

    class FakeLmStudio:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class FakeTailscale:
        def authorize_ssh(self, node_id: str, target: str) -> object:
            authorization_calls.append((node_id, target))
            return type("Authorized", (), {"target": target})()

    backend = BackendConfig(
        id="lm",
        node_id="remote",
        kind=BackendKind.LM_STUDIO,
        base_url="http://remote.example.ts.net:1234",
        control_endpoint="operator@remote.example.ts.net",
        known_hosts_file=tmp_path / "known_hosts",
    )
    monkeypatch.setattr(composition_module, "LmStudioAdapter", FakeLmStudio)
    composition_module.build_configured_adapter(
        backend,
        tailscale=cast(TailscaleAdapter, FakeTailscale()),
    )
    authorizer = cast("Callable[[str], Awaitable[None]]", captured["control_authorizer"])

    await authorizer("operator@remote.example.ts.net")

    assert authorization_calls == [("remote", "operator@remote.example.ts.net")]


def test_doctor_direct_is_read_only_and_does_not_use_daemon_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = AppConfig(
        daemon=DaemonConfig(socket_path=tmp_path / "daemon.sock"),
        storage=StorageConfig(database_path=tmp_path / "state.db"),
        nodes=(NodeConfig(id="local", display_name="Local", platform="macos"),),
    )
    calls: list[str] = []

    async def fake_doctor(_config: AppConfig) -> dict[str, object]:
        calls.append("doctor")
        return {"status": "healthy", "checks": [{"name": "config", "ok": True}]}

    monkeypatch.setattr(cli_module, "load_user_config", lambda *_a, **_k: config)
    monkeypatch.setattr(cli_module, "run_direct_doctor", fake_doctor)
    monkeypatch.setattr(
        cli_module,
        "_client_factory",
        lambda _path: pytest.fail("direct doctor must not construct daemon client"),
    )
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    result = CliRunner().invoke(app, ["doctor", "--direct", "--json"])

    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["status"] == "healthy"
    assert calls == ["doctor"]
    assert before == after
    assert not config.storage.database_path.exists()


@pytest.mark.asyncio
async def test_real_direct_doctor_does_not_create_database_or_config(tmp_path: Path) -> None:
    from omlxc.diagnostics import run_direct_doctor

    config = AppConfig(
        daemon=DaemonConfig(socket_path=tmp_path / "daemon.sock"),
        storage=StorageConfig(database_path=tmp_path / "state.db"),
    )
    before = tuple(tmp_path.rglob("*"))

    result = await run_direct_doctor(config)

    assert result["status"] == "degraded"
    assert before == tuple(tmp_path.rglob("*")) == ()
    assert not config.storage.database_path.exists()


@pytest.mark.asyncio
async def test_production_composition_builds_tailscale_and_authorizes_before_remote_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from datetime import UTC, datetime

    import omlxc.daemon.composition as composition_module
    from omlxc.domain.protocols import CapabilitySnapshot

    events: list[str] = []

    class FakeTailscale:
        def __init__(self, **kwargs: object) -> None:
            events.append("constructed")
            assert kwargs["snapshot_ttl_seconds"] == 45
            policies = kwargs["policies"]
            assert isinstance(policies, tuple) and policies[0].node_id == "remote"

        async def snapshot(self) -> object:
            events.append("snapshot")
            return object()

        def authorize_http(self, node_id: str, base_url: str) -> object:
            events.append(f"authorize:{node_id}:{base_url}")
            return object()

        def authorize_ssh(self, node_id: str, target: str) -> object:
            events.append(f"authorize-ssh:{node_id}:{target}")
            return type("Authorized", (), {"target": target})()

    class FakeBackend:
        async def discover(self) -> CapabilitySnapshot:
            events.append("discover")
            return CapabilitySnapshot(
                backend_id="lm",
                reachable=True,
                compatible=True,
                model_available=True,
                generation_ready=True,
                capabilities=frozenset(),
                observed_at=datetime.now(UTC),
            )

        async def list_models(self) -> tuple[object, ...]:
            return ()

        async def aclose(self) -> None:
            return None

    executable = tmp_path / "trusted" / "tailscale"
    executable.parent.mkdir(mode=0o700)
    executable.write_text("fixture", encoding="utf-8")
    executable.chmod(0o700)
    config = AppConfig.model_validate(
        {
            "schema_version": 1,
            "daemon": {"socket_path": tmp_path / "daemon.sock", "probe_interval_seconds": 60.0},
            "storage": {"database_path": tmp_path / "state.db"},
            "tailscale": {"executable": executable, "snapshot_ttl_seconds": 45},
            "nodes": [
                {
                    "id": "remote",
                    "display_name": "Remote",
                    "platform": "windows",
                    "tailscale": {
                        "peer_id": "peer_identifier_123456",
                        "public_key": "nodekey:abcdefghijklmnopqrstuvwxyz1234",
                        "magic_dns_name": "remote.example.ts.net",
                        "allowed_ips": ["100.64.0.10"],
                        "allowed_http_ports": [1234],
                        "allowed_ssh_users": ["operator"],
                    },
                }
            ],
            "backends": [
                {
                    "id": "lm",
                    "node_id": "remote",
                    "kind": "lm_studio",
                    "base_url": "http://remote.example.ts.net:1234",
                    "control_endpoint": "operator@remote.example.ts.net",
                    "known_hosts_file": tmp_path / "known_hosts",
                }
            ],
        }
    )
    monkeypatch.setattr(composition_module, "TailscaleAdapter", FakeTailscale)
    composition = composition_module.build_production_daemon(
        config, adapters={"lm": cast(BackendAdapter, FakeBackend())}
    )

    await composition.runtime.start()
    await composition.runtime.close()

    assert events[:4] == [
        "constructed",
        "snapshot",
        "authorize:remote:http://remote.example.ts.net:1234",
        "authorize-ssh:remote:operator@remote.example.ts.net",
    ]
    assert events[4] == "discover"


@pytest.mark.asyncio
async def test_remote_lm_discovery_denies_mismatched_ssh_target_before_adapter_call(
    tmp_path: Path,
) -> None:
    import omlxc.daemon.composition as composition_module

    events: list[str] = []

    class DenyingTailscale:
        async def snapshot(self) -> object:
            events.append("snapshot")
            return object()

        def authorize_http(self, node_id: str, base_url: str) -> object:
            events.append(f"http:{node_id}:{base_url}")
            return object()

        def authorize_ssh(self, node_id: str, target: str) -> object:
            events.append(f"ssh:{node_id}:{target}")
            raise PermissionError("mismatched SSH identity")

    class NeverDiscover:
        async def discover(self) -> object:
            events.append("discover")
            raise AssertionError("adapter discovery would execute SSH control")

        async def list_models(self) -> tuple[object, ...]:
            return ()

        async def aclose(self) -> None:
            return None

    config = AppConfig.model_validate(
        {
            "schema_version": 1,
            "daemon": {"socket_path": tmp_path / "daemon.sock", "probe_interval_seconds": 60.0},
            "storage": {"database_path": tmp_path / "state.db"},
            "nodes": [
                {
                    "id": "node-a",
                    "display_name": "Node A",
                    "platform": "windows",
                    "tailscale": {
                        "peer_id": "peer_identifier_123456",
                        "public_key": "nodekey:abcdefghijklmnopqrstuvwxyz1234",
                        "magic_dns_name": "node-a.example.ts.net",
                        "allowed_ips": ["100.64.0.10"],
                        "allowed_http_ports": [1234],
                        "allowed_ssh_users": ["operator"],
                    },
                }
            ],
            "backends": [
                {
                    "id": "lm",
                    "node_id": "node-a",
                    "kind": "lm_studio",
                    "base_url": "http://node-a.example.ts.net:1234",
                    "control_endpoint": "intruder@node-b.example.ts.net",
                    "known_hosts_file": tmp_path / "known_hosts",
                }
            ],
        }
    )
    composition = composition_module.build_production_daemon(
        config,
        adapters={"lm": cast(BackendAdapter, NeverDiscover())},
        tailscale=cast(TailscaleAdapter, DenyingTailscale()),
    )

    await composition.runtime.start()
    await composition.runtime.close()

    assert events == [
        "snapshot",
        "http:node-a:http://node-a.example.ts.net:1234",
        "ssh:node-a:intruder@node-b.example.ts.net",
    ]


def _tailscale_status() -> str:
    return json.dumps(
        {
            "Self": {
                "ID": "self_peer_identifier_1234",
                "PublicKey": "nodekey:selfabcdefghijklmnopqrstuvwxyz",
                "HostName": "mbp",
                "DNSName": "mbp.example.ts.net.",
                "TailscaleIPs": ["100.64.0.1"],
                "Online": True,
                "OS": "macOS",
            },
            "Peer": {
                "nodekey:remoteabcdefghijklmnopqrstuv": {
                    "ID": "remote_peer_identifier_1",
                    "PublicKey": "nodekey:remoteabcdefghijklmnopqrstuv",
                    "HostName": "remote",
                    "DNSName": "remote.example.ts.net.",
                    "TailscaleIPs": ["100.64.0.10"],
                    "Online": True,
                    "OS": "windows",
                }
            },
        }
    )


def _trusted_tailscale_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "trusted-bin" / "tailscale"
    executable.parent.mkdir(mode=0o700)
    executable.write_text("fixture", encoding="utf-8")
    executable.chmod(0o700)
    return executable


@pytest.mark.asyncio
async def test_lm_load_reauthorizes_every_ssh_control_and_blocks_expired_snapshot(
    tmp_path: Path,
) -> None:
    monotonic = [0.0]
    ssh_calls: list[tuple[str, ...]] = []

    async def tailscale_runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, _tailscale_status(), "")

    tailscale = TailscaleAdapter(
        policies=(
            TailscaleNodePolicy(
                node_id="remote",
                expected_peer_id="remote_peer_identifier_1",
                expected_public_key="nodekey:remoteabcdefghijklmnopqrstuv",
                magic_dns_name="remote.example.ts.net",
                allowed_ips=frozenset({"100.64.0.10"}),
                allowed_http_ports=frozenset({1234}),
                allowed_ssh_users=frozenset({"operator"}),
            ),
        ),
        tailscale_executable=_trusted_tailscale_executable(tmp_path),
        process_runner=tailscale_runner,
        snapshot_ttl_seconds=30,
        monotonic_clock=lambda: monotonic[0],
    )
    await tailscale.snapshot()

    async def authorize(target: str) -> None:
        accepted = tailscale.authorize_ssh("remote", target)
        if accepted.target != target:
            raise PermissionError

    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("fixture", encoding="utf-8")
    known_hosts.chmod(0o600)

    async def control_runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        ssh_calls.append(argv)
        return ProcessOutput(0, "[]", "")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "model-a"}]})

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://remote.example.ts.net:1234",
        ssh_target="operator@remote.example.ts.net",
        known_hosts_file=known_hosts,
        process_runner=control_runner,
        control_authorizer=authorize,
        transport=httpx.MockTransport(handler),
    )
    await adapter.list_models()
    assert len(ssh_calls) == 1

    monotonic[0] = 31.0
    result = await adapter.load_model("model-a")

    assert result.status is OperationStatus.FAILED
    assert len(ssh_calls) == 1


@pytest.mark.asyncio
async def test_lm_load_with_fresh_per_call_authorization_executes_each_control_once(
    tmp_path: Path,
) -> None:
    authorizations: list[str] = []
    ssh_calls: list[tuple[str, ...]] = []
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("fixture", encoding="utf-8")
    known_hosts.chmod(0o600)

    async def authorize(target: str) -> None:
        authorizations.append(target)

    outputs = iter(
        (
            ProcessOutput(0, "[]", ""),
            ProcessOutput(0, "ok", ""),
            ProcessOutput(
                0,
                '[{"modelKey":"model-a","identifier":"model-a"}]',
                "",
            ),
        )
    )

    async def control_runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        ssh_calls.append(argv)
        return next(outputs)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "model-a"}]})

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://remote.example.ts.net:1234",
        ssh_target="operator@remote.example.ts.net",
        known_hosts_file=known_hosts,
        process_runner=control_runner,
        control_authorizer=authorize,
        transport=httpx.MockTransport(handler),
    )

    result = await adapter.load_model("model-a")

    assert result.status is OperationStatus.SUCCEEDED
    assert len(authorizations) == len(ssh_calls) == 3
