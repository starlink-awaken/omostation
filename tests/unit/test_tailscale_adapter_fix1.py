"""Review regressions for trusted execution, strict peer keys, and freshness."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import omlxc.adapters.lmstudio as lmstudio_module
from omlxc.adapters.process import ProcessOutput
from omlxc.adapters.tailscale import (
    TailscaleAdapter,
    TailscaleErrorCode,
    TailscaleFailure,
    TailscaleNodePolicy,
)

_PEER_KEY = "nodekey:FAKEPEER000000000000000000000001"
_DNS = "compute-a.example.test"
_MINIMAL_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C",
    "LC_ALL": "C",
}


def _executable(tmp_path: Path) -> Path:
    executable = tmp_path / "tailscale-fake"
    executable.write_text("review fixture; never executed\n", encoding="utf-8")
    executable.chmod(0o700)
    return executable


def _policy() -> TailscaleNodePolicy:
    return TailscaleNodePolicy(
        node_id="node-a",
        expected_peer_id="peeridFAKE000000000000000000000001",
        expected_public_key=_PEER_KEY,
        magic_dns_name=_DNS,
        allowed_ips=frozenset({"100.64.0.10"}),
        allowed_http_ports=frozenset({1234}),
        allowed_ssh_users=frozenset({"operator"}),
    )


def _status(*, map_key: str = _PEER_KEY, online: bool = True) -> dict[str, object]:
    return {
        "Self": {
            "ID": "peeridFAKESELF000000000000000000000",
            "PublicKey": "nodekey:FAKESELF000000000000000000000000",
            "HostName": "controller",
            "DNSName": "controller.example.test.",
            "TailscaleIPs": ["100.64.0.1"],
            "Online": True,
            "OS": "macOS",
        },
        "Peer": {
            map_key: {
                "ID": "peeridFAKE000000000000000000000001",
                "PublicKey": _PEER_KEY,
                "HostName": "compute-a",
                "DNSName": f"{_DNS}.",
                "TailscaleIPs": ["100.64.0.10"],
                "Online": online,
                "OS": "linux",
            }
        },
    }


def _runner(documents: list[object], calls: list[tuple[str, ...]] | None = None) -> Any:
    responses = iter(documents)

    async def run(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        if calls is not None:
            calls.append(argv)
        document = next(responses)
        if isinstance(document, Exception):
            raise document
        if isinstance(document, str):
            return ProcessOutput(0, document, "")
        return ProcessOutput(0, json.dumps(document), "")

    return run


@pytest.mark.parametrize("case", ["relative", "missing", "directory", "writable", "not-executable"])
def test_trusted_executable_rejects_invalid_path_or_mode(tmp_path: Path, case: str) -> None:
    executable = _executable(tmp_path)
    if case == "relative":
        executable = Path("tailscale-fake")
    elif case == "missing":
        executable = tmp_path / "missing"
    elif case == "directory":
        executable = tmp_path
    elif case == "writable":
        executable.chmod(0o722)
    elif case == "not-executable":
        executable.chmod(0o600)

    with pytest.raises(ValueError, match="trusted Tailscale executable"):
        TailscaleAdapter(
            policies=(_policy(),),
            tailscale_executable=executable,
            process_runner=_runner([_status()]),
        )


def test_trusted_executable_rejects_symlink_and_symlink_ancestor(tmp_path: Path) -> None:
    executable = _executable(tmp_path)
    direct_link = tmp_path / "tailscale-link"
    direct_link.symlink_to(executable)
    real_dir = tmp_path / "real-bin"
    real_dir.mkdir()
    nested = _executable(real_dir)
    directory_link = tmp_path / "linked-bin"
    directory_link.symlink_to(real_dir, target_is_directory=True)

    for candidate in (direct_link, directory_link / nested.name):
        with pytest.raises(ValueError, match="trusted Tailscale executable"):
            TailscaleAdapter(
                policies=(_policy(),),
                tailscale_executable=candidate,
                process_runner=_runner([_status()]),
            )


def test_trusted_executable_rejects_untrusted_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _executable(tmp_path)
    owner = executable.stat().st_uid
    if owner == 0:
        pytest.skip("root-owned fixture is an explicitly trusted owner")
    monkeypatch.setattr(os, "geteuid", lambda: owner + 1)

    with pytest.raises(ValueError, match="trusted Tailscale executable"):
        TailscaleAdapter(
            policies=(_policy(),),
            tailscale_executable=executable,
            process_runner=_runner([_status()]),
        )


@pytest.mark.asyncio
async def test_refresh_revalidates_executable_before_injected_runner(tmp_path: Path) -> None:
    executable = _executable(tmp_path)
    calls: list[tuple[str, ...]] = []
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()], calls),
    )
    executable.chmod(0o722)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code.value == "spawn"
    assert calls == []


@pytest.mark.asyncio
async def test_injected_runner_receives_resolved_absolute_executable(tmp_path: Path) -> None:
    executable = _executable(tmp_path)
    calls: list[tuple[str, ...]] = []
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()], calls),
    )

    await adapter.snapshot()

    assert calls == [(str(executable.resolve()), "status", "--json")]


class _Reader:
    def __init__(self, value: bytes) -> None:
        self._value = value

    async def read(self, size: int = -1) -> bytes:
        del size
        value, self._value = self._value, b""
        return value


class _Process:
    def __init__(self, stdout: bytes) -> None:
        self.stdout = _Reader(stdout)
        self.stderr = _Reader(b"")
        self.returncode: int | None = None

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


@pytest.mark.asyncio
async def test_default_tailscale_spawn_uses_exact_minimal_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _executable(tmp_path)
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    async def fake_exec(*argv: str, **kwargs: object) -> _Process:
        calls.append((argv, kwargs))
        return _Process(json.dumps(_status()).encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
    )

    await adapter.snapshot()

    assert calls == [
        (
            (str(executable.resolve()), "status", "--json"),
            {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "env": _MINIMAL_ENV,
            },
        )
    ]


@pytest.mark.asyncio
async def test_lm_default_process_runner_explicitly_preserves_inherited_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_exec(*argv: str, **kwargs: object) -> _Process:
        del argv
        calls.append(kwargs)
        return _Process(b"ok")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    await lmstudio_module._default_process_runner(("ssh", "-T"), 1.0)

    assert calls[0]["env"] is None


@pytest.mark.asyncio
async def test_arbitrary_peer_mapping_key_fails_even_without_nodekey_prefix(tmp_path: Path) -> None:
    executable = _executable(tmp_path)
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status(map_key="arbitrary-peer-index")]),
    )

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.INVALID_SNAPSHOT


@pytest.mark.asyncio
async def test_snapshot_records_utc_observation_and_ttl_boundary(tmp_path: Path) -> None:
    executable = _executable(tmp_path)
    monotonic = [100.0]
    observed = datetime(2026, 8, 11, 3, 4, tzinfo=UTC)
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()]),
        snapshot_ttl_seconds=10,
        monotonic_clock=lambda: monotonic[0],
        wall_clock=lambda: observed,
    )

    snapshot = await adapter.snapshot()
    monotonic[0] = 110.0
    endpoint = adapter.authorize_http("node-a", f"http://{_DNS}:1234")

    assert snapshot.observed_at == observed
    assert snapshot.observed_at.tzinfo is UTC
    assert endpoint.port == 1234
    dumped = repr(snapshot.model_dump())
    for sensitive in (_PEER_KEY, _DNS, "100.64.0.10"):
        assert sensitive not in dumped


@pytest.mark.asyncio
@pytest.mark.parametrize("current", [110.0001, 99.9999])
async def test_expired_or_rolled_back_monotonic_clock_is_typed_stale(
    tmp_path: Path, current: float
) -> None:
    executable = _executable(tmp_path)
    monotonic = [100.0]
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()]),
        snapshot_ttl_seconds=10,
        monotonic_clock=lambda: monotonic[0],
    )
    await adapter.snapshot()
    monotonic[0] = current

    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_ssh("node-a", f"operator@{_DNS}")

    assert captured.value.code.value == "stale"


@pytest.mark.asyncio
async def test_failed_refresh_clears_old_snapshot_and_successful_refresh_renews_ttl(
    tmp_path: Path,
) -> None:
    executable = _executable(tmp_path)
    monotonic = [10.0]
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status(), "not-json", _status()]),
        snapshot_ttl_seconds=5,
        monotonic_clock=lambda: monotonic[0],
    )
    await adapter.snapshot()
    monotonic[0] = 14.0
    assert adapter.authorize_http("node-a", f"http://{_DNS}:1234").port == 1234

    with pytest.raises(TailscaleFailure):
        await adapter.snapshot()
    with pytest.raises(TailscaleFailure) as cleared:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert cleared.value.code is TailscaleErrorCode.UNKNOWN_NODE

    monotonic[0] = 20.0
    await adapter.snapshot()
    monotonic[0] = 25.0
    assert adapter.authorize_http("node-a", f"http://{_DNS}:1234").port == 1234


@pytest.mark.parametrize("ttl", [True, 0, 301, 1.5])
def test_snapshot_ttl_is_strictly_typed_and_bounded(tmp_path: Path, ttl: object) -> None:
    with pytest.raises(ValueError, match="snapshot TTL"):
        TailscaleAdapter(
            policies=(_policy(),),
            tailscale_executable=_executable(tmp_path),
            process_runner=_runner([_status()]),
            snapshot_ttl_seconds=ttl,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["?", "#"])
async def test_http_rejects_raw_empty_query_or_fragment(tmp_path: Path, suffix: str) -> None:
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=_executable(tmp_path),
        process_runner=_runner([_status()]),
    )
    await adapter.snapshot()

    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234/{suffix}")

    assert captured.value.code is TailscaleErrorCode.ENDPOINT_NOT_ALLOWED
