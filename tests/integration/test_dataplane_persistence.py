from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from omlxc.dataplane import (
    AdapterBinding,
    AdapterRegistry,
    BoundRouteTelemetry,
    CapacityCoordinator,
    DataPlaneOrchestrator,
    ExecutionErrorCode,
    RouteTelemetryRecorder,
)
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
)
from omlxc.scheduler import PlacementSnapshot, RoutePlanner, default_policies
from omlxc.storage import SQLiteRuntimeStore


def _placement(pid: str) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=pid,
        model_id="public/model",
        backend_id=f"backend-{pid}",
        backend_model_id=f"physical-{pid}",
        node_id=f"node-{pid}",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat", "embedding", "streaming"}),
        context_limit=8192,
        memory_admitted=True,
        loaded=True,
        ttft_ms=10,
        throughput_tps=50,
        queue_depth=0,
        error_rate=0,
        network_cost_ms=1,
        affinity=1,
        available_concurrency=1,
        local=True,
        security_allowed=True,
    )


@pytest.mark.asyncio
async def test_route_audit_and_metrics_are_redacted_and_restart_safe(tmp_path: object) -> None:
    from pathlib import Path

    db = Path(str(tmp_path)) / "state.db"
    request = RouteRequest(
        request_id="req-1",
        model_id="public/model",
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat"}),
        context_tokens=10,
    )
    decision = RoutePlanner(default_policies()).plan(request, (_placement("p"),))
    recorder = RouteTelemetryRecorder(now=lambda: datetime(2026, 8, 11, tzinfo=UTC))

    async with await SQLiteRuntimeStore.open(db) as store:
        await recorder.record_route(store, decision)
        assert recorder.record_metric(store, request_id="req-1", latency_ms=12.5, success=True)
        await store.flush_metrics()

    async with await SQLiteRuntimeStore.open(db) as reopened:
        audits = await reopened.list_route_audits(after_sequence=0)
        assert audits[0].request_id == "req-1"
        assert audits[0].candidates[0].startswith("p@")
        assert "prompt" not in repr(audits).lower()
        assert await reopened.metric_count() == 1


def test_planner_is_pure_and_repeatable_without_repository_access() -> None:
    request = RouteRequest(
        request_id="req",
        model_id="public/model",
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat"}),
        context_tokens=1,
    )
    planner = RoutePlanner(default_policies())
    snapshot = (_placement("p"),)
    assert planner.plan(request, snapshot) == planner.plan(request, snapshot)


class PersistingAdapter:
    async def chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(request_id=request.request_id, success=True, content="not-persisted")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=((1.0, 2.0),),
        )

    def stream_chat(self, request: ChatRequest) -> object:
        async def events() -> object:
            yield StreamEvent(
                kind=StreamEventKind.DONE,
                request_id=request.request_id,
                emitted_content=False,
                phase=StreamPhase.COMPLETE,
            )

        return events()


@pytest.mark.asyncio
async def test_orchestrator_persists_route_and_terminal_metric_across_restart(
    tmp_path: object,
) -> None:
    from pathlib import Path

    db = Path(str(tmp_path)) / "orchestrator.db"
    placement = _placement("p")
    route = RouteRequest(
        request_id="req-auto",
        model_id="public/model",
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat"}),
        context_tokens=1,
    )
    chat = ChatRequest(
        request_id="req-auto",
        model="public/model",
        messages=(ChatMessage(role="user", content="never persist me"),),
    )
    async with await SQLiteRuntimeStore.open(db) as store:
        telemetry = BoundRouteTelemetry(
            store,
            RouteTelemetryRecorder(now=lambda: datetime(2026, 8, 11, tzinfo=UTC)),
        )
        orchestrator = DataPlaneOrchestrator(
            planner=RoutePlanner(default_policies()),
            snapshot_provider=lambda: (placement,),
            registry=AdapterRegistry((AdapterBinding(placement.backend_id, PersistingAdapter()),)),
            capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
            telemetry=telemetry,
        )
        result = await orchestrator.chat(route, chat, deadline=10)
        assert result.success
        embedding_route = route.model_copy(
            update={"required_capabilities": frozenset({"embedding"})}
        )
        embedding = await orchestrator.embed(
            embedding_route,
            EmbeddingRequest(request_id="req-embed", model="public/model", input="one"),
            deadline=10,
        )
        assert embedding.error is None
        streaming_route = route.model_copy(
            update={"required_capabilities": frozenset({"chat", "streaming"})}
        )
        stream = [
            event
            async for event in orchestrator.stream_chat(
                streaming_route,
                chat.model_copy(update={"request_id": "req-stream"}),
                deadline=10,
            )
        ]
        assert [event.kind for event in stream] == [StreamEventKind.DONE]
        await store.flush_metrics()

    async with await SQLiteRuntimeStore.open(db) as reopened:
        audits = await reopened.list_route_audits(after_sequence=0)
        assert [audit.request_id for audit in audits] == [
            "req-auto",
            "req-auto",
            "req-auto",
        ]
        assert await reopened.metric_count() == 3
        assert "never persist me" not in repr(audits)


@pytest.mark.asyncio
async def test_terminal_metric_persists_safe_error_code_and_phase_across_restart(
    tmp_path: object,
) -> None:
    from pathlib import Path

    db = Path(str(tmp_path)) / "terminal.db"
    placement = replace(_placement("cold"), loaded=False)
    route = RouteRequest(
        request_id="req-terminal",
        model_id="public/model",
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat"}),
        context_tokens=1,
    )
    request = ChatRequest(
        request_id="req-terminal",
        model="public/model",
        messages=(ChatMessage(role="user", content="never persist me"),),
    )
    async with await SQLiteRuntimeStore.open(db) as store:
        orchestrator = DataPlaneOrchestrator(
            planner=RoutePlanner(default_policies()),
            snapshot_provider=lambda: (placement,),
            registry=AdapterRegistry(
                (AdapterBinding(placement.backend_id, PersistingAdapter()),)
            ),
            capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
            telemetry=BoundRouteTelemetry(
                store,
                RouteTelemetryRecorder(now=lambda: datetime(2026, 8, 11, tzinfo=UTC)),
            ),
        )
        result = await orchestrator.chat(route, request, deadline=10)
        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.NO_CANDIDATE
        await store.flush_metrics()

    async with await SQLiteRuntimeStore.open(db) as reopened:
        metrics = await reopened.list_metrics(after_sequence=0)

    assert len(metrics) == 1
    assert metrics[0].error_code == "unavailable"
    assert metrics[0].phase == StreamPhase.BEFORE_CONTENT.value
    assert "never persist me" not in repr(metrics)
