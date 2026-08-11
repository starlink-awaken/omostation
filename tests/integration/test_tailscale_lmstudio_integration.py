"""Tailscale admission composes with LM Studio without tunnelling inference over SSH."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from omlxc.adapters.lmstudio import LmStudioAdapter
from omlxc.adapters.process import ProcessOutput
from omlxc.adapters.tailscale import TailscaleAdapter, TailscaleFailure, TailscaleNodePolicy
from omlxc.domain.protocols import ChatMessage, ChatRequest

_KEY = "nodekey:FAKEPEER000000000000000000000001"
_DNS = "compute-a.example.test"
_TRUSTED_EXECUTABLE: Path | None = None


@pytest.fixture(autouse=True)
def _trusted_executable(tmp_path: Path) -> None:
    global _TRUSTED_EXECUTABLE
    executable = tmp_path / "tailscale-fake"
    executable.write_text("integration fixture; never executed\n", encoding="utf-8")
    executable.chmod(0o700)
    _TRUSTED_EXECUTABLE = executable


def _adapter(**kwargs: Any) -> TailscaleAdapter:
    assert _TRUSTED_EXECUTABLE is not None
    return TailscaleAdapter(tailscale_executable=_TRUSTED_EXECUTABLE, **kwargs)


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


@pytest.mark.asyncio
async def test_authorized_lmstudio_inference_uses_original_http_not_ssh() -> None:
    process_calls: list[tuple[str, ...]] = []
    http_calls: list[httpx.URL] = []

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del timeout
        process_calls.append(argv)
        return ProcessOutput(0, json.dumps(_status()), "")

    tailscale = _adapter(policies=(_policy(),), process_runner=runner)
    await tailscale.snapshot()
    endpoint = tailscale.authorize_http("node-a", f"http://{_DNS}:1234")
    control = tailscale.authorize_ssh("node-a", f"operator@{_DNS}")

    async def handler(request: httpx.Request) -> httpx.Response:
        http_calls.append(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "direct"}}]})

    adapter = LmStudioAdapter(
        backend_id="lm-a",
        base_url=endpoint.url,
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.chat(
        ChatRequest(
            request_id="req-a",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )
    )

    assert result.success is True
    assert result.content == "direct"
    assert [str(url) for url in http_calls] == [f"http://{_DNS}:1234/v1/chat/completions"]
    assert _TRUSTED_EXECUTABLE is not None
    assert process_calls == [(str(_TRUSTED_EXECUTABLE.resolve()), "status", "--json")]
    assert control.target == f"operator@{_DNS}"


@pytest.mark.asyncio
async def test_unauthorized_endpoint_is_rejected_before_lmstudio_or_http_construction() -> None:
    http_calls = 0
    constructed = False

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(0, json.dumps(_status()), "")

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        del request
        http_calls += 1
        return httpx.Response(500)

    tailscale = _adapter(policies=(_policy(),), process_runner=runner)
    await tailscale.snapshot()

    with pytest.raises(TailscaleFailure):
        endpoint = tailscale.authorize_http("node-a", "http://unlisted.example.test:1234")
        constructed = True
        LmStudioAdapter(
            backend_id="lm-a",
            base_url=endpoint.url,
            transport=httpx.MockTransport(handler),
        )

    assert constructed is False
    assert http_calls == 0
