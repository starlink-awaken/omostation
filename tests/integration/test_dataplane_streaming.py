from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from omlxc.dataplane import (
    AdapterBinding,
    AdapterRegistry,
    CapacityCoordinator,
    DataPlaneOrchestrator,
)
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    ChatMessage,
    ChatRequest,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TokenUsage,
)
from omlxc.scheduler import PlacementSnapshot, RoutePlanner, default_policies


class ClosingStream:
    def __init__(self, events: tuple[StreamEvent, ...]) -> None:
        self._events = iter(events)
        self.closed = False

    def __aiter__(self) -> ClosingStream:
        return self

    async def __anext__(self) -> StreamEvent:
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        self.closed = True


class RaisingStream(ClosingStream):
    def __init__(self, events: tuple[StreamEvent, ...], error: BaseException | None = None) -> None:
        super().__init__(events)
        self._error = error or TimeoutError()

    async def __anext__(self) -> StreamEvent:
        try:
            return await super().__anext__()
        except StopAsyncIteration:
            raise self._error from None


class StreamAdapter:
    def __init__(self, stream: ClosingStream) -> None:
        self.stream = stream
        self.requests: list[ChatRequest] = []

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.requests.append(request)
        return self.stream


def _event(
    kind: StreamEventKind,
    *,
    content: str = "",
    retryable: bool = False,
    emitted: bool = False,
) -> StreamEvent:
    phase = StreamPhase.AFTER_CONTENT if emitted else StreamPhase.BEFORE_CONTENT
    error = None
    if kind is StreamEventKind.ERROR:
        error = AdapterError(
            code=AdapterErrorCode.STREAM_INTERRUPTED,
            message="safe",
            retryable=retryable,
            emitted_content=emitted,
            phase=phase,
        )
    if kind is StreamEventKind.DONE:
        phase = StreamPhase.COMPLETE
    return StreamEvent(
        kind=kind,
        request_id="req",
        content=content,
        error=error,
        emitted_content=emitted,
        phase=phase,
    )


def _usage() -> StreamEvent:
    return StreamEvent(
        kind=StreamEventKind.USAGE,
        request_id="req",
        usage=TokenUsage(total_tokens=1),
        emitted_content=False,
        phase=StreamPhase.BEFORE_CONTENT,
    )


def _snapshot(pid: str, backend: str, affinity: float) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=pid,
        model_id="public/model",
        backend_id=backend,
        backend_model_id=f"physical/{pid}",
        node_id=f"node/{pid}",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat", "streaming"}),
        context_limit=8192,
        memory_admitted=True,
        loaded=True,
        ttft_ms=10,
        throughput_tps=50,
        queue_depth=0,
        error_rate=0,
        network_cost_ms=1,
        affinity=affinity,
        available_concurrency=1,
        local=True,
        security_allowed=True,
    )


def _orchestrator(
    first: StreamAdapter, second: StreamAdapter, clock: object | None = None
) -> DataPlaneOrchestrator:
    return DataPlaneOrchestrator(
        planner=RoutePlanner(default_policies()),
        snapshot_provider=lambda: (_snapshot("a", "b1", 1), _snapshot("b", "b2", 0)),
        registry=AdapterRegistry((AdapterBinding("b1", first), AdapterBinding("b2", second))),
        capacity=CapacityCoordinator(global_limit=2, per_node=1, per_backend=1),
        monotonic=clock if callable(clock) else None,
    )


def _route() -> RouteRequest:
    return RouteRequest(
        request_id="req",
        model_id="public/model",
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat", "streaming"}),
        context_tokens=4,
    )


def _chat() -> ChatRequest:
    return ChatRequest(
        request_id="req",
        model="public/model",
        messages=(ChatMessage(role="user", content="secret"),),
    )


@pytest.mark.asyncio
async def test_pre_content_error_fails_over_and_closes_iterators_with_unique_done() -> None:
    first_stream = ClosingStream((_event(StreamEventKind.ERROR, retryable=True),))
    second_stream = ClosingStream(
        (
            _event(StreamEventKind.CONTENT, content="ok", emitted=True),
            _event(StreamEventKind.DONE),
        )
    )
    events = [
        event
        async for event in _orchestrator(
            StreamAdapter(first_stream), StreamAdapter(second_stream)
        ).stream_chat(_route(), _chat(), deadline=10)
    ]

    assert [event.kind for event in events] == [StreamEventKind.CONTENT, StreamEventKind.DONE]
    assert first_stream.closed and second_stream.closed


@pytest.mark.asyncio
async def test_post_content_error_is_returned_without_replay() -> None:
    first_stream = ClosingStream(
        (
            _event(StreamEventKind.CONTENT, content="partial", emitted=True),
            _event(StreamEventKind.ERROR, retryable=True, emitted=True),
        )
    )
    second = StreamAdapter(
        ClosingStream((_event(StreamEventKind.CONTENT, content="replay", emitted=True),))
    )
    events = [
        event
        async for event in _orchestrator(StreamAdapter(first_stream), second).stream_chat(
            _route(), _chat(), deadline=10
        )
    ]

    assert [event.content for event in events if event.kind is StreamEventKind.CONTENT] == [
        "partial"
    ]
    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].emitted_content
    assert events[-1].phase is StreamPhase.AFTER_CONTENT
    assert second.requests == []


@pytest.mark.asyncio
async def test_deadline_exhaustion_does_not_start_next_candidate() -> None:
    times = iter((0.0, 0.0, 11.0, 11.0))
    first = StreamAdapter(ClosingStream((_event(StreamEventKind.ERROR, retryable=True),)))
    second = StreamAdapter(ClosingStream((_event(StreamEventKind.DONE),)))
    events = [
        event
        async for event in _orchestrator(first, second, lambda: next(times)).stream_chat(
            _route(), _chat(), deadline=10
        )
    ]

    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].error is not None
    assert events[-1].error.code is AdapterErrorCode.TIMEOUT
    assert second.requests == []


@pytest.mark.asyncio
async def test_transport_exception_before_content_fails_over_without_escaping() -> None:
    first_stream = RaisingStream(())
    second_stream = ClosingStream((_event(StreamEventKind.DONE),))
    events = [
        event
        async for event in _orchestrator(
            StreamAdapter(first_stream), StreamAdapter(second_stream)
        ).stream_chat(_route(), _chat(), deadline=10)
    ]

    assert [event.kind for event in events] == [StreamEventKind.DONE]
    assert first_stream.closed and second_stream.closed


@pytest.mark.asyncio
async def test_usage_and_done_are_emitted_at_most_once() -> None:
    stream = ClosingStream((_usage(), _usage(), _event(StreamEventKind.DONE)))
    events = [
        event
        async for event in _orchestrator(
            StreamAdapter(stream), StreamAdapter(ClosingStream(()))
        ).stream_chat(_route(), _chat(), deadline=10)
    ]

    assert [event.kind for event in events] == [
        StreamEventKind.USAGE,
        StreamEventKind.DONE,
    ]


@pytest.mark.asyncio
async def test_unexpected_exception_after_content_becomes_sanitized_no_replay_error() -> None:
    first_stream = RaisingStream(
        (_event(StreamEventKind.CONTENT, content="partial", emitted=True),),
        ValueError("prompt=do-not-leak"),
    )
    second = StreamAdapter(ClosingStream((_event(StreamEventKind.DONE),)))
    events = [
        event
        async for event in _orchestrator(StreamAdapter(first_stream), second).stream_chat(
            _route(), _chat(), deadline=10
        )
    ]

    assert [event.kind for event in events] == [
        StreamEventKind.CONTENT,
        StreamEventKind.ERROR,
    ]
    assert events[-1].emitted_content
    assert "do-not-leak" not in repr(events[-1])
    assert second.requests == []
