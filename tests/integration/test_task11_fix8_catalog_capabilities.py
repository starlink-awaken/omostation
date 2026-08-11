from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest

from omlxc.config import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    StorageConfig,
)
from omlxc.daemon import DaemonServer, build_production_daemon
from omlxc.domain import BackendKind
from omlxc.domain.protocols import (
    AdapterCapability,
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
    with tempfile.TemporaryDirectory(prefix="omlxc-fix8-", dir="/private/tmp") as directory:
        yield Path(directory)


class CapabilityBackend:
    def __init__(
        self,
        backend_id: str,
        *,
        backend_capabilities: frozenset[AdapterCapability],
        model_capabilities: Mapping[str, frozenset[AdapterCapability]],
    ) -> None:
        self.backend_id = backend_id
        self.backend_capabilities = backend_capabilities
        self.model_capabilities = dict(model_capabilities)
        self.states = {model_id: ModelRuntimeState.AVAILABLE for model_id in model_capabilities}
        self.load_calls = 0
        self.chat_calls = 0

    async def discover(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            backend_id=self.backend_id,
            reachable=True,
            compatible=True,
            model_available=bool(self.states),
            generation_ready=any(
                state is ModelRuntimeState.LOADED for state in self.states.values()
            ),
            observed_at=datetime.now(UTC),
            capabilities=self.backend_capabilities,
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        return tuple(
            ModelRuntime(
                id=model_id,
                state=self.states[model_id],
                loaded=self.states[model_id] is ModelRuntimeState.LOADED,
                capabilities=capabilities,
                context_limit=8192,
            )
            for model_id, capabilities in sorted(self.model_capabilities.items())
        )

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.load_calls += 1
        self.states[model_id] = ModelRuntimeState.LOADED
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        self.states[model_id] = ModelRuntimeState.AVAILABLE
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        self.chat_calls += 1
        return ChatResult(request_id=request.request_id, success=True, content="unexpected")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        count = 1 if isinstance(request.input, str) else len(request.input)
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=tuple((float(index),) for index in range(count)),
        )

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise AssertionError(f"unexpected stream request: {request.request_id}")

    async def aclose(self) -> None:
        return None


def _config(
    root: Path,
    *,
    models: tuple[ModelConfig, ...],
    placements: tuple[PlacementConfig, ...],
    backend_ids: tuple[str, ...],
) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(socket_path=root / "daemon.sock", probe_interval_seconds=60),
        storage=StorageConfig(database_path=root / "state.db"),
        nodes=(NodeConfig(id="node", display_name="Node", platform="macos", memory_gb=64),),
        backends=tuple(
            BackendConfig(
                id=backend_id,
                node_id="node",
                kind=BackendKind.OLLAMA,
                base_url=f"http://127.0.0.1:{8100 + index}",
            )
            for index, backend_id in enumerate(backend_ids)
        ),
        models=models,
        placements=placements,
    )


async def _client(socket_path: Path) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=str(socket_path)),
        base_url="http://omlxc",
    )


def _model(payload: dict[str, object], model_id: str) -> dict[str, object]:
    items = cast(list[dict[str, object]], cast(dict[str, object], payload["data"])["items"])
    return next(item for item in items if item["id"] == model_id)


@pytest.mark.asyncio
async def test_empty_runtime_capabilities_use_role_seed_without_backend_broadcast(
    short_root: Path,
) -> None:
    config = _config(
        short_root,
        backend_ids=("broad", "narrow"),
        models=(
            ModelConfig(id="local/chat", category="llm", role="chat", engine="ollama"),
            ModelConfig(id="local/embed", category="retrieval", role="embedding", engine="omlx"),
        ),
        placements=(
            PlacementConfig(
                id="chat-broad",
                model_id="local/chat",
                backend_id="broad",
                backend_model_id="physical/chat",
                context_limit=8192,
                memory_gb=2,
            ),
            PlacementConfig(
                id="embed-narrow",
                model_id="local/embed",
                backend_id="narrow",
                backend_model_id="physical/embed",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )
    broad = CapabilityBackend(
        "broad",
        backend_capabilities=frozenset(
            {
                AdapterCapability.CHAT,
                AdapterCapability.STREAMING,
                AdapterCapability.VISION,
                AdapterCapability.EMBEDDING,
                AdapterCapability.MODEL_LIFECYCLE,
                AdapterCapability.TUNING,
            }
        ),
        model_capabilities={"physical/chat": frozenset()},
    )
    narrow = CapabilityBackend(
        "narrow",
        backend_capabilities=frozenset({AdapterCapability.CHAT, AdapterCapability.STREAMING}),
        model_capabilities={"physical/embed": frozenset()},
    )
    composition = build_production_daemon(
        config,
        adapters={
            "broad": cast(BackendAdapter, broad),
            "narrow": cast(BackendAdapter, narrow),
        },
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            models = await client.get("/api/v1/models")
            chat_embedding = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/chat", "required_capabilities": ["embedding"]},
            )
            embedding = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/embed", "required_capabilities": ["embedding"]},
            )
            vision = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/chat",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "describe"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "https://images.invalid/local.png"},
                                },
                            ],
                        }
                    ],
                },
            )
    finally:
        await server.stop()

    assert models.status_code == 200
    assert set(cast(list[str], _model(models.json(), "local/chat")["capabilities"])) == {
        "chat",
        "streaming",
    }
    assert set(cast(list[str], _model(models.json(), "local/embed")["capabilities"])) == {
        "embedding"
    }
    assert chat_embedding.status_code == 409
    assert chat_embedding.json()["error"]["partial_result"]["rejected"] == {
        "chat-broad": "capability_missing",
        "embed-narrow": "model_mismatch",
    }
    assert embedding.status_code == 200
    assert embedding.json()["data"]["selected_placement_id"] == "embed-narrow"
    assert vision.status_code == 409
    assert vision.json()["error"]["type"] == "insufficient_capacity"
    assert broad.load_calls == broad.chat_calls == 0


@pytest.mark.asyncio
async def test_nonempty_runtime_capabilities_replace_seed_and_respect_transport_upper_bound(
    short_root: Path,
) -> None:
    config = _config(
        short_root,
        backend_ids=("backend",),
        models=(ModelConfig(id="local/model", category="llm", role="chat", engine="test"),),
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
    backend = CapabilityBackend(
        "backend",
        backend_capabilities=frozenset(
            {AdapterCapability.CHAT, AdapterCapability.EMBEDDING, AdapterCapability.TUNING}
        ),
        model_capabilities={
            "physical/model": frozenset(
                {AdapterCapability.EMBEDDING, AdapterCapability.VISION, AdapterCapability.TUNING}
            )
        },
    )
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            models = await client.get("/api/v1/models")
            embedding = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/model", "required_capabilities": ["embedding"]},
            )
            chat = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/model", "required_capabilities": ["chat"]},
            )
            vision = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/model", "required_capabilities": ["vision"]},
            )
    finally:
        await server.stop()

    assert set(cast(list[str], _model(models.json(), "local/model")["capabilities"])) == {
        "embedding"
    }
    assert embedding.status_code == 200
    assert chat.status_code == 409
    assert vision.status_code == 409


@pytest.mark.asyncio
async def test_same_model_multi_backend_capabilities_remain_independent_and_deterministic(
    short_root: Path,
) -> None:
    config = _config(
        short_root,
        backend_ids=("embed", "chat"),
        models=(ModelConfig(id="local/multi", category="llm", role="chat", engine="test"),),
        placements=(
            PlacementConfig(
                id="a-embed",
                model_id="local/multi",
                backend_id="embed",
                backend_model_id="physical/embed",
                context_limit=8192,
                memory_gb=2,
            ),
            PlacementConfig(
                id="b-chat",
                model_id="local/multi",
                backend_id="chat",
                backend_model_id="physical/chat",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )
    embed = CapabilityBackend(
        "embed",
        backend_capabilities=frozenset({AdapterCapability.EMBEDDING}),
        model_capabilities={"physical/embed": frozenset({AdapterCapability.EMBEDDING})},
    )
    chat = CapabilityBackend(
        "chat",
        backend_capabilities=frozenset({AdapterCapability.CHAT}),
        model_capabilities={
            "physical/chat": frozenset({AdapterCapability.CHAT, AdapterCapability.VISION})
        },
    )
    composition = build_production_daemon(
        config,
        adapters={
            "embed": cast(BackendAdapter, embed),
            "chat": cast(BackendAdapter, chat),
        },
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            first = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/multi", "required_capabilities": ["embedding"]},
            )
            second = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/multi", "required_capabilities": ["embedding"]},
            )
            chat_route = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/multi", "required_capabilities": ["chat"]},
            )
            vision = await client.post(
                "/api/v1/routes/plan",
                json={"model_id": "local/multi", "required_capabilities": ["vision"]},
            )
    finally:
        await server.stop()

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["selected_placement_id"] == "a-embed"
    assert second.json()["data"]["selected_placement_id"] == "a-embed"
    assert first.json()["data"]["rejected"] == {"b-chat": "capability_missing"}
    assert chat_route.status_code == 200
    assert chat_route.json()["data"]["selected_placement_id"] == "b-chat"
    assert chat_route.json()["data"]["rejected"] == {"a-embed": "capability_missing"}
    assert vision.status_code == 409
    assert vision.json()["error"]["partial_result"]["rejected"] == {
        "a-embed": "capability_missing",
        "b-chat": "capability_missing",
    }
