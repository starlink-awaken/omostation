"""Integration of LM Studio HTTP inventory with injected SSH control state."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from omlxc.adapters.lmstudio import LmStudioAdapter, ProcessOutput
from omlxc.domain.protocols import ModelRuntimeState


@pytest.mark.asyncio
async def test_http_inventory_merges_with_control_only_loaded_instance(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("node.invalid ssh-ed25519 AAAATEST\n", encoding="utf-8")
    known_hosts.chmod(0o600)

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(
            0,
            '[{"modelKey":"model-b","identifier":"resident-b","contextLength":8192}]',
            "",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "model-a"}]})

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=known_hosts,
        process_runner=runner,
        transport=httpx.MockTransport(handler),
    )

    models = await adapter.list_models()

    assert [(model.id, model.state, model.loaded) for model in models] == [
        ("model-a", ModelRuntimeState.AVAILABLE, False),
        ("model-b", ModelRuntimeState.LOADED, True),
    ]
    assert models[1].context_limit == 8192


@pytest.mark.asyncio
async def test_http_model_id_matches_control_identifier_without_duplicate(tmp_path: Path) -> None:
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("node.invalid ssh-ed25519 AAAATEST\n", encoding="utf-8")
    known_hosts.chmod(0o600)

    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        return ProcessOutput(
            0,
            '[{"modelKey":"catalog-key","identifier":"served-id"}]',
            "",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "served-id"}]})

    adapter = LmStudioAdapter(
        backend_id="lm",
        base_url="http://node.invalid:1234",
        ssh_target="node.invalid",
        known_hosts_file=known_hosts,
        process_runner=runner,
        transport=httpx.MockTransport(handler),
    )

    models = await adapter.list_models()

    assert [(model.id, model.loaded) for model in models] == [("served-id", True)]
