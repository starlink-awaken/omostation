"""Fail-closed identity and endpoint contracts for the Tailscale adapter."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import omlxc.adapters.lmstudio as lmstudio_module
from omlxc.adapters.process import ProcessOutput
from omlxc.adapters.tailscale import (
    TAILSCALE_STATUS_OUTPUT_LIMIT,
    TailscaleAdapter,
    TailscaleErrorCode,
    TailscaleFailure,
    TailscaleNodePolicy,
)

_SELF_KEY = "nodekey:FAKESELF000000000000000000000000"
_PEER_KEY = "nodekey:FAKEPEER000000000000000000000001"
_OTHER_KEY = "nodekey:FAKEPEER000000000000000000000002"
_PEER_ID = "peeridFAKE000000000000000000000001"
_OTHER_ID = "peeridFAKE000000000000000000000002"
_DNS = "compute-a.example.test"
_IPV4 = "100.64.0.10"
_IPV6 = "fd7a:115c:a1e0::10"
_TRUSTED_EXECUTABLE: Path | None = None


@pytest.fixture(autouse=True)
def _trusted_executable(tmp_path: Path) -> None:
    global _TRUSTED_EXECUTABLE
    executable = tmp_path / "tailscale-fake"
    executable.write_text("unit fixture; never executed\n", encoding="utf-8")
    executable.chmod(0o700)
    _TRUSTED_EXECUTABLE = executable


def _adapter(**kwargs: Any) -> TailscaleAdapter:
    assert _TRUSTED_EXECUTABLE is not None
    return TailscaleAdapter(tailscale_executable=_TRUSTED_EXECUTABLE, **kwargs)


def _policy(**changes: object) -> TailscaleNodePolicy:
    values: dict[str, object] = {
        "node_id": "node-a",
        "expected_peer_id": _PEER_ID,
        "expected_public_key": _PEER_KEY,
        "magic_dns_name": _DNS,
        "allowed_ips": frozenset({_IPV4, _IPV6}),
        "allowed_http_ports": frozenset({1234, 11434}),
        "allowed_ssh_users": frozenset({"operator"}),
    }
    values.update(changes)
    return TailscaleNodePolicy(**values)


def _row(
    *,
    peer_id: object = _PEER_ID,
    public_key: object = _PEER_KEY,
    host_name: object = "compute-a",
    dns_name: object = f"{_DNS}.",
    ips: object = None,
    online: object = True,
    os_name: object = "linux",
) -> dict[str, object]:
    return {
        "ID": peer_id,
        "PublicKey": public_key,
        "HostName": host_name,
        "DNSName": dns_name,
        "TailscaleIPs": [_IPV4, _IPV6] if ips is None else ips,
        "Online": online,
        "OS": os_name,
    }


def _document(*, peer: object | None = None, peer_key: str = _PEER_KEY) -> dict[str, object]:
    return {
        "Self": _row(
            peer_id="peeridFAKESELF000000000000000000000",
            public_key=_SELF_KEY,
            host_name="controller",
            dns_name="controller.example.test.",
            ips=["100.64.0.1"],
            online=True,
            os_name="macOS",
        ),
        "Peer": {peer_key: _row() if peer is None else peer},
    }


def _runner_for(
    document: object,
    *,
    calls: list[tuple[tuple[str, ...], float]] | None = None,
) -> Callable[[tuple[str, ...], float], object]:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        if calls is not None:
            calls.append((argv, timeout))
        return ProcessOutput(0, json.dumps(document), "")

    return runner


@pytest.mark.asyncio
async def test_snapshot_uses_fixed_argv_and_returns_only_allowlisted_nodes() -> None:
    calls: list[tuple[tuple[str, ...], float]] = []
    document = _document()
    peers = document["Peer"]
    assert isinstance(peers, dict)
    peers[_OTHER_KEY] = _row(
        peer_id=_OTHER_ID,
        public_key=_OTHER_KEY,
        host_name="ignored",
        dns_name="ignored.example.test.",
        ips=["100.64.0.20"],
    )
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(document, calls=calls))

    snapshot = await adapter.snapshot()

    assert _TRUSTED_EXECUTABLE is not None
    assert calls == [((str(_TRUSTED_EXECUTABLE.resolve()), "status", "--json"), 10.0)]
    assert tuple(node.node_id for node in snapshot.nodes) == ("node-a",)
    assert snapshot.nodes[0].online is True


@pytest.mark.asyncio
async def test_valid_offline_peer_is_visible_but_authorization_is_typed_offline() -> None:
    adapter = _adapter(
        policies=(_policy(),),
        process_runner=_runner_for(_document(peer=_row(online=False))),
    )

    snapshot = await adapter.snapshot()

    assert snapshot.nodes[0].online is False
    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert captured.value.code is TailscaleErrorCode.OFFLINE


@pytest.mark.asyncio
async def test_offline_allowlisted_peer_does_not_block_another_online_peer() -> None:
    policy_b = _policy(
        node_id="node-b",
        expected_peer_id=_OTHER_ID,
        expected_public_key=_OTHER_KEY,
        magic_dns_name="compute-b.example.test",
        allowed_ips=frozenset({"100.64.0.20"}),
    )
    document = _document(peer=_row(online=False))
    peers = document["Peer"]
    assert isinstance(peers, dict)
    peers[_OTHER_KEY] = _row(
        peer_id=_OTHER_ID,
        public_key=_OTHER_KEY,
        host_name="compute-b",
        dns_name="compute-b.example.test.",
        ips=["100.64.0.20"],
    )
    adapter = _adapter(policies=(_policy(), policy_b), process_runner=_runner_for(document))

    await adapter.snapshot()
    online = adapter.authorize_http("node-b", "http://compute-b.example.test:1234")

    assert online.url == "http://compute-b.example.test:1234/"
    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_ssh("node-a", f"operator@{_DNS}")
    assert captured.value.code is TailscaleErrorCode.OFFLINE


def test_sensitive_identity_fields_are_excluded_from_repr_and_model_dump() -> None:
    policy = _policy()
    rendered = repr(policy)
    dumped = policy.model_dump()

    for secret in (_PEER_ID, _PEER_KEY, _DNS, _IPV4, _IPV6):
        assert secret not in rendered
        assert secret not in repr(dumped)
    assert dumped == {
        "node_id": "node-a",
        "allowed_http_ports": frozenset({1234, 11434}),
        "allowed_ssh_users": frozenset({"operator"}),
    }


def test_invalid_sensitive_policy_input_is_hidden_from_validation_rendering() -> None:
    secret = "nodekey:private status material that should hide"

    with pytest.raises(ValidationError) as captured:
        _policy(expected_public_key=secret)

    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"expected_peer_id": "short"}, "peer ID"),
        ({"expected_public_key": "nodekey:name-only"}, "public key"),
        ({"magic_dns_name": "localhost"}, "MagicDNS"),
        ({"allowed_ips": frozenset({"192.0.2.10"})}, "Tailscale"),
        ({"allowed_http_ports": frozenset()}, "at least 1 item"),
        ({"allowed_ssh_users": frozenset({"-oProxyCommand=id"})}, "SSH user"),
    ],
)
def test_policy_requires_strong_identity_and_safe_endpoint_constraints(
    changes: dict[str, object], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        _policy(**changes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document",
    [
        [],
        {"Self": _document()["Self"], "Peer": []},
        _document(peer={"ID": _PEER_ID}),
        _document(peer=_row(online=1)),
        _document(peer=_row(ips=["192.0.2.10"])),
        _document(peer_key=_OTHER_KEY),
    ],
)
async def test_malformed_or_map_key_mismatched_status_fails_closed(document: object) -> None:
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(document))

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.INVALID_SNAPSHOT
    assert _PEER_ID not in str(captured.value)
    assert _PEER_KEY not in repr(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("ID", 1),
        ("PublicKey", []),
        ("HostName", None),
        ("DNSName", 1),
        ("TailscaleIPs", "100.64.0.10"),
        ("Online", "true"),
        ("OS", False),
    ],
)
async def test_every_required_peer_field_is_strictly_typed(field: str, invalid: object) -> None:
    peer = _row()
    peer[field] = invalid
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document(peer=peer)))

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.INVALID_SNAPSHOT


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate_field", ["ID", "PublicKey", "DNSName", "TailscaleIPs"])
async def test_duplicate_identity_across_any_peer_fails_the_whole_snapshot(
    duplicate_field: str,
) -> None:
    document = _document()
    peers = document["Peer"]
    assert isinstance(peers, dict)
    second = _row(
        peer_id=_OTHER_ID,
        public_key=_OTHER_KEY,
        host_name="other",
        dns_name="other.example.test.",
        ips=["100.64.0.20"],
    )
    if duplicate_field == "PublicKey":
        second[duplicate_field] = _SELF_KEY
        map_key = _SELF_KEY
    elif duplicate_field == "TailscaleIPs":
        second[duplicate_field] = [_IPV4]
        map_key = _OTHER_KEY
    else:
        first = _row()[duplicate_field]
        second[duplicate_field] = first
        map_key = _OTHER_KEY
    peers[map_key] = second
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(document))

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.IDENTITY_CONFLICT


@pytest.mark.asyncio
async def test_self_cannot_impersonate_a_peer() -> None:
    document = _document()
    document["Self"] = _row()
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(document))

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.IDENTITY_CONFLICT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "peer",
    [
        _row(dns_name="drift.example.test."),
        _row(ips=[_IPV4, "100.64.0.99"]),
        _row(peer_id=_OTHER_ID),
        _row(public_key=_OTHER_KEY),
    ],
)
async def test_partial_policy_identity_match_is_typed_identity_drift(peer: object) -> None:
    key = (
        _OTHER_KEY if isinstance(peer, dict) and peer.get("PublicKey") == _OTHER_KEY else _PEER_KEY
    )
    adapter = _adapter(
        policies=(_policy(),), process_runner=_runner_for(_document(peer=peer, peer_key=key))
    )

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.IDENTITY_DRIFT


@pytest.mark.asyncio
async def test_peer_and_policy_multiplicity_fail_closed_without_first_match() -> None:
    duplicate_policy = _policy(node_id="node-b")
    adapter = _adapter(
        policies=(_policy(), duplicate_policy), process_runner=_runner_for(_document())
    )

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.IDENTITY_CONFLICT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (OSError("status-secret"), TailscaleErrorCode.SPAWN),
        (TimeoutError("status-secret"), TailscaleErrorCode.TIMEOUT),
        (lmstudio_module.ProcessOutputLimitError("status-secret"), TailscaleErrorCode.OUTPUT_LIMIT),
        (RuntimeError("status-secret"), TailscaleErrorCode.PROCESS),
    ],
)
async def test_process_failures_are_typed_without_echoing_status(
    failure: Exception, code: TailscaleErrorCode
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise failure

    adapter = _adapter(policies=(_policy(),), process_runner=runner)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is code
    assert "status-secret" not in str(captured.value)
    assert "status-secret" not in repr(captured.value)


@pytest.mark.asyncio
async def test_nonzero_and_invalid_json_are_distinct_and_redacted() -> None:
    async def nonzero(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(1, _PEER_ID, _PEER_KEY)

    async def invalid_json(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, f"not-json {_PEER_ID}", "")

    for runner, code in (
        (nonzero, TailscaleErrorCode.STATUS_FAILED),
        (invalid_json, TailscaleErrorCode.INVALID_JSON),
    ):
        adapter = _adapter(policies=(_policy(),), process_runner=runner)
        with pytest.raises(TailscaleFailure) as captured:
            await adapter.snapshot()
        assert captured.value.code is code
        assert _PEER_ID not in repr(captured.value)
        assert _PEER_KEY not in str(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate_location", ["root", "peer-row"])
async def test_duplicate_json_object_keys_fail_before_dict_overwrite(
    duplicate_location: str,
) -> None:
    self_json = json.dumps(_document()["Self"])
    peer_json = json.dumps(_row())
    if duplicate_location == "root":
        raw_status = f'{{"Self":{self_json},"Peer":{{}},"Peer":{{"{_PEER_KEY}":{peer_json}}}}}'
    else:
        duplicate_row = peer_json[:-1] + f',"ID":"{_OTHER_ID}"}}'
        raw_status = f'{{"Self":{self_json},"Peer":{{"{_PEER_KEY}":{duplicate_row}}}}}'

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, raw_status, "")

    adapter = _adapter(policies=(_policy(),), process_runner=runner)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.INVALID_SNAPSHOT


@pytest.mark.asyncio
async def test_nonstandard_json_constants_are_rejected_even_in_unused_fields() -> None:
    raw_status = json.dumps(_document())[:-1] + ',"unused":NaN}'

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, raw_status, "")

    adapter = _adapter(policies=(_policy(),), process_runner=runner)

    with pytest.raises(TailscaleFailure) as captured:
        await adapter.snapshot()

    assert captured.value.code is TailscaleErrorCode.INVALID_JSON


@pytest.mark.asyncio
async def test_snapshot_cancellation_is_not_converted_to_a_typed_process_error() -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise asyncio.CancelledError

    adapter = _adapter(policies=(_policy(),), process_runner=runner)

    with pytest.raises(asyncio.CancelledError):
        await adapter.snapshot()


@pytest.mark.asyncio
async def test_authorize_http_accepts_exact_live_dns_or_ip_and_returns_canonical_url() -> None:
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document()))
    await adapter.snapshot()

    dns = adapter.authorize_http("node-a", "HTTP://COMPUTE-A.EXAMPLE.TEST.:1234/")
    ipv6 = adapter.authorize_http("node-a", f"https://[{_IPV6}]:11434")

    assert dns.url == f"http://{_DNS}:1234/"
    assert ipv6.url == f"https://[{_IPV6}]:11434/"
    assert _DNS not in repr(dns)
    assert _IPV6 not in repr(ipv6.model_dump())


@pytest.mark.asyncio
async def test_unallowlisted_peer_cannot_be_used_as_an_endpoint() -> None:
    adapter = _adapter(policies=(), process_runner=_runner_for(_document()))
    snapshot = await adapter.snapshot()

    assert snapshot.nodes == ()
    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")
    assert captured.value.code is TailscaleErrorCode.UNKNOWN_NODE


def test_authorization_requires_an_adapter_owned_validated_snapshot() -> None:
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document()))

    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_http("node-a", f"http://{_DNS}:1234")

    assert captured.value.code is TailscaleErrorCode.UNKNOWN_NODE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        f"ssh://{_DNS}:1234",
        f"http://user:password@{_DNS}:1234",
        f"http://{_DNS}:1234/v1",
        f"http://{_DNS}:1234/?query=1",
        f"http://{_DNS}:1234/#fragment",
        f"http://{_DNS}..:1234",
        "http://localhost:1234",
        "http://127.0.0.1:1234",
        "http://unlisted.example.test:1234",
        "http://192.0.2.10:1234",
        f"http://{_DNS}:9999",
        f"http://{_IPV4}:1234",
    ],
)
async def test_authorize_http_rejects_every_bypass_before_network(url: str) -> None:
    peer = _row(ips=[_IPV6]) if url == f"http://{_IPV4}:1234" else _row()
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document(peer=peer)))
    await adapter.snapshot()

    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_http("node-a", url)

    assert captured.value.code is TailscaleErrorCode.ENDPOINT_NOT_ALLOWED


@pytest.mark.asyncio
async def test_authorize_ssh_requires_explicit_allowed_user_and_exact_live_host() -> None:
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document()))
    await adapter.snapshot()

    dns = adapter.authorize_ssh("node-a", f"operator@{_DNS}.")
    ipv6 = adapter.authorize_ssh("node-a", f"operator@[{_IPV6}]")

    assert dns.target == f"operator@{_DNS}"
    assert ipv6.target == f"operator@[{_IPV6}]"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        _DNS,
        f"root@{_DNS}",
        f"-oProxyCommand=id@{_DNS}",
        f"operator@{_DNS}:22",
        f"operator@[{_DNS}]",
        f"operator@{_IPV6}",
        f"operator@{_DNS};id",
        f"operator@{_DNS} remote-command",
        f"operator@{_DNS}\n-oProxyCommand=id",
        "operator@localhost",
    ],
)
async def test_authorize_ssh_rejects_options_ports_and_command_injection(target: str) -> None:
    adapter = _adapter(policies=(_policy(),), process_runner=_runner_for(_document()))
    await adapter.snapshot()

    with pytest.raises(TailscaleFailure) as captured:
        adapter.authorize_ssh("node-a", target)

    assert captured.value.code is TailscaleErrorCode.ENDPOINT_NOT_ALLOWED


def test_lmstudio_uses_the_shared_backend_neutral_process_primitive() -> None:
    from omlxc.adapters import process

    assert lmstudio_module.ProcessOutput is process.ProcessOutput
    assert lmstudio_module.ProcessOutputLimitError is process.ProcessOutputLimitError
    assert lmstudio_module._default_process_runner is process.default_process_runner
    assert TAILSCALE_STATUS_OUTPUT_LIMIT == 4 * 1024 * 1024
