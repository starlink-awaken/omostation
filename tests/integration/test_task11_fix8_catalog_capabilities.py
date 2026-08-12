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
from omlxc.scheduler import PlacementSnapshot


@pytest.fixture
def short_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="omlxc-fix8-") as directory:
        yield Path(directory)


class CapabilityBackend:
    def __init__(
        self,
        backend_id: str,
        *,
        backend_capabilities: frozenset[AdapterCapability],
        model_capabilities: Mapping[str, frozenset[AdapterCapability]],
        initial_states: Mapping[str, ModelRuntimeState] | None = None,
        generation_ready: bool | None = None,
        complete_load: bool = True,
        load_status: OperationStatus = OperationStatus.SUCCEEDED,
    ) -> None:
        self.backend_id = backend_id
        self.backend_capabilities = backend_capabilities
        self.model_capabilities = dict(model_capabilities)
        self.states = {
            model_id: (
                initial_states[model_id]
                if initial_states is not None
                else ModelRuntimeState.AVAILABLE
            )
            for model_id in model_capabilities
        }
        self.generation_ready = generation_ready
        self.complete_load = complete_load
        self.load_status = load_status
        self.load_calls = 0
        self.chat_calls = 0
        self.embed_calls = 0

    async def discover(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            backend_id=self.backend_id,
            reachable=True,
            compatible=True,
            model_available=bool(self.states),
            generation_ready=(
                self.generation_ready
                if self.generation_ready is not None
                else any(state is ModelRuntimeState.LOADED for state in self.states.values())
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
        if self.complete_load and self.load_status is OperationStatus.SUCCEEDED:
            self.states[model_id] = ModelRuntimeState.LOADED
        return LifecycleResult(
            model_id=model_id,
            status=self.load_status,
            changed=self.load_status is OperationStatus.SUCCEEDED,
            idempotency_key=idempotency_key,
            error=(
                AdapterError(
                    code=AdapterErrorCode.MODEL_UNAVAILABLE,
                    message="model load failed",
                )
                if self.load_status is OperationStatus.FAILED
                else None
            ),
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
        self.embed_calls += 1
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


@pytest.mark.asyncio
async def test_loaded_mixed_modalities_apply_generation_readiness_per_placement(
    short_root: Path,
) -> None:
    config = _config(
        short_root,
        backend_ids=("backend",),
        models=(
            ModelConfig(id="local/chat", category="llm", role="chat", engine="omlx"),
            ModelConfig(id="local/embed", category="retrieval", role="embedding", engine="omlx"),
            ModelConfig(id="local/vision", category="vision", role="vision", engine="omlx"),
        ),
        placements=tuple(
            PlacementConfig(
                id=f"{role}-placement",
                model_id=f"local/{role}",
                backend_id="backend",
                backend_model_id=f"physical/{role}",
                context_limit=8192,
                memory_gb=2,
            )
            for role in ("chat", "embed", "vision")
        ),
    )
    runtime_capabilities = {f"physical/{role}": frozenset() for role in ("chat", "embed", "vision")}
    backend = CapabilityBackend(
        "backend",
        backend_capabilities=frozenset(
            {
                AdapterCapability.CHAT,
                AdapterCapability.STREAMING,
                AdapterCapability.VISION,
                AdapterCapability.EMBEDDING,
            }
        ),
        model_capabilities=runtime_capabilities,
        initial_states={model_id: ModelRuntimeState.LOADED for model_id in runtime_capabilities},
        generation_ready=False,
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
                "/openai/v1/embeddings",
                json={"model": "local/embed", "input": "hello"},
            )
            chat = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/chat",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            vision = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": "local/vision",
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

    embed_state = cast(
        list[dict[str, object]], _model(models.json(), "local/embed")["placement_states"]
    )[0]
    chat_state = cast(
        list[dict[str, object]], _model(models.json(), "local/chat")["placement_states"]
    )[0]
    vision_state = cast(
        list[dict[str, object]], _model(models.json(), "local/vision")["placement_states"]
    )[0]
    assert embed_state["available"] is embed_state["ready"] is True
    assert chat_state["available"] is chat_state["ready"] is False
    assert vision_state["available"] is vision_state["ready"] is False
    assert embedding.status_code == 200
    assert embedding.json()["data"][0]["embedding"] == [0.0]
    assert chat.status_code == vision.status_code == 409
    assert backend.embed_calls == 1
    assert backend.chat_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "complete_load", "load_status", "expected_status", "expected_embed_calls"),
    [
        ("success", True, OperationStatus.SUCCEEDED, 200, 1),
        ("postverify", False, OperationStatus.SUCCEEDED, 409, 0),
        ("failed", False, OperationStatus.FAILED, 409, 0),
    ],
)
async def test_cold_embedding_load_requires_physical_postverify_before_exactly_once_embed(
    short_root: Path,
    mode: str,
    complete_load: bool,
    load_status: OperationStatus,
    expected_status: int,
    expected_embed_calls: int,
) -> None:
    config = _config(
        short_root,
        backend_ids=("backend",),
        models=(
            ModelConfig(id="local/embed", category="retrieval", role="embedding", engine="omlx"),
        ),
        placements=(
            PlacementConfig(
                id="embedding-placement",
                model_id="local/embed",
                backend_id="backend",
                backend_model_id="physical/embed",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )
    backend = CapabilityBackend(
        "backend",
        backend_capabilities=frozenset({AdapterCapability.CHAT, AdapterCapability.STREAMING}),
        model_capabilities={"physical/embed": frozenset()},
        generation_ready=False,
        complete_load=complete_load,
        load_status=load_status,
    )
    composition = build_production_daemon(
        config, adapters={"backend": cast(BackendAdapter, backend)}
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            response = await client.post(
                "/openai/v1/embeddings",
                headers={"X-OMLXC-Request-ID": f"fix9.{mode}"},
                json={"model": "local/embed", "input": "hello"},
            )
            models = await client.get("/api/v1/models")
    finally:
        await server.stop()

    state = cast(list[dict[str, object]], _model(models.json(), "local/embed")["placement_states"])[
        0
    ]
    assert response.status_code == expected_status
    assert backend.load_calls == 1
    assert backend.embed_calls == expected_embed_calls
    assert state["loaded"] is (mode == "success")
    assert state["ready"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"available": False}, "unavailable"),
        ({"authorized": False}, "authorization"),
        ({"fresh": False}, "stale"),
        ({"local": False, "security_allowed": False}, "local-security"),
        ({"memory_admitted": False}, "memory"),
    ],
)
async def test_embedding_scheduler_blockers_remain_fail_closed(
    short_root: Path, updates: Mapping[str, object], reason: str
) -> None:
    config = _config(
        short_root,
        backend_ids=("backend",),
        models=(
            ModelConfig(id="local/embed", category="retrieval", role="embedding", engine="omlx"),
        ),
        placements=(
            PlacementConfig(
                id="embedding-placement",
                model_id="local/embed",
                backend_id="backend",
                backend_model_id="physical/embed",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )
    values: dict[str, object] = {
        "placement_id": "embedding-placement",
        "model_id": "local/embed",
        "backend_id": "backend",
        "backend_model_id": "physical/embed",
        "node_id": "node",
        "fresh": True,
        "available": True,
        "authorized": True,
        "capabilities": frozenset({"embedding"}),
        "context_limit": 8192,
        "memory_admitted": True,
        "loaded": True,
        "ttft_ms": None,
        "throughput_tps": None,
        "queue_depth": 0,
        "error_rate": 0.0,
        "network_cost_ms": 0.0,
        "affinity": 0.0,
        "available_concurrency": 1,
        "local": True,
        "security_allowed": True,
    }
    values.update(updates)
    snapshot = PlacementSnapshot(**values)  # type: ignore[arg-type]
    backend = CapabilityBackend(
        "backend",
        backend_capabilities=frozenset({AdapterCapability.EMBEDDING}),
        model_capabilities={"physical/embed": frozenset({AdapterCapability.EMBEDDING})},
        initial_states={"physical/embed": ModelRuntimeState.LOADED},
        generation_ready=False,
    )
    composition = build_production_daemon(
        config,
        adapters={"backend": cast(BackendAdapter, backend)},
        snapshots=(snapshot,),
    )
    server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
    await server.start()
    try:
        async with await _client(config.daemon.socket_path) as client:
            response = await client.post(
                "/openai/v1/embeddings",
                headers={"X-OMLXC-Request-ID": f"fix9.blocked.{reason}"},
                json={"model": "local/embed", "input": "hello"},
            )
            models = await client.get("/api/v1/models")
    finally:
        await server.stop()

    state = cast(list[dict[str, object]], _model(models.json(), "local/embed")["placement_states"])[
        0
    ]
    assert response.status_code == 409
    assert state["ready"] is False
    assert backend.load_calls == backend.embed_calls == 0
