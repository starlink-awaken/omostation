"""placement.resident=True 此前只是类型系统里"活着"的声明字段, 真正执行
"周期性检查+ensure_loaded"的 ReconciliationEngine/ReconcileLoop 从未被
daemon 组装流程(build_production_daemon)实例化启动 —— 和 remote_resident
是同一类"写好了但没接入"的模式。这里验证接入本身: resident 的 placement
在 daemon 启动后被自动加载, 非 resident 的 placement 保持不动, 内存压力
时被 MemoryAdmissionPolicy 正确拒绝。
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omlxc.autonomy import MemorySnapshot
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
    TuneRequest,
    TuneResult,
)


class FakeBackend:
    def __init__(self) -> None:
        self.operations: list[tuple[str, str, str | None]] = []
        self.loaded = False

    async def load_model(self, model_id: str, *, idempotency_key: str | None = None) -> LifecycleResult:
        self.operations.append(("load", model_id, idempotency_key))
        self.loaded = True
        return LifecycleResult(
            model_id=model_id, status=OperationStatus.SUCCEEDED, changed=True, idempotency_key=idempotency_key
        )

    async def unload_model(self, model_id: str, *, idempotency_key: str | None = None) -> LifecycleResult:
        self.operations.append(("unload", model_id, idempotency_key))
        self.loaded = False
        return LifecycleResult(
            model_id=model_id, status=OperationStatus.SUCCEEDED, changed=True, idempotency_key=idempotency_key
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
            capabilities=frozenset({AdapterCapability.CHAT, AdapterCapability.EMBEDDING, AdapterCapability.STREAMING}),
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
        return EmbeddingResult(request_id=request.request_id, status=OperationStatus.SUCCEEDED, embeddings=((1.0,),))

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def tune(self, request: TuneRequest) -> TuneResult:
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=OperationStatus.SUCCEEDED,
            idempotency_key=request.idempotency_key,
        )

    async def aclose(self) -> None:
        return None


def _config(root: Path, *, resident: bool, reconcile_interval_seconds: float = 0.02) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(
            socket_path=root / "omlxcd.sock",
            reconcile_interval_seconds=reconcile_interval_seconds,
        ),
        storage=StorageConfig(database_path=root / "state.db"),
        nodes=(NodeConfig(id="node", display_name="Node", platform="macos", memory_gb=16),),
        backends=(
            BackendConfig(
                id="backend", node_id="node", kind=BackendKind.OMLX_APP, base_url="http://127.0.0.1:8000"
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
                resident=resident,
            ),
        ),
    )


async def _ample_memory() -> MemorySnapshot | None:
    return MemorySnapshot(total_gb=64.0, available_gb=40.0, observed_monotonic=time.monotonic())


async def _scarce_memory() -> MemorySnapshot | None:
    return MemorySnapshot(total_gb=64.0, available_gb=1.0, observed_monotonic=time.monotonic())


async def _wait_until(predicate: Callable[[], bool], *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("condition did not become true within timeout")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_resident_placement_is_auto_loaded_without_any_external_request() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-reconcile-resident-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root, resident=True)
        backend = FakeBackend()
        composition = build_production_daemon(config, adapters={"backend": backend}, memory_probe=_ample_memory)
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            await _wait_until(lambda: any(op[:2] == ("load", "physical/model") for op in backend.operations))
        finally:
            await server.stop()

    assert composition.runtime.task_settled


@pytest.mark.asyncio
async def test_non_resident_placement_is_left_untouched() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-reconcile-non-resident-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root, resident=False)
        backend = FakeBackend()
        composition = build_production_daemon(config, adapters={"backend": backend}, memory_probe=_ample_memory)
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            # 给 reconcile loop 足够时间跑好几轮 (interval=0.02s), 确认它确实
            # 什么都没做, 而不是"还没来得及做"。
            await asyncio.sleep(0.2)
        finally:
            await server.stop()

    assert backend.operations == []
    assert composition.runtime.task_settled


@pytest.mark.asyncio
async def test_resident_placement_is_denied_when_memory_probe_reports_pressure() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-reconcile-memory-pressure-", dir="/tmp") as directory:
        root = Path(directory)
        config = _config(root, resident=True)
        backend = FakeBackend()
        composition = build_production_daemon(config, adapters={"backend": backend}, memory_probe=_scarce_memory)
        server = DaemonServer(composition.app, socket_path=config.daemon.socket_path)
        await server.start()
        try:
            await asyncio.sleep(0.2)
        finally:
            await server.stop()

    assert backend.operations == []
    assert composition.runtime.task_settled
