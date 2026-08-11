"""Backend-neutral contract suite reusable by every HTTP adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx
import pytest

from omlxc.domain.protocols import (
    AdapterErrorCode,
    BackendAdapterV1,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    OperationStatus,
    StreamEventKind,
    StreamPhase,
)


class ContractScenario(StrEnum):
    HEALTH_ONLY = "health_only"
    MODEL_AVAILABLE = "model_available"
    GENERATION_READY = "generation_ready"
    REASONING_RESPONSE = "reasoning_response"
    EMBEDDING_UNSUPPORTED = "embedding_unsupported"
    MODEL_ALREADY_LOADED = "model_already_loaded"
    STREAM_SUCCESS = "stream_success"
    STREAM_EMPTY = "stream_empty"
    STREAM_NON_JSON = "stream_non_json"
    STREAM_BREAK_BEFORE_CONTENT = "stream_break_before_content"
    STREAM_BREAK_AFTER_CONTENT = "stream_break_after_content"


@dataclass
class ContractHarness:
    adapter: BackendAdapterV1
    requests: list[httpx.Request]


class HarnessFactory(Protocol):
    def __call__(self, scenario: ContractScenario) -> ContractHarness: ...


class BackendAdapterContract:
    """Behavioral tests with no backend-specific route assumptions."""

    __test__ = False
    make_harness: Callable[[ContractScenario], ContractHarness]

    @pytest.mark.asyncio
    async def test_health_endpoint_alone_never_means_generation_ready(self) -> None:
        harness = self.make_harness(ContractScenario.HEALTH_ONLY)

        snapshot = await harness.adapter.discover()

        assert snapshot.reachable is True
        assert snapshot.compatible is False
        assert snapshot.model_available is False
        assert snapshot.generation_ready is False

    @pytest.mark.asyncio
    async def test_model_inventory_alone_never_means_generation_ready(self) -> None:
        harness = self.make_harness(ContractScenario.MODEL_AVAILABLE)

        snapshot = await harness.adapter.discover()

        assert snapshot.reachable is True
        assert snapshot.compatible is True
        assert snapshot.model_available is True
        assert snapshot.generation_ready is False

    @pytest.mark.asyncio
    async def test_readiness_requires_a_minimal_real_generation_semantic(self) -> None:
        harness = self.make_harness(ContractScenario.GENERATION_READY)

        snapshot = await harness.adapter.discover()

        assert snapshot.generation_ready is True
        generation_requests = [
            request
            for request in harness.requests
            if request.url.path.endswith("/chat/completions")
        ]
        assert len(generation_requests) == 1
        payload = generation_requests[0].read().decode("utf-8")
        assert '"max_tokens":1' in payload

    @pytest.mark.asyncio
    async def test_chat_forces_reasoning_off_and_never_returns_reasoning_content(self) -> None:
        harness = self.make_harness(ContractScenario.REASONING_RESPONSE)
        request = ChatRequest(
            request_id="req-chat",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )

        result = await harness.adapter.chat(request)

        assert result.success is True
        assert result.content == "visible"
        serialized_request = harness.requests[-1].read().decode("utf-8")
        assert '"enable_thinking":false' in serialized_request
        assert '"thinking_budget_enabled":false' in serialized_request
        assert "reasoning_content" not in result.model_dump_json()
        assert "hidden-reasoning" not in result.model_dump_json()

    @pytest.mark.asyncio
    async def test_embedding_reports_unsupported_as_a_typed_result(self) -> None:
        harness = self.make_harness(ContractScenario.EMBEDDING_UNSUPPORTED)

        result = await harness.adapter.embed(
            EmbeddingRequest(request_id="req-embed", model="model-a", input="hello")
        )

        assert result.status is OperationStatus.UNSUPPORTED
        assert result.error is not None
        assert result.error.code is AdapterErrorCode.UNSUPPORTED

    @pytest.mark.asyncio
    async def test_load_is_idempotent_when_inventory_is_already_loaded(self) -> None:
        harness = self.make_harness(ContractScenario.MODEL_ALREADY_LOADED)

        result = await harness.adapter.load_model("model-a", idempotency_key="idem-load")

        assert result.status is OperationStatus.UNCHANGED
        assert result.changed is False
        assert all(request.method == "GET" for request in harness.requests)

    @pytest.mark.asyncio
    async def test_stream_emits_content_usage_and_done_with_explicit_phase(self) -> None:
        harness = self.make_harness(ContractScenario.STREAM_SUCCESS)
        request = ChatRequest(
            request_id="req-stream",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )

        events = [event async for event in harness.adapter.stream_chat(request)]

        assert [event.kind for event in events] == [
            StreamEventKind.CONTENT,
            StreamEventKind.USAGE,
            StreamEventKind.DONE,
        ]
        assert events[0].content == "hello"
        assert events[0].emitted_content is True
        assert events[-1].phase is StreamPhase.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("scenario", "emitted_content", "phase", "code"),
        [
            (
                ContractScenario.STREAM_EMPTY,
                False,
                StreamPhase.BEFORE_CONTENT,
                AdapterErrorCode.BAD_RESPONSE,
            ),
            (
                ContractScenario.STREAM_NON_JSON,
                False,
                StreamPhase.BEFORE_CONTENT,
                AdapterErrorCode.BAD_RESPONSE,
            ),
            (
                ContractScenario.STREAM_BREAK_BEFORE_CONTENT,
                False,
                StreamPhase.BEFORE_CONTENT,
                AdapterErrorCode.STREAM_INTERRUPTED,
            ),
            (
                ContractScenario.STREAM_BREAK_AFTER_CONTENT,
                True,
                StreamPhase.AFTER_CONTENT,
                AdapterErrorCode.STREAM_INTERRUPTED,
            ),
        ],
    )
    async def test_stream_failures_never_hide_replay_safety_state(
        self,
        scenario: ContractScenario,
        emitted_content: bool,
        phase: StreamPhase,
        code: AdapterErrorCode,
    ) -> None:
        harness = self.make_harness(scenario)
        request = ChatRequest(
            request_id="req-stream-failure",
            model="model-a",
            messages=(ChatMessage(role="user", content="hello"),),
        )

        events = [event async for event in harness.adapter.stream_chat(request)]

        assert events[-1].kind is StreamEventKind.ERROR
        assert events[-1].emitted_content is emitted_content
        assert events[-1].phase is phase
        assert events[-1].error is not None
        assert events[-1].error.code is code


def request_json(request: httpx.Request) -> Mapping[str, object]:
    """Typed helper for concrete harness assertions without coupling the contract."""
    import json

    parsed = json.loads(request.read())
    if not isinstance(parsed, dict):
        raise AssertionError("expected JSON object request")
    return parsed
