from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator

import pytest

from omlxc.autonomy import (
    PlacementOperationOutcome,
    PlacementProbeFailure,
    PlacementProbeReason,
    PlacementTarget,
)
from omlxc.dataplane import (
    AdapterBinding,
    AdapterRegistry,
    CapacityCoordinator,
    DataPlaneOrchestrator,
    ExecutionErrorCode,
    RerankRequest,
    RerankResult,
)
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    ChatMessage,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    ImageContentBlock,
    ImageURL,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
)
from omlxc.scheduler import PlacementSnapshot, RejectionCode, RoutePlanner, default_policies


class FakeAdapter:
    def __init__(
        self,
        *,
        chats: list[ChatResult | BaseException] | None = None,
        embeddings: list[EmbeddingResult | BaseException] | None = None,
    ) -> None:
        self.chats = chats or []
        self.embeddings = embeddings or []
        self.chat_requests: list[ChatRequest] = []
        self.embedding_requests: list[EmbeddingRequest] = []
        self.stream_requests: list[ChatRequest] = []
        self.active = 0
        self.max_active = 0
        self.release = asyncio.Event()

    async def chat(self, request: ChatRequest) -> ChatResult:
        self.chat_requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.release.is_set():
            await asyncio.sleep(0)
        try:
            result = self.chats.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        finally:
            self.active -= 1

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.embedding_requests.append(request)
        result = self.embeddings.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.stream_requests.append(request)
        raise NotImplementedError


class FakeLoader:
    def __init__(self, *, loaded: bool) -> None:
        self.loaded = loaded
        self.targets: list[PlacementTarget] = []

    async def ensure_loaded(self, target: PlacementTarget) -> PlacementOperationOutcome:
        self.targets.append(target)
        return PlacementOperationOutcome(self.loaded, True, None)


class RejectingLoader:
    def __init__(self, rejection: RejectionCode) -> None:
        self.rejection = rejection

    async def ensure_loaded(self, target: PlacementTarget) -> PlacementOperationOutcome:
        if self.rejection is RejectionCode.NO_CAPACITY:
            raise TimeoutError
        if self.rejection in {
            RejectionCode.AUTHORIZATION,
            RejectionCode.STALE,
            RejectionCode.UNAVAILABLE,
            RejectionCode.LOCAL_SECURITY,
        }:
            reason = {
                RejectionCode.AUTHORIZATION: PlacementProbeReason.AUTHORIZATION,
                RejectionCode.STALE: PlacementProbeReason.STALE,
                RejectionCode.UNAVAILABLE: PlacementProbeReason.UNAVAILABLE,
                RejectionCode.LOCAL_SECURITY: PlacementProbeReason.LOCAL_SECURITY,
            }[self.rejection]
            raise PlacementProbeFailure(target.id, reason)
        return PlacementOperationOutcome(True, True, None)


def _snapshot(pid: str, backend: str, node: str, **updates: object) -> PlacementSnapshot:
    values: dict[str, object] = {
        "placement_id": pid,
        "model_id": "public/model",
        "backend_id": backend,
        "backend_model_id": f"physical/{pid}",
        "node_id": node,
        "fresh": True,
        "available": True,
        "authorized": True,
        "capabilities": frozenset({"chat", "vision", "embedding"}),
        "context_limit": 8192,
        "memory_admitted": True,
        "loaded": True,
        "ttft_ms": 10.0,
        "throughput_tps": 50.0,
        "queue_depth": 0,
        "error_rate": 0.0,
        "network_cost_ms": 1.0,
        "affinity": 1.0,
        "available_concurrency": 1,
        "local": True,
        "security_allowed": True,
    }
    values.update(updates)
    return PlacementSnapshot(**values)


def _route_request(**updates: object) -> RouteRequest:
    values: dict[str, object] = {
        "request_id": "req",
        "model_id": "public/model",
        "profile": RouteProfile.INTERACTIVE,
        "required_capabilities": frozenset({"chat"}),
        "context_tokens": 16,
    }
    values.update(updates)
    return RouteRequest.model_validate(values)


def _chat() -> ChatRequest:
    return ChatRequest(
        request_id="req",
        model="public/model",
        messages=(ChatMessage(role="user", content="private prompt"),),
    )


def _failure(code: AdapterErrorCode, *, retryable: bool) -> ChatResult:
    return ChatResult(
        request_id="req",
        success=False,
        error=AdapterError(code=code, message="safe", retryable=retryable),
    )


def _success(content: str = "ok") -> ChatResult:
    return ChatResult(request_id="req", success=True, content=content)


def _orchestrator(
    placements: tuple[PlacementSnapshot, ...], bindings: tuple[AdapterBinding, ...]
) -> DataPlaneOrchestrator:
    return DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: placements,
        registry=AdapterRegistry(bindings),
        capacity=CapacityCoordinator(global_limit=4, per_node=2, per_backend=2),
    )


@pytest.mark.asyncio
async def test_chat_maps_backend_model_and_preserves_public_identity_with_failover() -> None:
    first = FakeAdapter(chats=[_failure(AdapterErrorCode.TIMEOUT, retryable=True)])
    second = FakeAdapter(chats=[_success()])
    placements = (
        _snapshot("a", "b1", "n1", affinity=1.0),
        _snapshot("b", "b2", "n2", affinity=0.5),
    )
    result = await _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    ).chat(_route_request(), _chat(), deadline=10.0)

    assert result.success
    assert result.model_id == "public/model"
    assert result.placement_id == "b"
    assert result.backend_id == "b2"
    assert result.profile is RouteProfile.INTERACTIVE
    assert result.attempted_placements == ("a", "b")
    assert first.chat_requests[0].model == "physical/a"
    assert second.chat_requests[0].model == "physical/b"
    assert second.chat_requests[0].messages[0].content == "private prompt"


@pytest.mark.asyncio
async def test_non_retryable_and_quality_thinking_fail_closed_without_fallback() -> None:
    first = FakeAdapter(chats=[_failure(AdapterErrorCode.INVALID_REQUEST, retryable=False)])
    second = FakeAdapter(chats=[_success()])
    placements = (_snapshot("a", "b1", "n1"), _snapshot("b", "b2", "n2"))
    orchestrator = _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    )

    invalid = await orchestrator.chat(_route_request(), _chat(), deadline=10.0)
    assert invalid.error is not None
    assert invalid.attempted_placements == ("a",)
    assert second.chat_requests == []
    assert "reasoning" not in first.chat_requests[0].model_dump()
    assert "thinking" not in first.chat_requests[0].model_dump()

    thinking = await orchestrator.chat(
        _route_request(profile=RouteProfile.QUALITY, thinking_requested=True),
        _chat(),
        deadline=10.0,
    )
    assert thinking.error is not None
    assert thinking.error.code is ExecutionErrorCode.UNSUPPORTED
    assert len(first.chat_requests) == 1


@pytest.mark.asyncio
async def test_vision_reuses_typed_message_without_fetching_or_rewriting_url() -> None:
    adapter = FakeAdapter(chats=[_success()])
    placement = _snapshot("p", "b", "n")
    request = ChatRequest(
        request_id="req",
        model="public/model",
        messages=(
            ChatMessage(
                role="user",
                content=(
                    ImageContentBlock(image_url=ImageURL(url="https://images.invalid/a.png")),
                ),
            ),
        ),
    )
    result = await _orchestrator((placement,), (AdapterBinding("b", adapter),)).chat(
        _route_request(required_capabilities=frozenset({"vision"})),
        request,
        deadline=10,
    )

    assert result.success
    assert adapter.chat_requests[0].messages == request.messages


@pytest.mark.asyncio
async def test_chat_transport_timeout_before_output_uses_remaining_fallback_budget() -> None:
    first = FakeAdapter(chats=[TimeoutError()])
    second = FakeAdapter(chats=[_success()])
    placements = (_snapshot("a", "b1", "n1"), _snapshot("b", "b2", "n2"))
    result = await _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    ).chat(_route_request(), _chat(), deadline=10)

    assert result.success
    assert result.attempted_placements == ("a", "b")


@pytest.mark.asyncio
async def test_unexpected_chat_exception_is_sanitized_and_not_retried() -> None:
    first = FakeAdapter(chats=[ValueError("prompt=do-not-leak")])
    second = FakeAdapter(chats=[_success()])
    placements = (_snapshot("a", "b1", "n1"), _snapshot("b", "b2", "n2"))
    result = await _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    ).chat(_route_request(), _chat(), deadline=10)

    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.BACKEND_FAILURE
    assert "do-not-leak" not in repr(result)
    assert second.chat_requests == []


def test_registry_rejects_duplicate_unknown_and_cross_binding() -> None:
    adapter = FakeAdapter()
    with pytest.raises(ValueError):
        AdapterRegistry((AdapterBinding("b", adapter), AdapterBinding("b", adapter)))
    registry = AdapterRegistry((AdapterBinding("b", adapter),))
    with pytest.raises(LookupError):
        registry.resolve(_snapshot("p", "missing", "n"))
    registry.resolve(_snapshot("p", "b", "n"))
    with pytest.raises(LookupError):
        registry.resolve(_snapshot("p", "b", "n", backend_model_id="changed"))


@pytest.mark.asyncio
async def test_embedding_preserves_batch_order_and_rejects_bad_shape() -> None:
    good = EmbeddingResult(
        request_id="req",
        status=OperationStatus.SUCCEEDED,
        embeddings=((1.0, 2.0), (3.0, 4.0)),
    )
    bad = EmbeddingResult(
        request_id="req",
        status=OperationStatus.SUCCEEDED,
        embeddings=((1.0,),),
    )
    adapter = FakeAdapter(embeddings=[good, bad])
    placement = _snapshot("p", "b", "n")
    orchestrator = _orchestrator((placement,), (AdapterBinding("b", adapter),))
    request = EmbeddingRequest(request_id="req", model="public/model", input=("one", "two"))

    success = await orchestrator.embed(
        _route_request(required_capabilities=frozenset({"embedding"})),
        request,
        deadline=10.0,
    )
    assert success.embeddings == ((1.0, 2.0), (3.0, 4.0))
    assert success.placement_id == "p"
    assert success.backend_id == "b"
    assert success.profile is RouteProfile.INTERACTIVE
    assert adapter.embedding_requests[0].model == "physical/p"

    invalid = await orchestrator.embed(
        _route_request(required_capabilities=frozenset({"embedding"})),
        request,
        deadline=10.0,
    )
    assert invalid.error is not None
    assert invalid.error.code is ExecutionErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_unexpected_embedding_exception_is_sanitized() -> None:
    adapter = FakeAdapter(embeddings=[ValueError("vector=do-not-leak")])
    placement = _snapshot("p", "b", "n")
    orchestrator = _orchestrator((placement,), (AdapterBinding("b", adapter),))
    request = EmbeddingRequest(request_id="req", model="public/model", input="one")

    result = await orchestrator.embed(
        _route_request(required_capabilities=frozenset({"embedding"})),
        request,
        deadline=10,
    )

    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.BACKEND_FAILURE
    assert "do-not-leak" not in repr(result)


class FakeReranker:
    async def rerank(self, request: RerankRequest) -> RerankResult:
        return RerankResult(
            scores=(0.5, 0.5, 0.8),
            placement_id="rerank-placement",
            backend_id="rerank-backend",
            profile=RouteProfile.QUALITY,
        )


class BrokenTelemetry:
    async def record_route(self, plan: object) -> None:
        raise RuntimeError("database-path=do-not-leak")

    def record_metric(
        self,
        *,
        request_id: str,
        latency_ms: float,
        success: bool,
        error_code: str | None = None,
        phase: str | None = None,
    ) -> bool:
        del request_id, latency_ms, success, error_code, phase
        raise RuntimeError("database-path=do-not-leak")


@pytest.mark.asyncio
async def test_rerank_validates_and_stably_orders_equal_scores() -> None:
    result = await DataPlaneOrchestrator.rerank(
        FakeReranker(),
        RerankRequest(request_id="r", query="q", documents=("a", "b", "c")),
    )
    assert [(item.index, item.score) for item in result.items] == [
        (2, 0.8),
        (0, 0.5),
        (1, 0.5),
    ]
    assert result.placement_id == "rerank-placement"
    assert result.backend_id == "rerank-backend"
    assert result.profile is RouteProfile.QUALITY


@pytest.mark.asyncio
async def test_telemetry_failures_are_fail_open_counted_and_safely_reported() -> None:
    adapter = FakeAdapter(chats=[_success()])
    placement = _snapshot("p", "b", "n")
    reports: list[str] = []
    orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: (placement,),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        telemetry=BrokenTelemetry(),
        telemetry_error_sink=reports.append,
    )

    result = await orchestrator.chat(_route_request(), _chat(), deadline=10)

    assert result.success
    assert orchestrator.telemetry_failure_count == 2
    assert reports == ["telemetry_write_failed", "telemetry_write_failed"]


@pytest.mark.asyncio
async def test_unloaded_placement_uses_shared_loader_then_rediscovers_before_call() -> None:
    adapter = FakeAdapter(chats=[_success()])
    unloaded = _snapshot("p", "b", "n", loaded=False)
    loaded = _snapshot("p", "b", "n", loaded=True)
    snapshots = iter(((unloaded,), (loaded,)))
    loader = FakeLoader(loaded=True)
    target = PlacementTarget(
        id="p",
        node_id="n",
        model_id="physical/p",
        resident=False,
        memory_gb=1,
        idle_unload_seconds=0,
        last_used_monotonic=0,
        rollback_reference="placement:p",
    )
    orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: next(snapshots),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        loader=loader,
        load_target=lambda _placement: target,
    )

    result = await orchestrator.chat(_route_request(), _chat(), deadline=10)

    assert result.success
    assert loader.targets == [target]
    assert len(adapter.chat_requests) == 1


@pytest.mark.asyncio
async def test_unloaded_placement_fails_closed_when_post_load_snapshot_is_not_loaded() -> None:
    adapter = FakeAdapter(chats=[_success()])
    unloaded = _snapshot("p", "b", "n", loaded=False)
    loader = FakeLoader(loaded=True)
    target = PlacementTarget(
        id="p",
        node_id="n",
        model_id="physical/p",
        resident=False,
        memory_gb=1,
        idle_unload_seconds=0,
        last_used_monotonic=0,
        rollback_reference="placement:p",
    )
    orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: (unloaded,),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        loader=loader,
        load_target=lambda _placement: target,
    )

    result = await orchestrator.chat(_route_request(), _chat(), deadline=10)

    assert not result.success
    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.NO_CANDIDATE
    assert adapter.chat_requests == []


@pytest.mark.asyncio
async def test_post_load_snapshot_replays_full_eligibility_filter() -> None:
    adapter = FakeAdapter(chats=[_success()])
    unloaded = _snapshot("p", "b", "n", loaded=False)
    refreshed_but_denied = _snapshot("p", "b", "n", loaded=True, memory_admitted=False)
    snapshots = iter(((unloaded,), (refreshed_but_denied,)))
    loader = FakeLoader(loaded=True)
    target = PlacementTarget(
        id="p",
        node_id="n",
        model_id="physical/p",
        resident=False,
        memory_gb=1,
        idle_unload_seconds=0,
        last_used_monotonic=0,
        rollback_reference="placement:p",
    )
    orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: next(snapshots),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        loader=loader,
        load_target=lambda _placement: target,
    )

    result = await orchestrator.chat(_route_request(), _chat(), deadline=10)

    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.NO_CANDIDATE
    assert adapter.chat_requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rejection", "placement_id"),
    [
        (rejection, placement_id)
        for rejection in (
            RejectionCode.UNAVAILABLE,
            RejectionCode.AUTHORIZATION,
            RejectionCode.STALE,
            RejectionCode.LOCAL_SECURITY,
            RejectionCode.MEMORY,
            RejectionCode.CAPABILITY,
            RejectionCode.NO_CAPACITY,
        )
        for placement_id in ("placement.safe-1", "node/private/model")
    ],
)
async def test_prepare_failure_preserves_ordered_typed_rejection_without_adapter_call(
    rejection: RejectionCode,
    placement_id: str,
) -> None:
    adapter = FakeAdapter(chats=[_success()])
    unloaded = _snapshot(placement_id, "b", "n", loaded=False)
    refreshed_updates: dict[str, object] = {"loaded": True}
    if rejection is RejectionCode.MEMORY:
        refreshed_updates["memory_admitted"] = False
    elif rejection is RejectionCode.CAPABILITY:
        refreshed_updates["capabilities"] = frozenset({"chat"})
    refreshed = _snapshot(placement_id, "b", "n", **refreshed_updates)
    snapshots = iter(((unloaded,), (refreshed,)))
    target = PlacementTarget(
        id=placement_id,
        node_id="n",
        model_id="physical/p",
        resident=False,
        memory_gb=1,
        idle_unload_seconds=0,
        last_used_monotonic=0,
        rollback_reference="placement:p",
    )
    orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: next(snapshots),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        loader=RejectingLoader(rejection),
        load_target=lambda _placement: target,
    )

    result = await orchestrator.chat(
        _route_request(required_capabilities=frozenset({"chat", "vision"})),
        _chat(),
        deadline=10,
    )

    assert result.error is not None
    assert result.error.code in {ExecutionErrorCode.NO_CANDIDATE, ExecutionErrorCode.NO_CAPACITY}
    safe_id = (
        placement_id
        if "/" not in placement_id
        else f"opaque:{hashlib.sha256(placement_id.encode()).hexdigest()[:12]}"
    )
    assert result.error.prepare_rejections == ((safe_id, rejection),)
    assert placement_id == safe_id or placement_id not in repr(result.error)
    assert adapter.chat_requests == []

    stream_snapshots = iter(((unloaded,), (refreshed,)))
    stream_orchestrator = DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: next(stream_snapshots),
        registry=AdapterRegistry((AdapterBinding("b", adapter),)),
        capacity=CapacityCoordinator(global_limit=1, per_node=1, per_backend=1),
        loader=RejectingLoader(rejection),
        load_target=lambda _placement: target,
    )
    stream = [
        event
        async for event in stream_orchestrator.stream_chat(
            _route_request(required_capabilities=frozenset({"chat", "vision"})),
            _chat(),
            deadline=10,
        )
    ]

    assert len(stream) == 1
    assert stream[0].kind is StreamEventKind.ERROR
    assert [
        (item.placement_id, item.reason.value) for item in stream[0].prepare_rejections
    ] == [(safe_id, rejection.value)]
    assert placement_id == safe_id or placement_id not in repr(stream[0])
    assert adapter.stream_requests == []


@pytest.mark.asyncio
async def test_prepare_rejection_is_consistent_for_embedding_and_stream_without_adapter_call(
) -> None:
    adapter = FakeAdapter(chats=[_success()])
    unloaded = _snapshot("p", "b", "n", loaded=False)
    orchestrator = _orchestrator((unloaded,), (AdapterBinding("b", adapter),))

    embedding = await orchestrator.embed(
        _route_request(required_capabilities=frozenset({"embedding"})),
        EmbeddingRequest(request_id="req", model="public/model", input="one"),
        deadline=10,
    )
    stream = [
        event
        async for event in orchestrator.stream_chat(_route_request(), _chat(), deadline=10)
    ]

    assert embedding.error is not None
    assert embedding.error.prepare_rejections == (("p", RejectionCode.UNAVAILABLE),)
    assert len(stream) == 1
    assert stream[0].kind is StreamEventKind.ERROR
    assert stream[0].error is not None
    assert stream[0].error.message == RejectionCode.UNAVAILABLE.value
    assert [
        (item.placement_id, item.reason.value) for item in stream[0].prepare_rejections
    ] == [("p", RejectionCode.UNAVAILABLE.value)]
    assert adapter.embedding_requests == []
    assert adapter.chat_requests == []
    assert adapter.stream_requests == []


@pytest.mark.asyncio
async def test_embedding_timeout_uses_next_candidate_when_budget_remains() -> None:
    first = FakeAdapter(embeddings=[TimeoutError()])
    second = FakeAdapter(
        embeddings=[
            EmbeddingResult(
                request_id="req",
                status=OperationStatus.SUCCEEDED,
                embeddings=((1.0, 2.0),),
            )
        ]
    )
    placements = (_snapshot("a", "b1", "n1"), _snapshot("b", "b2", "n2"))
    result = await _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    ).embed(
        _route_request(required_capabilities=frozenset({"embedding"})),
        EmbeddingRequest(request_id="req", model="public/model", input="one"),
        deadline=10,
    )

    assert result.error is None
    assert result.attempted_placements == ("a", "b")


@pytest.mark.asyncio
async def test_retryable_flag_cannot_override_non_failover_error_code() -> None:
    first = FakeAdapter(chats=[_failure(AdapterErrorCode.INVALID_REQUEST, retryable=True)])
    second = FakeAdapter(chats=[_success()])
    placements = (_snapshot("a", "b1", "n1"), _snapshot("b", "b2", "n2"))
    result = await _orchestrator(
        placements,
        (AdapterBinding("b1", first), AdapterBinding("b2", second)),
    ).chat(_route_request(), _chat(), deadline=10)

    assert not result.success
    assert result.attempted_placements == ("a",)
    assert second.chat_requests == []


@pytest.mark.asyncio
async def test_execution_rejects_duplicate_placement_ids_without_calling_adapter() -> None:
    adapter = FakeAdapter(chats=[_success()])
    duplicates = (_snapshot("p", "b", "n"), _snapshot("p", "b", "n"))
    result = await _orchestrator(duplicates, (AdapterBinding("b", adapter),)).chat(
        _route_request(), _chat(), deadline=10
    )

    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.INVALID_BINDING
    assert adapter.chat_requests == []


class RaisingReranker:
    async def rerank(self, request: RerankRequest) -> RerankResult:
        raise ValueError("query=do-not-leak")


@pytest.mark.asyncio
async def test_reranker_exception_is_typed_and_sanitized() -> None:
    result = await DataPlaneOrchestrator.rerank(
        RaisingReranker(),
        RerankRequest(request_id="r", query="q", documents=("a",)),
    )
    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.BACKEND_FAILURE
    assert "do-not-leak" not in repr(result)
