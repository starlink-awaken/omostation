from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from omlxc.config import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    StorageConfig,
    config_identity,
)
from omlxc.daemon import DaemonServer, build_production_daemon
from omlxc.domain import BackendKind
from omlxc.domain.protocols import (
    AdapterCapability,
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
from omlxc.scheduler import PlacementSnapshot


class FakeBackend:
    def __init__(self) -> None:
        self.operations: list[tuple[str, str, str | None]] = []
        self.block = False
        self.started = asyncio.Event()
        self.loaded = True

    async def _maybe_block(self) -> None:
        self.started.set()
        if self.block:
            await asyncio.Event().wait()

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.operations.append(("load", model_id, idempotency_key))
        await self._maybe_block()
        self.loaded = True
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.operations.append(("unload", model_id, idempotency_key))
        await self._maybe_block()
        self.loaded = False
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(request_id=request.request_id, success=True, content="ok")

    async def discover(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            backend_id="backend",
            reachable=True,
            compatible=True,
            model_available=True,
            generation_ready=self.loaded,
            observed_at=datetime.now(UTC),
            capabilities=frozenset(
                {AdapterCapability.CHAT, AdapterCapability.EMBEDDING, AdapterCapability.STREAMING}
            ),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        return (
            ModelRuntime(
                id="physical/model",
                state=ModelRuntimeState.LOADED if self.loaded else ModelRuntimeState.AVAILABLE,
                loaded=self.loaded,
                capabilities=frozenset({AdapterCapability.CHAT, AdapterCapability.EMBEDDING}),
                context_limit=4096,
            ),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=((1.0,),),
        )

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class DiscoveringBackend(FakeBackend):
    def __init__(self, *, backend_id: str = "healthy", fail: bool = False) -> None:
        super().__init__()
        self.backend_id = backend_id
        self.fail = fail
        self.discoveries = 0

    async def discover(self) -> CapabilitySnapshot:
        self.discoveries += 1
        if self.fail:
            raise RuntimeError("backend probe failed")
        return CapabilitySnapshot(
            backend_id=self.backend_id,
            reachable=True,
            compatible=True,
            model_available=True,
            generation_ready=True,
            observed_at=datetime.now(UTC),
            capabilities=frozenset(
                {
                    AdapterCapability.CHAT,
                    AdapterCapability.STREAMING,
                    AdapterCapability.EMBEDDING,
                }
            ),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        return (
            ModelRuntime(
                id="physical/model",
                state=ModelRuntimeState.LOADED,
                loaded=True,
                capabilities=frozenset({AdapterCapability.CHAT, AdapterCapability.EMBEDDING}),
                context_limit=4096,
            ),
        )


def _config(root: Path) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(socket_path=root / "omlxcd.sock"),
        storage=StorageConfig(database_path=root / "state.db"),
        nodes=(NodeConfig(id="node", display_name="Node", platform="macos", memory_gb=16),),
        backends=(
            BackendConfig(
                id="backend",
                node_id="node",
                kind=BackendKind.OMLX_APP,
                base_url="http://127.0.0.1:8000",
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
                memory_gb=2,
            ),
        ),
    )


def _snapshot() -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id="placement",
        model_id="local/model",
        backend_id="backend",
        backend_model_id="physical/model",
        node_id="node",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat", "streaming", "embedding"}),
        context_limit=8192,
        memory_admitted=True,
        loaded=True,
        ttft_ms=10,
        throughput_tps=10,
        queue_depth=0,
        error_rate=0,
        network_cost_ms=0,
        affinity=1,
        available_concurrency=1,
        local=True,
        security_allowed=True,
    )


def _discovery_config(root: Path) -> AppConfig:
    config = _config(root)
    return config.model_copy(
        update={
            "nodes": (
                NodeConfig(id="bad-node", display_name="Bad", platform="macos", memory_gb=16),
                NodeConfig(id="good-node", display_name="Good", platform="macos", memory_gb=16),
            ),
            "backends": (
                BackendConfig(
                    id="bad",
                    node_id="bad-node",
                    kind=BackendKind.OMLX_APP,
                    base_url="http://127.0.0.1:8001",
                ),
                BackendConfig(
                    id="healthy",
                    node_id="good-node",
                    kind=BackendKind.OMLX_APP,
                    base_url="http://127.0.0.1:8002",
                ),
            ),
            "placements": (
                PlacementConfig(
                    id="bad-placement",
                    model_id="local/model",
                    backend_id="bad",
                    backend_model_id="physical/model",
                    context_limit=8192,
                    memory_gb=2,
                ),
                PlacementConfig(
                    id="healthy-placement",
                    model_id="local/model",
                    backend_id="healthy",
                    backend_model_id="physical/model",
                    context_limit=8192,
                    memory_gb=2,
                ),
            ),
        }
    )


@pytest.mark.asyncio
async def test_production_discovery_isolates_failure_and_enables_chat_and_embed() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix2-", dir="/tmp") as directory:
        root = Path(directory)
        config = _discovery_config(root)
        bad = DiscoveringBackend(fail=True)
        healthy = DiscoveringBackend()
        composition = build_production_daemon(
            config,
            adapters={"bad": bad, "healthy": healthy},
        )
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(config.daemon.socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                chat = await client.post(
                    "/openai/v1/chat/completions",
                    json={
                        "model": "local/model",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                )
                embedding = await client.post(
                    "/openai/v1/embeddings",
                    json={"model": "local/model", "input": "hello"},
                )
        finally:
            await server.stop()

    assert bad.discoveries == healthy.discoveries == 1
    assert chat.status_code == 200
    assert chat.json()["choices"][0]["message"]["content"] == "ok"
    assert embedding.status_code == 200
    assert embedding.json()["data"][0]["embedding"] == [1.0]


@pytest.mark.asyncio
async def test_production_discovery_periodically_recovers_a_failed_backend() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix2-refresh-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root).model_copy(
            update={
                "daemon": DaemonConfig(
                    socket_path=root / "omlxcd.sock", probe_interval_seconds=0.01
                )
            }
        )
        backend = DiscoveringBackend(backend_id="backend", fail=True)
        composition = build_production_daemon(config, adapters={"backend": backend})
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(config.daemon.socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                unavailable = await client.post(
                    "/openai/v1/chat/completions",
                    json={
                        "model": "local/model",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                )
                backend.fail = False
                for _ in range(50):
                    recovered = await client.post(
                        "/openai/v1/chat/completions",
                        json={
                            "model": "local/model",
                            "messages": [{"role": "user", "content": "hello"}],
                        },
                    )
                    if recovered.status_code == 200:
                        break
                    await asyncio.sleep(0.01)
        finally:
            await server.stop()

    assert unavailable.status_code == 409
    assert backend.discoveries >= 2
    assert recovered.status_code == 200
    assert composition.runtime.task_settled


@pytest.mark.asyncio
async def test_remote_discovery_is_blocked_before_tailscale_authorization() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix2-auth-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root).model_copy(
            update={
                "nodes": (
                    NodeConfig(
                        id="node",
                        display_name="Node",
                        platform="macos",
                        tailscale_identity="node.example.ts.net",
                    ),
                ),
                "backends": (
                    BackendConfig(
                        id="backend",
                        node_id="node",
                        kind=BackendKind.OMLX_APP,
                        base_url="http://100.64.0.10:8000",
                    ),
                ),
            }
        )
        backend = DiscoveringBackend(backend_id="backend")
        composition = build_production_daemon(config, adapters={"backend": backend})
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(config.daemon.socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                response = await client.post(
                    "/openai/v1/chat/completions",
                    json={
                        "model": "local/model",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                )
        finally:
            await server.stop()

    assert backend.discoveries == 0
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_production_composition_and_jobs_survive_real_uds_restart() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix1-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root)
        backend = FakeBackend()
        ids = count(1)
        composition = build_production_daemon(
            config,
            adapters={"backend": backend},
            snapshots=(_snapshot(),),
            id_factory=lambda: f"job-{next(ids)}",
            now=lambda: datetime.now(UTC),
        )
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(config.daemon.socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                health = await client.get("/api/v1/health")
                models = await client.get("/openai/v1/models")
                first = await client.post(
                    "/api/v1/models/local%2Fmodel/load",
                    headers={"Idempotency-Key": "same-key"},
                )
                repeated = await client.post(
                    "/api/v1/models/local%2Fmodel/load",
                    headers={"Idempotency-Key": "same-key"},
                )
                conflict = await client.post(
                    "/api/v1/models/local%2Fmodel/unload",
                    headers={"Idempotency-Key": "same-key"},
                )
                for _ in range(100):
                    current = await client.get(f"/api/v1/jobs/{first.json()['data']['id']}")
                    if current.json()["data"]["state"] == "succeeded":
                        break
                    await asyncio.sleep(0)
                backend.block = True
                backend.started.clear()
                recoverable = await client.post(
                    "/api/v1/models/local%2Fmodel/unload",
                    headers={"Idempotency-Key": "recover-key"},
                )
                await asyncio.wait_for(backend.started.wait(), 1)
        finally:
            await server.stop()

        assert health.status_code == 200
        assert health.json()["data"]["status"] == "ready"
        assert health.json()["data"]["config_identity"] == config_identity(config)
        assert str(root) not in health.text
        assert models.status_code == 200
        assert first.status_code == repeated.status_code == 202
        assert first.json()["data"]["id"] == repeated.json()["data"]["id"]
        assert conflict.status_code == 409
        assert backend.operations == [("unload", "physical/model", "placement:unload:placement")]

        recovery_backend = FakeBackend()
        restarted = build_production_daemon(
            config,
            adapters={"backend": recovery_backend},
            snapshots=(_snapshot(),),
        )
        restarted_server = DaemonServer(restarted.app, socket_path=config.daemon.socket_path)
        await restarted_server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(config.daemon.socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                persisted = await client.get("/api/v1/jobs/job-1")
                await asyncio.wait_for(recovery_backend.started.wait(), 1)
                for _ in range(100):
                    recovered = await client.get(f"/api/v1/jobs/{recoverable.json()['data']['id']}")
                    if recovered.json()["data"]["state"] == "succeeded":
                        break
                    await asyncio.sleep(0)
                jobs = await client.get("/api/v1/jobs")
        finally:
            await restarted_server.stop()

        assert persisted.status_code == 200
        assert persisted.json()["data"]["state"] == "succeeded"
        assert recovered.json()["data"]["state"] == "succeeded"
        assert [item["state"] for item in jobs.json()["data"]["items"]] == [
            "succeeded",
            "succeeded",
        ]
        assert restarted.runtime.task_settled


@pytest.mark.asyncio
async def test_receive_layer_rejects_chunked_body_without_content_length() -> None:
    composition = build_production_daemon(
        _config(Path("/tmp/omlxc-unused")),
        adapters={"backend": FakeBackend()},
        snapshots=(_snapshot(),),
    )

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"model":"local/model","input":"'
        for _ in range(1025):
            yield b"x" * 1024
        pytest.fail("body limiter consumed beyond the first oversized chunk")

    transport = httpx.ASGITransport(app=composition.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post("/openai/v1/embeddings", content=chunks())

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_route_failure_and_catalog_views_are_typed_and_observable(tmp_path: Path) -> None:
    config = _config(tmp_path).model_copy(
        update={
            "nodes": (
                NodeConfig(id="node", display_name="Ready", platform="macos"),
                NodeConfig(
                    id="node-b",
                    display_name="Rejected",
                    platform="windows",
                    tailscale_identity="private-peer-identity",
                ),
            )
        }
    )
    ready = _snapshot()
    rejected = replace(
        ready,
        placement_id="placement-b",
        node_id="node-b",
        fresh=False,
        available=False,
        authorized=False,
        loaded=False,
        available_concurrency=0,
        security_allowed=False,
    )
    composition = build_production_daemon(
        config,
        adapters={"backend": FakeBackend()},
        snapshots=(ready, rejected),
        now=lambda: datetime(2026, 8, 12, tzinfo=UTC),
    )
    transport = httpx.ASGITransport(app=composition.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        failure = await client.post(
            "/api/v1/routes/plan",
            json={"model_id": "local/model", "required_capabilities": ["vision"]},
        )
        nodes = await client.get("/api/v1/nodes")
        models = await client.get("/api/v1/models")

    assert failure.status_code == 409
    error = failure.json()["error"]
    assert error["code"] == "E400"
    assert error["partial_result"] == {
        "kind": "no_candidate",
        "rejected": {
            "placement": "capability_missing",
            "placement-b": "authorization_denied",
        },
        "config_version": "scheduler-v1",
    }
    assert "http://" not in failure.text and "physical/model" not in failure.text

    node_items = nodes.json()["data"]["items"]
    assert "private-peer-identity" not in nodes.text
    assert [(item["id"], item["fresh"], item["ready"]) for item in node_items] == [
        ("node", True, True),
        ("node-b", False, False),
    ]
    assert node_items[0]["last_observed_at"] == "2026-08-12T00:00:00Z"
    model = models.json()["data"]["items"][0]
    assert model["fresh"] is True
    assert model["available"] is True
    assert model["authorized"] is True
    assert model["loaded"] is True
    assert model["ready"] is True
    assert [item["placement_id"] for item in model["placement_states"]] == [
        "placement",
        "placement-b",
    ]

    capacity_composition = build_production_daemon(
        config,
        adapters={"backend": FakeBackend()},
        snapshots=(replace(ready, available_concurrency=0),),
        now=lambda: datetime(2026, 8, 12, tzinfo=UTC),
    )
    capacity_transport = httpx.ASGITransport(app=capacity_composition.app)
    async with httpx.AsyncClient(transport=capacity_transport, base_url="http://omlxc") as client:
        capacity = await client.post("/api/v1/routes/plan", json={"model_id": "local/model"})

    assert capacity.status_code == 409
    assert capacity.json()["error"]["code"] == "E401"
    assert capacity.json()["error"]["retryable"] is True
    assert capacity.json()["error"]["partial_result"]["rejected"] == {"placement": "no_capacity"}


@pytest.mark.asyncio
async def test_unprobed_production_catalog_returns_typed_no_candidate_not_503() -> None:
    composition = build_production_daemon(
        _config(Path("/tmp/omlxc-unprobed")),
        adapters={"backend": FakeBackend()},
    )
    transport = httpx.ASGITransport(app=composition.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["type"] == "insufficient_capacity"


@pytest.mark.asyncio
async def test_server_stop_bounds_a_hanging_stream_and_settles_tasks() -> None:
    app = FastAPI()

    @app.get("/hang")
    async def hang() -> StreamingResponse:
        async def forever() -> AsyncIterator[bytes]:
            yield b"started\n"
            await asyncio.Event().wait()

        return StreamingResponse(forever())

    with tempfile.TemporaryDirectory(prefix="omlxc-stop-", dir="/tmp") as directory:
        path = Path(directory) / "daemon.sock"
        server = DaemonServer(app, socket_path=path, shutdown_timeout=1)
        await server.start()
        reader, writer = await asyncio.open_unix_connection(str(path))
        writer.write(b"GET /hang HTTP/1.1\r\nHost: omlxc\r\n\r\n")
        await writer.drain()
        assert b"200 OK" in await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1)

        await asyncio.wait_for(server.stop(), 2.5)
        writer.close()
        await writer.wait_closed()

        assert server.task_settled
        assert not path.exists()
