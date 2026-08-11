"""Prove that the shared contract accepts a backend with no HTTP surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from omlxc.domain.protocols import (
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
    StreamEventKind,
    StreamPhase,
    TokenUsage,
    TuneRequest,
    TuneResult,
)

from .backend_adapter_contract import (
    BackendAdapterContract,
    ContractHarness,
    ContractScenario,
)


def _error(code: AdapterErrorCode, *, emitted: bool = False) -> AdapterError:
    return AdapterError(
        code=code,
        message="synthetic adapter outcome",
        emitted_content=emitted,
        phase=StreamPhase.AFTER_CONTENT if emitted else StreamPhase.BEFORE_CONTENT,
    )


class FakeBackendAdapter:
    """Behavioral fake deliberately exposing no transport or route details."""

    def __init__(self, scenario: ContractScenario) -> None:
        self._scenario = scenario

    async def discover(self) -> CapabilitySnapshot:
        reachable = True
        compatible = self._scenario is not ContractScenario.HEALTH_ONLY
        model_available = compatible
        generation_ready = self._scenario is ContractScenario.GENERATION_READY
        return CapabilitySnapshot(
            backend_id="fake",
            reachable=reachable,
            compatible=compatible,
            model_available=model_available,
            generation_ready=generation_ready,
            observed_at=datetime.now(UTC),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        loaded = self._scenario is ContractScenario.MODEL_ALREADY_LOADED
        return (
            ModelRuntime(
                id="model-a",
                state=(ModelRuntimeState.LOADED if loaded else ModelRuntimeState.AVAILABLE),
                loaded=loaded,
            ),
        )

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.UNCHANGED,
            changed=False,
            idempotency_key=idempotency_key,
        )

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.UNSUPPORTED,
            changed=False,
            idempotency_key=idempotency_key,
            error=_error(AdapterErrorCode.UNSUPPORTED),
        )

    async def tune(self, request: TuneRequest) -> TuneResult:
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=OperationStatus.UNSUPPORTED,
            idempotency_key=request.idempotency_key,
            error=_error(AdapterErrorCode.UNSUPPORTED),
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(request_id=request.request_id, success=True, content="visible")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.UNSUPPORTED,
            error=_error(AdapterErrorCode.UNSUPPORTED),
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        if self._scenario in {
            ContractScenario.STREAM_SUCCESS,
            ContractScenario.STREAM_BREAK_AFTER_CONTENT,
        }:
            yield StreamEvent(
                kind=StreamEventKind.CONTENT,
                request_id=request.request_id,
                content="hello",
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
            )
        if self._scenario is ContractScenario.STREAM_SUCCESS:
            yield StreamEvent(
                kind=StreamEventKind.USAGE,
                request_id=request.request_id,
                usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
            )
            yield StreamEvent(
                kind=StreamEventKind.DONE,
                request_id=request.request_id,
                emitted_content=True,
                phase=StreamPhase.COMPLETE,
            )
            return

        code = (
            AdapterErrorCode.BAD_RESPONSE
            if self._scenario in {ContractScenario.STREAM_EMPTY, ContractScenario.STREAM_NON_JSON}
            else AdapterErrorCode.STREAM_INTERRUPTED
        )
        emitted = self._scenario is ContractScenario.STREAM_BREAK_AFTER_CONTENT
        error = _error(code, emitted=emitted)
        yield StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request.request_id,
            error=error,
            emitted_content=emitted,
            phase=error.phase,
        )


class TestFakeBackendContract(BackendAdapterContract):
    __test__ = True

    @staticmethod
    def make_harness(scenario: ContractScenario) -> ContractHarness:
        adapter = FakeBackendAdapter(scenario)
        assert isinstance(adapter, BackendAdapter)
        return ContractHarness(adapter=adapter)
