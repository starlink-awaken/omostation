"""Fix2 regressions for path-chain trust and authorization freshness state."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from omlxc.adapters.process import ProcessOutput
from omlxc.adapters.tailscale import (
    TailscaleAdapter,
    TailscaleErrorCode,
    TailscaleFailure,
    TailscaleNodePolicy,
)

_KEY = "nodekey:FAKEPEER000000000000000000000001"
_DNS = "compute-a.example.test"


def _executable(directory: Path) -> Path:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    executable = directory / "tailscale-fake"
    executable.write_text("fix2 fixture; never executed\n", encoding="utf-8")
    executable.chmod(0o700)
    return executable


def _policy() -> TailscaleNodePolicy:
    return TailscaleNodePolicy(
        node_id="node-a",
        expected_peer_id="peeridFAKE000000000000000000000001",
        expected_public_key=_KEY,
        magic_dns_name=_DNS,
        allowed_ips=frozenset({"100.64.0.10"}),
        allowed_http_ports=frozenset({1234}),
        allowed_ssh_users=frozenset({"operator"}),
    )


def _status() -> dict[str, object]:
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
            _KEY: {
                "ID": "peeridFAKE000000000000000000000001",
                "PublicKey": _KEY,
                "HostName": "compute-a",
                "DNSName": f"{_DNS}.",
                "TailscaleIPs": ["100.64.0.10"],
                "Online": True,
                "OS": "linux",
            }
        },
    }


def _runner(responses: list[object], calls: list[tuple[str, ...]] | None = None) -> Any:
    items = iter(responses)

    async def run(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        if calls is not None:
            calls.append(argv)
        item = next(items)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return ProcessOutput(0, item, "")
        return ProcessOutput(0, json.dumps(item), "")

    return run


def _metadata_with(
    metadata: os.stat_result,
    *,
    mode: int | None = None,
    uid: int | None = None,
    inode: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        st_mode=metadata.st_mode if mode is None else mode,
        st_uid=metadata.st_uid if uid is None else uid,
        st_dev=metadata.st_dev,
        st_ino=metadata.st_ino if inode is None else inode,
    )


@pytest.mark.parametrize("mode", [0o770, 0o707])
def test_constructor_rejects_group_or_world_writable_ancestor(tmp_path: Path, mode: int) -> None:
    parent = tmp_path / "trusted-bin"
    executable = _executable(parent)
    parent.chmod(mode)

    with pytest.raises(ValueError, match="trusted Tailscale executable"):
        TailscaleAdapter(
            policies=(_policy(),),
            tailscale_executable=executable,
            process_runner=_runner([_status()]),
        )


@pytest.mark.parametrize("drift", ["wrong-owner", "non-directory", "symlink"])
def test_constructor_rejects_untrusted_ancestor_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    parent = tmp_path / "trusted-bin"
    executable = _executable(parent)
    real_lstat = Path.lstat

    def fake_lstat(candidate: Path) -> os.stat_result | SimpleNamespace:
        metadata = real_lstat(candidate)
        if candidate != parent:
            return metadata
        if drift == "wrong-owner":
            untrusted_uid = os.geteuid() + 1
            if untrusted_uid == 0:
                untrusted_uid += 1
            return _metadata_with(metadata, uid=untrusted_uid)
        if drift == "non-directory":
            return _metadata_with(metadata, mode=stat.S_IFREG | 0o700)
        return _metadata_with(metadata, mode=stat.S_IFLNK | 0o700)

    monkeypatch.setattr(Path, "lstat", fake_lstat)

    with pytest.raises(ValueError, match="trusted Tailscale executable"):
        TailscaleAdapter(
            policies=(_policy(),),
            tailscale_executable=executable,
            process_runner=_runner([_status()]),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["executable", "ancestor"])
async def test_constructor_fingerprint_rejects_path_replacement_before_refresh(
    tmp_path: Path, target: str
) -> None:
    parent = tmp_path / "trusted-bin"
    executable = _executable(parent)
    calls: list[tuple[str, ...]] = []
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()], calls),
    )
    if target == "executable":
        replacement = parent / "replacement"
        replacement.write_text("different inode\n", encoding="utf-8")
        replacement.chmod(0o700)
        replacement.replace(executable)
    else:
        old_parent = tmp_path / "old-bin"
        parent.rename(old_parent)
        _executable(parent)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.SPAWN
    assert calls == []


@pytest.mark.asyncio
async def test_second_pre_spawn_fingerprint_check_rejects_post_validation_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "trusted-bin"
    executable = _executable(parent)
    calls: list[tuple[str, ...]] = []
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=executable,
        process_runner=_runner([_status()], calls),
    )
    real_lstat = Path.lstat
    executable_reads = 0

    def drifting_lstat(candidate: Path) -> os.stat_result | SimpleNamespace:
        nonlocal executable_reads
        metadata = real_lstat(candidate)
        if candidate == executable:
            executable_reads += 1
            if executable_reads >= 2:
                return _metadata_with(metadata, inode=metadata.st_ino + 1)
        return metadata

    monkeypatch.setattr(Path, "lstat", drifting_lstat)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.SPAWN
    assert executable_reads >= 2
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [OSError("fake spawn"), "not-json"])
async def test_first_refresh_failure_marks_authorization_stale(
    tmp_path: Path, failure: object
) -> None:
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=_executable(tmp_path / "trusted-bin"),
        process_runner=_runner([failure]),
    )

    with pytest.raises(TailscaleFailure):
        await adapter.snapshot()
    for authorize in (
        lambda: adapter.authorize_http("node-a", f"http://{_DNS}:1234"),
        lambda: adapter.authorize_ssh("node-a", f"operator@{_DNS}"),
    ):
        with pytest.raises(TailscaleFailure) as captured:
            authorize()
        assert captured.value.code is TailscaleErrorCode.STALE


@pytest.mark.asyncio
async def test_failed_refresh_never_reuses_old_snapshot_and_success_recovers_freshness(
    tmp_path: Path,
) -> None:
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=_executable(tmp_path / "trusted-bin"),
        process_runner=_runner([_status(), "not-json", _status()]),
    )
    await adapter.snapshot()
    assert adapter.authorize_http("node-a", f"http://{_DNS}:1234").port == 1234

    with pytest.raises(TailscaleFailure):
        await adapter.snapshot()
    with pytest.raises(TailscaleFailure) as stale:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert stale.value.code is TailscaleErrorCode.STALE

    await adapter.snapshot()
    assert adapter.authorize_ssh("node-a", f"operator@{_DNS}").node_id == "node-a"


@pytest.mark.asyncio
async def test_expiry_or_clock_rollback_latches_stale_until_successful_refresh(
    tmp_path: Path,
) -> None:
    monotonic = [100.0]
    adapter = TailscaleAdapter(
        policies=(_policy(),),
        tailscale_executable=_executable(tmp_path / "trusted-bin"),
        process_runner=_runner([_status(), _status()]),
        snapshot_ttl_seconds=5,
        monotonic_clock=lambda: monotonic[0],
    )
    await adapter.snapshot()
    monotonic[0] = 99.0
    with pytest.raises(TailscaleFailure) as rollback:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert rollback.value.code is TailscaleErrorCode.STALE

    monotonic[0] = 101.0
    with pytest.raises(TailscaleFailure) as latched:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert latched.value.code is TailscaleErrorCode.STALE

    await adapter.snapshot()
    monotonic[0] = 106.0001
    with pytest.raises(TailscaleFailure) as expired:
        adapter.authorize_ssh("node-a", f"operator@{_DNS}")
    assert expired.value.code is TailscaleErrorCode.STALE
