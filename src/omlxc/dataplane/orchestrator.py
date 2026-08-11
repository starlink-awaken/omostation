"""Deadline-bounded local inference orchestration and replay-safe failover."""

from __future__ import annotations

import math
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Protocol

import anyio

from omlxc.autonomy import PlacementOperationOutcome, PlacementTarget
from omlxc.domain import RouteDecision, RouteRequest
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
)
from omlxc.scheduler import (
    PlacementSnapshot,
    RejectionCode,
    RouteFailure,
    RouteFailureCode,
    RoutePlanner,
)

from .capacity import CapacityCoordinator
from .models import (
    ChatExecution,
    EmbeddingExecution,
    ExecutionError,
    ExecutionErrorCode,
    RankedItem,
    Reranker,
    RerankExecution,
    RerankRequest,
    validate_vectors,
)
from .registry import AdapterRegistry
from .telemetry import TelemetrySink

SnapshotProvider = Callable[[], tuple[PlacementSnapshot, ...]]


class PlacementLoader(Protocol):
    async def ensure_loaded(self, target: PlacementTarget) -> PlacementOperationOutcome: ...


class DataPlaneOrchestrator:
    def __init__(
        self,
        *,
        planner: RoutePlanner,
        snapshot_provider: SnapshotProvider,
        registry: AdapterRegistry,
        capacity: CapacityCoordinator,
        monotonic: Callable[[], float] | None = None,
        loader: PlacementLoader | None = None,
        load_target: Callable[[PlacementSnapshot], PlacementTarget] | None = None,
        telemetry: TelemetrySink | None = None,
        telemetry_error_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._planner = planner
        self._snapshot_provider = snapshot_provider
        self._registry = registry
        self._capacity = capacity
        self._monotonic = monotonic or time.monotonic
        self._loader = loader
        self._load_target = load_target
        self._telemetry = telemetry
        self._telemetry_error_sink = telemetry_error_sink
        self._telemetry_failure_count = 0

    @property
    def telemetry_failure_count(self) -> int:
        return self._telemetry_failure_count

    async def chat(
        self, route_request: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        if self._telemetry is None:
            return await self._chat_unobserved(route_request, request, deadline=deadline)
        started = self._monotonic()
        success = False
        try:
            result = await self._chat_unobserved(route_request, request, deadline=deadline)
            success = result.success
            return result
        finally:
            self._record_metric(request.request_id, started, success)

    async def _chat_unobserved(
        self, route_request: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        snapshots = self._snapshot_provider()
        plan = self._planner.plan(route_request, snapshots)
        await self._record_plan(plan)
        failure = self._plan_error(plan)
        if failure is not None:
            return ChatExecution(request.request_id, request.model, False, None, (), error=failure)
        assert isinstance(plan, RouteDecision)
        if plan.thinking_authorized:
            return ChatExecution(
                request.request_id,
                request.model,
                False,
                None,
                (),
                error=ExecutionError(
                    ExecutionErrorCode.UNSUPPORTED,
                    False,
                    reason="adapter_contract_has_no_safe_reasoning_field",
                ),
            )
        end = self._deadline(deadline)
        placements = self._by_id(snapshots)
        attempted: list[str] = []
        preparation_rejections: list[RejectionCode] = []
        for placement_id in plan.fallback_chain:
            attempted.append(placement_id)
            placement, rejection = await self._prepare(route_request, placements[placement_id], end)
            if placement is None:
                if rejection is not None:
                    preparation_rejections.append(rejection)
                continue
            try:
                result = await self._chat_once(placement, request, end)
            except TimeoutError:
                if self._remaining(end) > 0:
                    continue
                return ChatExecution(
                    request.request_id,
                    request.model,
                    False,
                    None,
                    tuple(attempted),
                    error=self._timeout_error(),
                )
            except Exception:
                return ChatExecution(
                    request.request_id,
                    request.model,
                    False,
                    placement_id,
                    tuple(attempted),
                    error=ExecutionError(
                        ExecutionErrorCode.BACKEND_FAILURE,
                        False,
                        reason="backend_call_failed",
                    ),
                )
            if result.success:
                return ChatExecution(
                    request.request_id,
                    request.model,
                    True,
                    placement_id,
                    tuple(attempted),
                    result=result,
                )
            assert result.error is not None
            if not self._can_failover(result.error):
                return ChatExecution(
                    request.request_id,
                    request.model,
                    False,
                    placement_id,
                    tuple(attempted),
                    result=result,
                    error=ExecutionError(
                        ExecutionErrorCode.BACKEND_FAILURE,
                        False,
                        reason=result.error.code.value,
                    ),
                )
            if self._remaining(end) <= 0:
                return ChatExecution(
                    request.request_id,
                    request.model,
                    False,
                    placement_id,
                    tuple(attempted),
                    error=self._timeout_error(),
                )
        return ChatExecution(
            request.request_id,
            request.model,
            False,
            attempted[-1] if attempted else None,
            tuple(attempted),
            error=ExecutionError(
                self._preparation_error(preparation_rejections)
                if preparation_rejections
                else ExecutionErrorCode.BACKEND_FAILURE,
                False,
            ),
        )

    async def _chat_once(
        self, placement: PlacementSnapshot, request: ChatRequest, deadline: float
    ) -> ChatResult:
        adapter = self._registry.resolve(placement)
        backend_request = request.model_copy(update={"model": placement.backend_model_id})
        async with self._capacity.acquire(placement, deadline=deadline, monotonic=self._monotonic):
            remaining = self._remaining(deadline)
            if remaining <= 0:
                raise TimeoutError
            with anyio.fail_after(remaining):
                return await adapter.chat(backend_request)

    async def embed(
        self, route_request: RouteRequest, request: EmbeddingRequest, *, deadline: float
    ) -> EmbeddingExecution:
        if self._telemetry is None:
            return await self._embed_unobserved(route_request, request, deadline=deadline)
        started = self._monotonic()
        success = False
        try:
            result = await self._embed_unobserved(route_request, request, deadline=deadline)
            success = result.error is None
            return result
        finally:
            self._record_metric(request.request_id, started, success)

    async def _embed_unobserved(
        self, route_request: RouteRequest, request: EmbeddingRequest, *, deadline: float
    ) -> EmbeddingExecution:
        snapshots = self._snapshot_provider()
        plan = self._planner.plan(route_request, snapshots)
        await self._record_plan(plan)
        failure = self._plan_error(plan)
        if failure is not None:
            return EmbeddingExecution(request.request_id, request.model, None, (), error=failure)
        assert isinstance(plan, RouteDecision)
        end = self._deadline(deadline)
        placements = self._by_id(snapshots)
        attempted: list[str] = []
        preparation_rejections: list[RejectionCode] = []
        expected = 1 if isinstance(request.input, str) else len(request.input)
        for placement_id in plan.fallback_chain:
            attempted.append(placement_id)
            placement, rejection = await self._prepare(route_request, placements[placement_id], end)
            if placement is None:
                if rejection is not None:
                    preparation_rejections.append(rejection)
                continue
            adapter = self._registry.resolve(placement)
            backend_request = request.model_copy(update={"model": placement.backend_model_id})
            try:
                async with self._capacity.acquire(
                    placement, deadline=end, monotonic=self._monotonic
                ):
                    remaining = self._remaining(end)
                    if remaining <= 0:
                        raise TimeoutError
                    with anyio.fail_after(remaining):
                        result = await adapter.embed(backend_request)
            except TimeoutError:
                if self._remaining(end) > 0:
                    continue
                return EmbeddingExecution(
                    request.request_id,
                    request.model,
                    placement_id,
                    tuple(attempted),
                    error=self._timeout_error(),
                )
            except Exception:
                return EmbeddingExecution(
                    request.request_id,
                    request.model,
                    placement_id,
                    tuple(attempted),
                    error=ExecutionError(
                        ExecutionErrorCode.BACKEND_FAILURE,
                        False,
                        reason="backend_call_failed",
                    ),
                )
            if result.status is OperationStatus.SUCCEEDED:
                if not validate_vectors(result.embeddings, expected_count=expected):
                    return EmbeddingExecution(
                        request.request_id,
                        request.model,
                        placement_id,
                        tuple(attempted),
                        error=ExecutionError(ExecutionErrorCode.BAD_RESPONSE, False),
                    )
                return EmbeddingExecution(
                    request.request_id,
                    request.model,
                    placement_id,
                    tuple(attempted),
                    embeddings=result.embeddings,
                )
            assert result.error is not None
            if not self._can_failover(result.error):
                break
        return EmbeddingExecution(
            request.request_id,
            request.model,
            attempted[-1] if attempted else None,
            tuple(attempted),
            error=ExecutionError(
                self._preparation_error(preparation_rejections)
                if preparation_rejections and len(preparation_rejections) == len(attempted)
                else ExecutionErrorCode.BACKEND_FAILURE,
                False,
            ),
        )

    async def stream_chat(
        self, route_request: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> AsyncGenerator[StreamEvent]:
        if self._telemetry is None:
            async for event in self._stream_chat_unobserved(
                route_request, request, deadline=deadline
            ):
                yield event
            return
        started = self._monotonic()
        success = False
        try:
            async for event in self._stream_chat_unobserved(
                route_request, request, deadline=deadline
            ):
                if event.kind is StreamEventKind.DONE:
                    success = True
                yield event
        finally:
            self._record_metric(request.request_id, started, success)

    async def _stream_chat_unobserved(
        self, route_request: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> AsyncGenerator[StreamEvent]:
        snapshots = self._snapshot_provider()
        plan = self._planner.plan(route_request, snapshots)
        await self._record_plan(plan)
        failure = self._plan_error(plan)
        if failure is not None:
            yield self._error_event(request.request_id, failure)
            return
        assert isinstance(plan, RouteDecision)
        if plan.thinking_authorized:
            yield self._error_event(
                request.request_id,
                ExecutionError(ExecutionErrorCode.UNSUPPORTED, False),
            )
            return
        end = self._deadline(deadline)
        placements = self._by_id(snapshots)
        emitted_content = False
        emitted_usage = False
        for placement_id in plan.fallback_chain:
            if self._remaining(end) <= 0:
                yield self._timeout_stream_event(request.request_id, emitted_content)
                return
            placement = placements[placement_id]
            prepared, _rejection = await self._prepare(route_request, placement, end)
            if prepared is None:
                continue
            placement = prepared
            adapter = self._registry.resolve(placement)
            backend_request = request.model_copy(update={"model": placement.backend_model_id})
            retry = False
            iterator: AsyncIterator[StreamEvent] | None = None
            try:
                async with self._capacity.acquire(
                    placement, deadline=end, monotonic=self._monotonic
                ):
                    iterator = adapter.stream_chat(backend_request)
                    async for event in iterator:
                        if self._remaining(end) <= 0:
                            yield self._timeout_stream_event(request.request_id, emitted_content)
                            return
                        if event.kind is StreamEventKind.ERROR:
                            assert event.error is not None
                            if not emitted_content and self._can_failover(event.error):
                                retry = True
                                break
                            yield event.model_copy(
                                update={
                                    "placement_id": placement.placement_id,
                                    "backend_id": placement.backend_id,
                                }
                            )
                            return
                        if event.kind is StreamEventKind.CONTENT:
                            emitted_content = True
                            yield event.model_copy(
                                update={
                                    "placement_id": placement.placement_id,
                                    "backend_id": placement.backend_id,
                                }
                            )
                        elif event.kind is StreamEventKind.USAGE:
                            if not emitted_usage:
                                emitted_usage = True
                                yield event.model_copy(
                                    update={
                                        "placement_id": placement.placement_id,
                                        "backend_id": placement.backend_id,
                                    }
                                )
                        elif event.kind is StreamEventKind.DONE:
                            yield event.model_copy(
                                update={
                                    "placement_id": placement.placement_id,
                                    "backend_id": placement.backend_id,
                                }
                            )
                            return
                    else:
                        if emitted_content:
                            yield self._interrupted_event(request.request_id, True)
                            return
                        retry = True
            except TimeoutError:
                if not emitted_content and self._remaining(end) > 0:
                    retry = True
                else:
                    yield self._timeout_stream_event(request.request_id, emitted_content)
                    return
            except Exception:
                yield self._unexpected_stream_event(request.request_id, emitted_content)
                return
            finally:
                if iterator is not None:
                    close = getattr(iterator, "aclose", None)
                    if close is not None:
                        await close()
            if not retry:
                return
        yield self._interrupted_event(request.request_id, emitted_content)

    @staticmethod
    async def rerank(reranker: Reranker, request: RerankRequest) -> RerankExecution:
        try:
            result = await reranker.rerank(request)
        except Exception:
            return RerankExecution(
                request.request_id,
                (),
                ExecutionError(
                    ExecutionErrorCode.BACKEND_FAILURE,
                    False,
                    reason="reranker_call_failed",
                ),
            )
        if len(result.scores) != len(request.documents) or any(
            not math.isfinite(score) for score in result.scores
        ):
            return RerankExecution(
                request.request_id,
                (),
                ExecutionError(ExecutionErrorCode.BAD_RESPONSE, False),
            )
        items = tuple(
            RankedItem(index, score)
            for index, score in sorted(
                enumerate(result.scores), key=lambda item: (-item[1], item[0])
            )
        )
        return RerankExecution(request.request_id, items)

    def _deadline(self, budget: float) -> float:
        if not math.isfinite(budget) or budget <= 0:
            return self._monotonic()
        return self._monotonic() + budget

    def _remaining(self, deadline: float) -> float:
        return deadline - self._monotonic()

    async def _prepare(
        self,
        request: RouteRequest,
        placement: PlacementSnapshot,
        deadline: float,
    ) -> tuple[PlacementSnapshot | None, RejectionCode | None]:
        if placement.loaded:
            return placement, None
        if self._loader is None or self._load_target is None:
            return None, RejectionCode.HEALTH
        remaining = self._remaining(deadline)
        if remaining <= 0:
            return None, RejectionCode.NO_CAPACITY
        try:
            with anyio.fail_after(remaining):
                outcome = await self._loader.ensure_loaded(self._load_target(placement))
        except TimeoutError:
            return None, RejectionCode.NO_CAPACITY
        if not outcome.authorized or not outcome.actual_loaded:
            return None, RejectionCode.HEALTH
        try:
            refreshed = self._by_id(self._snapshot_provider()).get(placement.placement_id)
        except LookupError:
            return None, RejectionCode.LOCAL_SECURITY
        if refreshed is None or not refreshed.loaded:
            return None, RejectionCode.HEALTH
        immutable_binding = (
            refreshed.model_id,
            refreshed.backend_id,
            refreshed.backend_model_id,
            refreshed.node_id,
        )
        expected_binding = (
            placement.model_id,
            placement.backend_id,
            placement.backend_model_id,
            placement.node_id,
        )
        if immutable_binding != expected_binding:
            return None, RejectionCode.LOCAL_SECURITY
        rejection = self._planner.evaluate(request, refreshed)
        return (refreshed, None) if rejection is None else (None, rejection)

    @staticmethod
    def _by_id(placements: tuple[PlacementSnapshot, ...]) -> dict[str, PlacementSnapshot]:
        result: dict[str, PlacementSnapshot] = {}
        for placement in placements:
            if placement.placement_id in result:
                raise LookupError("duplicate placement ID")
            result[placement.placement_id] = placement
        return result

    @staticmethod
    def _plan_error(plan: RouteDecision | RouteFailure) -> ExecutionError | None:
        if isinstance(plan, RouteDecision):
            return None
        code = (
            ExecutionErrorCode.NO_CAPACITY
            if plan.code is RouteFailureCode.NO_CAPACITY
            else ExecutionErrorCode.INVALID_BINDING
            if plan.code is RouteFailureCode.INVALID_SNAPSHOT
            else ExecutionErrorCode.NO_CANDIDATE
        )
        return ExecutionError(code, False, reason=plan.code.value)

    @staticmethod
    def _timeout_error() -> ExecutionError:
        return ExecutionError(ExecutionErrorCode.TIMEOUT, False, reason="deadline_exhausted")

    @staticmethod
    def _can_failover(error: AdapterError) -> bool:
        if not error.retryable or error.emitted_content:
            return False
        if error.code in {
            AdapterErrorCode.UNREACHABLE,
            AdapterErrorCode.TIMEOUT,
            AdapterErrorCode.STREAM_INTERRUPTED,
            AdapterErrorCode.PARTIAL_FAILURE,
        }:
            return True
        return error.code is AdapterErrorCode.BAD_RESPONSE and (
            error.http_status is None or 500 <= error.http_status <= 599
        )

    @staticmethod
    def _preparation_error(rejections: list[RejectionCode]) -> ExecutionErrorCode:
        return (
            ExecutionErrorCode.NO_CAPACITY
            if rejections
            and all(rejection is RejectionCode.NO_CAPACITY for rejection in rejections)
            else ExecutionErrorCode.NO_CANDIDATE
        )

    async def _record_plan(self, plan: RouteDecision | RouteFailure) -> None:
        if self._telemetry is None:
            return
        try:
            await self._telemetry.record_route(plan)
        except Exception:
            self._telemetry_failed()

    def _record_metric(self, request_id: str, started: float, success: bool) -> None:
        if self._telemetry is None:
            return
        elapsed_ms = max(0.0, (self._monotonic() - started) * 1_000.0)
        try:
            if not self._telemetry.record_metric(
                request_id=request_id,
                latency_ms=elapsed_ms,
                success=success,
            ):
                self._telemetry_failed()
        except Exception:
            self._telemetry_failed()

    def _telemetry_failed(self) -> None:
        self._telemetry_failure_count += 1
        if self._telemetry_error_sink is None:
            return
        try:
            self._telemetry_error_sink("telemetry_write_failed")
        except Exception:
            return

    @staticmethod
    def _error_event(request_id: str, error: ExecutionError) -> StreamEvent:
        adapter_code = (
            AdapterErrorCode.TIMEOUT
            if error.code is ExecutionErrorCode.TIMEOUT
            else AdapterErrorCode.UNSUPPORTED
            if error.code is ExecutionErrorCode.UNSUPPORTED
            else AdapterErrorCode.MODEL_UNAVAILABLE
        )
        adapter_error = AdapterError(
            code=adapter_code,
            message=error.reason or error.code.value,
            retryable=error.retryable,
            emitted_content=error.emitted_content,
            phase=error.phase,
        )
        return StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request_id,
            error=adapter_error,
            emitted_content=error.emitted_content,
            phase=error.phase,
        )

    @classmethod
    def _timeout_stream_event(cls, request_id: str, emitted: bool) -> StreamEvent:
        phase = StreamPhase.AFTER_CONTENT if emitted else StreamPhase.BEFORE_CONTENT
        return cls._error_event(
            request_id,
            ExecutionError(ExecutionErrorCode.TIMEOUT, False, phase, emitted),
        )

    @staticmethod
    def _interrupted_event(request_id: str, emitted: bool) -> StreamEvent:
        phase = StreamPhase.AFTER_CONTENT if emitted else StreamPhase.BEFORE_CONTENT
        error = AdapterError(
            code=AdapterErrorCode.STREAM_INTERRUPTED,
            message="backend stream interrupted",
            retryable=not emitted,
            emitted_content=emitted,
            phase=phase,
        )
        return StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request_id,
            error=error,
            emitted_content=emitted,
            phase=phase,
        )

    @staticmethod
    def _unexpected_stream_event(request_id: str, emitted: bool) -> StreamEvent:
        phase = StreamPhase.AFTER_CONTENT if emitted else StreamPhase.BEFORE_CONTENT
        error = AdapterError(
            code=AdapterErrorCode.BAD_RESPONSE,
            message="backend stream failed",
            retryable=False,
            emitted_content=emitted,
            phase=phase,
        )
        return StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request_id,
            error=error,
            emitted_content=emitted,
            phase=phase,
        )
