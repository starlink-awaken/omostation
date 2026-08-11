from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest

from omlxc.adapters import TailscaleAdapter
from omlxc.config import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    StorageConfig,
    TailscaleNodePolicyConfig,
)
from omlxc.daemon import DaemonServer, build_production_daemon
from omlxc.domain import BackendKind
from omlxc.domain.protocols import (
    AdapterCapability,
    AdapterError,
    AdapterErrorCode,
    BackendAdapter,
    CapabilitySnapshot,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    LifecycleResult,
    ModelRuntime,
    ModelRuntimeState,
    OperationStatus,
    StreamEvent,
)


@pytest.fixture
def short_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix6-", dir="/private/tmp") as directory:
        yield Path(directory)


class ColdBackend:
    def __init__(
        self,
        *,
        state: ModelRuntimeState = ModelRuntimeState.AVAILABLE,
        complete_load: bool = True,
        block_load: bool = False,
        load_status: OperationStatus = OperationStatus.SUCCEEDED,
        stale_probe: bool = False,
        reachable: bool = True,
    ) -> None:
        self.state = state
        self.complete_load = complete_load
        self.block_load = block_load
        self.load_status = load_status
        self.stale_probe = stale_probe
        self.reachable = reachable
        self.load_calls = 0
        self.unload_calls = 0
        self.chat_calls = 0
        self.events: list[str] = []
        self.load_started = asyncio.Event()
        self.load_release = asyncio.Event()

    async def discover(self) -> CapabilitySnapshot:
        self.events.append("discover")
        loaded = self.state is ModelRuntimeState.LOADED
        return CapabilitySnapshot(
            backend_id="backend",
            reachable=self.reachable,
            compatible=True,
            model_available=self.state is not ModelRuntimeState.UNKNOWN,
            generation_ready=loaded and self.reachable,
            observed_at=(
                datetime(2020, 1, 1, tzinfo=UTC)
                if self.stale_probe
                else datetime.now(UTC)
            ),
            capabilities=frozenset(
                {
                    AdapterCapability.CHAT,
                    AdapterCapability.STREAMING,
                    AdapterCapability.MODEL_LIFECYCLE,
                }
            ),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        self.events.append("list")
        return (
            ModelRuntime(
                id="physical/model",
                state=self.state,
                loaded={
                    ModelRuntimeState.AVAILABLE: False,
                    ModelRuntimeState.LOADED: True,
                    ModelRuntimeState.UNKNOWN: None,
                }[self.state],
                capabilities=frozenset({AdapterCapability.CHAT}),
                context_limit=8192,
            ),
        )

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.events.append("load")
        self.load_calls += 1
        self.load_started.set()
        if self.block_load:
            await self.load_release.wait()
        if self.complete_load:
            self.state = ModelRuntimeState.LOADED
        return LifecycleResult(
            model_id=model_id,
            status=self.load_status,
            changed=self.load_status is OperationStatus.SUCCEEDED,
            idempotency_key=idempotency_key,
            error=(
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="lifecycle unsupported",
                )
                if self.load_status is OperationStatus.UNSUPPORTED
                else None
            ),
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.events.append("unload")
        self.unload_calls += 1
        self.state = ModelRuntimeState.AVAILABLE
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        self.events.append("chat")
        self.chat_calls += 1
        return ChatResult(request_id=request.request_id, success=True, content="cold-loaded")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        raise AssertionError(f"unexpected embedding request: {request.request_id}")

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise AssertionError(f"unexpected stream request: {request.request_id}")

    async def aclose(self) -> None:
        return None


class DenyingTailscale:
    async def snapshot(self) -> object:
        return object()

    def authorize_http(self, node_id: str, base_url: str) -> object:
        del node_id, base_url
        raise PermissionError("denied")


def _config(
    root: Path,
    *,
    placement_memory_gb: float | None = 2.0,
    node_memory_gb: float | None = 16.0,
    remote: bool = False,
) -> AppConfig:
    node = NodeConfig(
        id="node",
        display_name="Node",
        platform="macos",
        memory_gb=node_memory_gb,
        tailscale=(
            TailscaleNodePolicyConfig(
                peer_id="peer_identifier_123456",
                public_key="nodekey:abcdefghijklmnopqrstuvwxyz1234",
                magic_dns_name="node.example.ts.net",
                allowed_ips=("100.64.0.10",),
                allowed_http_ports=(8000,),
                allowed_ssh_users=("operator",),
            )
            if remote
            else None
        ),
    )
    return AppConfig(
        daemon=DaemonConfig(socket_path=root / "daemon.sock", probe_interval_seconds=60),
        storage=StorageConfig(database_path=root / "state.db"),
        nodes=(node,),
        backends=(
            BackendConfig(
                id="backend",
                node_id="node",
                kind=BackendKind.OMLX_APP,
                base_url="http://100.64.0.10:8000" if remote else "http://127.0.0.1:8000",
            ),
        ),
        models=(ModelConfig(id="local/model", category="llm", role="chat", engine="omlx"),),
        placements=(
            PlacementConfig(
                id="placement",
                model_id="local/model",
                backend_id="backend",
                backend_model_id="physical/model",
                context_limit=8192,
                memory_gb=placement_memory_gb,
            ),
        ),
    )


async def _uds_client(socket_path: Path) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=str(socket_path)),
        base_url="http://omlxc",
    )


async def _wait_job(client: httpx.AsyncClient, job_id: str) -> httpx.Response:
    for _ in range(100):
        current = await client.get(f"/api/v1/jobs/{job_id}")
        if current.json()["data"]["state"] in {"succeeded", "failed"}:
            return current
        await asyncio.sleep(0)
    raise AssertionError("job did not reach a terminal state")


@pytest.mark.asyncio
async def test_cold_available_production_uds_plans_loads_postverifies_and_infers_once(
    short_root: Path,
) -> None:
    config = _config(short_root)
    backend = ColdBackend()
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            plan = await client.post(
                "/api/v1/routes/plan", json={"model_id": "local/model"}
            )
            chat = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            models = await client.get("/api/v1/models")
    finally:
        await server.stop()

    assert plan.status_code == 200
    assert plan.json()["data"]["selected_placement_id"] == "placement"
    assert chat.status_code == 200
    assert chat.json()["choices"][0]["message"]["content"] == "cold-loaded"
    assert backend.load_calls == backend.chat_calls == 1
    load_index = backend.events.index("load")
    assert backend.events[load_index + 1 : load_index + 3] == ["discover", "list"]
    assert backend.events[-1] == "chat"
    state = models.json()["data"]["items"][0]["placement_states"][0]
    assert state["loaded"] is True
    assert state["ready"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unknown", "memory", "authorization"])
async def test_ineligible_production_catalog_never_attempts_load(
    short_root: Path, case: str
) -> None:
    backend = ColdBackend(
        state=ModelRuntimeState.UNKNOWN if case == "unknown" else ModelRuntimeState.AVAILABLE
    )
    config = _config(
        short_root,
        placement_memory_gb=None if case == "memory" else 2.0,
        remote=case == "authorization",
    )
    composition = build_production_daemon(
        config,
        adapters={"backend": cast(BackendAdapter, backend)},
        tailscale=(
            cast(TailscaleAdapter, DenyingTailscale()) if case == "authorization" else None
        ),
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            plan = await client.post(
                "/api/v1/routes/plan", json={"model_id": "local/model"}
            )
            chat = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        await server.stop()

    assert plan.status_code == chat.status_code == 409
    assert backend.load_calls == backend.chat_calls == 0
    expected = {
        "unknown": "unavailable",
        "memory": "memory_denied",
        "authorization": "authorization_denied",
    }[case]
    assert plan.json()["error"]["partial_result"]["rejected"] == {"placement": expected}


@pytest.mark.asyncio
async def test_successful_lifecycle_without_fresh_loaded_postverify_is_not_optimistic(
    short_root: Path,
) -> None:
    config = _config(short_root)
    backend = ColdBackend(complete_load=False)
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            chat = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            models = await client.get("/api/v1/models")
    finally:
        await server.stop()

    assert chat.status_code == 409
    assert backend.load_calls == 1
    assert backend.chat_calls == 0
    state = models.json()["data"]["items"][0]["placement_states"][0]
    assert state["loaded"] is False


@pytest.mark.asyncio
async def test_unsupported_lifecycle_never_infers_even_if_postprobe_claims_loaded(
    short_root: Path,
) -> None:
    config = _config(short_root)
    backend = ColdBackend(load_status=OperationStatus.UNSUPPORTED)
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            chat = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        await server.stop()

    assert chat.status_code == 409
    assert backend.load_calls == 1
    assert backend.chat_calls == 0


@pytest.mark.asyncio
async def test_explicit_job_and_inference_share_placement_singleflight(short_root: Path) -> None:
    config = _config(short_root)
    backend = ColdBackend(block_load=True)
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            chat_task = asyncio.create_task(
                client.post(
                    "/openai/v1/chat/completions",
                    json={
                        "model": "local/model",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                )
            )
            await asyncio.wait_for(backend.load_started.wait(), 1)
            job = await client.post(
                "/api/v1/models/local%2Fmodel/load",
                headers={"Idempotency-Key": "parallel-load"},
            )
            backend.load_release.set()
            chat = await asyncio.wait_for(chat_task, 2)
            job_id = job.json()["data"]["id"]
            current = await _wait_job(client, job_id)
    finally:
        backend.load_release.set()
        await server.stop()

    assert chat.status_code == 200
    assert current.json()["data"]["state"] == "succeeded"
    assert backend.load_calls == 1


@pytest.mark.asyncio
async def test_loaded_memory_denied_job_still_physically_unloads_and_postverifies(
    short_root: Path,
) -> None:
    config = _config(short_root, node_memory_gb=1)
    backend = ColdBackend(state=ModelRuntimeState.LOADED)
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            job = await client.post(
                "/api/v1/models/local%2Fmodel/unload",
                headers={"Idempotency-Key": "memory-pressure-unload"},
            )
            current = await _wait_job(client, job.json()["data"]["id"])
    finally:
        await server.stop()

    assert current.json()["data"]["state"] == "succeeded"
    assert backend.unload_calls == 1
    assert backend.state is ModelRuntimeState.AVAILABLE
    load_index = backend.events.index("unload")
    assert backend.events[load_index + 1 : load_index + 3] == ["discover", "list"]


@pytest.mark.asyncio
async def test_loaded_unavailable_backend_never_receives_unload_write(short_root: Path) -> None:
    config = _config(short_root)
    backend = ColdBackend(state=ModelRuntimeState.LOADED, reachable=False)
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            job = await client.post(
                "/api/v1/models/local%2Fmodel/unload",
                headers={"Idempotency-Key": "unavailable-unload"},
            )
            current = await _wait_job(client, job.json()["data"]["id"])
    finally:
        await server.stop()

    assert current.json()["data"]["state"] == "failed"
    assert backend.unload_calls == 0
    assert backend.state is ModelRuntimeState.LOADED


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["stale", "authorization"])
async def test_unload_probe_failure_never_becomes_false_noop_success(
    short_root: Path, case: str
) -> None:
    config = _config(short_root, remote=case == "authorization")
    backend = ColdBackend(state=ModelRuntimeState.LOADED, stale_probe=case == "stale")
    composition = build_production_daemon(
        config,
        adapters={"backend": cast(BackendAdapter, backend)},
        tailscale=(
            cast(TailscaleAdapter, DenyingTailscale()) if case == "authorization" else None
        ),
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            job = await client.post(
                "/api/v1/models/local%2Fmodel/unload",
                headers={"Idempotency-Key": f"{case}-unload"},
            )
            current = await _wait_job(client, job.json()["data"]["id"])
    finally:
        await server.stop()

    assert current.json()["data"]["state"] == "failed"
    assert backend.unload_calls == 0


@pytest.mark.asyncio
async def test_load_memory_denied_never_calls_adapter_and_job_fails(short_root: Path) -> None:
    config = _config(short_root, node_memory_gb=1)
    backend = ColdBackend()
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _uds_client(config.daemon.socket_path) as client:
            job = await client.post(
                "/api/v1/models/local%2Fmodel/load",
                headers={"Idempotency-Key": "memory-denied-load"},
            )
            current = await _wait_job(client, job.json()["data"]["id"])
    finally:
        await server.stop()

    assert current.json()["data"]["state"] == "failed"
    assert backend.load_calls == 0
