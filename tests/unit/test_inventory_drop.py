from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

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
from omlxc.daemon import build_production_daemon
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
from omlxc.health.inventory import (
    INVENTORY_DROP_CODE,
    inventory_count,
    is_inventory_cliff,
)
from omlxc.storage import InventoryHighWater, SQLiteRuntimeStore


def test_cliff_is_strictly_more_than_thirty_percent() -> None:
    assert is_inventory_cliff(10, 6)
    assert not is_inventory_cliff(10, 7)
    assert not is_inventory_cliff(10, 9)
    assert not is_inventory_cliff(10, 10)
    assert not is_inventory_cliff(0, 0)
    assert inventory_count(("a", "a", "b")) == 2


class InventoryBackend:
    def __init__(self, *, backend_id: str = "backend") -> None:
        self.backend_id = backend_id
        self.fail = False
        self.timeout = False
        self.ids: tuple[str, ...] = tuple(f"model-{index}" for index in range(10))

    def set_ids(self, count: int) -> None:
        self.ids = tuple(f"model-{index}" for index in range(count))

    async def discover(self) -> CapabilitySnapshot:
        if self.timeout:
            await asyncio.sleep(30)
        if self.fail:
            raise RuntimeError("backend probe failed")
        return CapabilitySnapshot(
            backend_id=self.backend_id,
            reachable=True,
            compatible=True,
            model_available=True,
            generation_ready=True,
            observed_at=datetime.now(UTC),
            capabilities=frozenset({AdapterCapability.CHAT}),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        if self.timeout:
            await asyncio.sleep(30)
        if self.fail:
            raise RuntimeError("backend list failed")
        return tuple(
            ModelRuntime(
                id=model_id,
                state=ModelRuntimeState.AVAILABLE,
                loaded=False,
                capabilities=frozenset({AdapterCapability.CHAT}),
                context_limit=4096,
            )
            for model_id in self.ids
        )

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=False,
            idempotency_key=idempotency_key,
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=False,
            idempotency_key=idempotency_key,
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(request_id=request.request_id, success=True, content="ok")

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


def _config(root: Path) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(
            socket_path=root / "omlxcd.sock",
            probe_interval_seconds=60.0,
        ),
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
                backend_model_id="model-0",
                context_limit=8192,
                memory_gb=2,
            ),
        ),
    )


async def _started(root: Path, backend: InventoryBackend):
    composition = build_production_daemon(config=_config(root), adapters={"backend": backend})
    await composition.runtime.start()
    return composition


@pytest.mark.asyncio
async def test_first_success_seeds_high_water_without_warning(tmp_path: Path) -> None:
    backend = InventoryBackend()
    composition = await _started(tmp_path, backend)
    try:
        health = await composition.control.health()
    finally:
        await composition.runtime.close()
    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    try:
        records = await store.list_inventory_high_water()
    finally:
        await store.close()

    assert health["status"] == "ready"
    assert health["degraded"] is False
    assert health["warnings"] == []
    assert records == (
        InventoryHighWater(
            node_id="node",
            backend_id="backend",
            high_water_count=10,
            observed_at=records[0].observed_at,
        ),
    )


@pytest.mark.asyncio
async def test_small_fluctuation_does_not_warn(tmp_path: Path) -> None:
    backend = InventoryBackend()
    composition = await _started(tmp_path, backend)
    try:
        backend.set_ids(9)
        await composition.control.probe_node("node")
        health = await composition.control.health()
    finally:
        await composition.runtime.close()

    assert health["warnings"] == []
    assert health["degraded"] is False


@pytest.mark.asyncio
async def test_cliff_warns_and_restore_clears_without_degrading(tmp_path: Path) -> None:
    backend = InventoryBackend()
    composition = await _started(tmp_path, backend)
    try:
        backend.set_ids(6)
        await composition.control.probe_node("node")
        dropped = await composition.control.health()
        backend.fail = True
        await composition.control.probe_node("node")
        failed = await composition.control.health()
        backend.fail = False
        backend.set_ids(8)
        await composition.control.probe_node("node")
        restored = await composition.control.health()
    finally:
        await composition.runtime.close()

    assert dropped["degraded"] is False
    assert dropped["warnings"] == [
        {
            "code": INVENTORY_DROP_CODE,
            "node_id": "node",
            "backend_id": "backend",
            "baseline": 10,
            "current": 6,
        }
    ]
    assert failed["warnings"] == dropped["warnings"]
    assert restored["warnings"] == []
    assert restored["degraded"] is False


@pytest.mark.asyncio
async def test_timeout_is_not_inventory_drift(tmp_path: Path) -> None:
    backend = InventoryBackend()
    composition = await _started(tmp_path, backend)
    try:
        backend.timeout = True
        await composition.control.probe_node("node")
        health = await composition.control.health()
    finally:
        await composition.runtime.close()
    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    try:
        records = await store.list_inventory_high_water()
    finally:
        await store.close()

    assert health["warnings"] == []
    assert records[0].high_water_count == 10


@pytest.mark.asyncio
async def test_restart_compares_against_persisted_high_water(tmp_path: Path) -> None:
    backend = InventoryBackend()
    composition = await _started(tmp_path, backend)
    await composition.runtime.close()
    backend.set_ids(6)
    composition = await _started(tmp_path, backend)
    try:
        health = await composition.control.health()
    finally:
        await composition.runtime.close()

    assert health["warnings"] == [
        {
            "code": INVENTORY_DROP_CODE,
            "node_id": "node",
            "backend_id": "backend",
            "baseline": 10,
            "current": 6,
        }
    ]
