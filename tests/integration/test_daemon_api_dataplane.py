from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator

import httpx
import pytest

from omlxc.api import create_app
from omlxc.dataplane import (
    ChatExecution,
    EmbeddingExecution,
    ExecutionError,
    ExecutionErrorCode,
    RankedItem,
    RerankExecution,
)
from omlxc.domain import RouteProfile
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    PrepareRejection,
    PrepareRejectionCode,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TokenUsage,
)
from omlxc.scheduler import RejectionCode


class FakeStream(AsyncIterator[StreamEvent]):
    def __init__(self, events: tuple[StreamEvent, ...]) -> None:
        self._events = iter(events)
        self.closed = False

    def __aiter__(self) -> FakeStream:
        return self

    async def __anext__(self) -> StreamEvent:
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        self.closed = True


class FakeInferenceService:
    final_placement_id = "placement-a"
    final_backend_id = "backend-a"
    final_profile = RouteProfile.QUALITY

    def __init__(self) -> None:
        self.chat_requests: list[ChatRequest] = []
        self.embedding_requests: list[EmbeddingRequest] = []
        self.stream = FakeStream(
            (
                StreamEvent(
                    kind=StreamEventKind.CONTENT,
                    request_id="unused",
                    content="hello",
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                    placement_id="placement-final",
                    backend_id="backend-final",
                ),
                StreamEvent(
                    kind=StreamEventKind.USAGE,
                    request_id="unused",
                    usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                    placement_id="placement-final",
                    backend_id="backend-final",
                ),
                StreamEvent(
                    kind=StreamEventKind.DONE,
                    request_id="unused",
                    emitted_content=True,
                    phase=StreamPhase.COMPLETE,
                    placement_id="placement-final",
                    backend_id="backend-final",
                ),
            )
        )

    async def list_openai_models(self) -> tuple[str, ...]:
        return ("local/model",)

    async def chat(self, route: object, request: ChatRequest, *, deadline: float) -> ChatExecution:
        assert deadline > 0
        self.chat_requests.append(request)
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=True,
            placement_id=self.final_placement_id,
            attempted_placements=(self.final_placement_id,),
            result=ChatResult(
                request_id=request.request_id,
                success=True,
                content="answer",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
            ),
            backend_id=self.final_backend_id,
            profile=self.final_profile,
        )

    def stream_chat(
        self, route: object, request: ChatRequest, *, deadline: float
    ) -> AsyncIterator[StreamEvent]:
        assert deadline > 0
        self.chat_requests.append(request)
        return self.stream

    async def embed(
        self, route: object, request: EmbeddingRequest, *, deadline: float
    ) -> EmbeddingExecution:
        self.embedding_requests.append(request)
        count = 1 if isinstance(request.input, str) else len(request.input)
        return EmbeddingExecution(
            request_id=request.request_id,
            model_id=request.model,
            placement_id=self.final_placement_id,
            attempted_placements=(self.final_placement_id,),
            embeddings=tuple((float(index), 1.0) for index in range(count)),
            backend_id=self.final_backend_id,
            profile=self.final_profile,
        )

    async def rerank(
        self, *, request_id: str, query: str, documents: tuple[str, ...]
    ) -> RerankExecution:
        del query
        return RerankExecution(
            request_id,
            tuple(
                RankedItem(index=index, score=1.0 - index / 10) for index in range(len(documents))
            ),
            placement_id=self.final_placement_id,
            backend_id=self.final_backend_id,
            profile=self.final_profile,
        )


@pytest.fixture
def inference() -> FakeInferenceService:
    return FakeInferenceService()


@pytest.fixture
def transport(inference: FakeInferenceService) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=create_app(inference=inference))


@pytest.mark.asyncio
async def test_openai_nonstream_chat_shape_and_aetherforge_strict_route_headers(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        models = await client.get("/openai/v1/models")
        chat = await client.post(
            "/openai/v1/chat/completions",
            headers={"X-OMLXC-Request-ID": "strict.req-1"},
            json={
                "model": "local/model",
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
                "profile": "batch",
            },
        )

    assert models.json() == {
        "object": "list",
        "data": [{"id": "local/model", "object": "model", "owned_by": "omlxc"}],
    }
    payload = chat.json()
    assert chat.status_code == 200
    assert payload["object"] == "chat.completion"
    assert payload["id"] == "chatcmpl-strict.req-1"
    assert payload["model"] == "local/model"
    assert payload["choices"][0]["message"] == {"role": "assistant", "content": "answer"}
    assert payload["usage"]["total_tokens"] == 3
    assert chat.headers["content-type"].startswith("application/json")
    assert chat.headers["X-OMLXC-Request-ID"] == "strict.req-1"
    assert chat.headers["X-OMLXC-Placement"] == inference.final_placement_id
    assert chat.headers["X-OMLXC-Backend"] == inference.final_backend_id
    assert chat.headers["X-OMLXC-Profile"] == inference.final_profile.value
    blocks = inference.chat_requests[0].messages[0].content
    assert not isinstance(blocks, str)
    assert blocks[1].image_url.url == "https://images.invalid/local.png"


@pytest.mark.asyncio
async def test_sse_prefetches_final_failover_metadata_and_emits_unique_done(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
                "profile": "interactive",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["X-OMLXC-Profile"] == "interactive"
    assert response.headers["X-OMLXC-Placement"] == "placement-final"
    assert response.headers["X-OMLXC-Backend"] == "backend-final"
    data_lines = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert data_lines[-1] == "[DONE]"
    assert data_lines.count("[DONE]") == 1
    chunks = [json.loads(line) for line in data_lines[:-1]]
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"
    assert chunks[-1]["choices"] == [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    assert inference.stream.closed


@pytest.mark.asyncio
async def test_sse_preserves_length_finish_reason_after_usage(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    inference.stream = FakeStream(
        (
            StreamEvent(
                kind=StreamEventKind.CONTENT,
                request_id="unused",
                content="partial",
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="placement-final",
                backend_id="backend-final",
            ),
            StreamEvent(
                kind=StreamEventKind.USAGE,
                request_id="unused",
                usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="placement-final",
                backend_id="backend-final",
            ),
            StreamEvent(
                kind=StreamEventKind.DONE,
                request_id="unused",
                finish_reason="length",
                emitted_content=True,
                phase=StreamPhase.COMPLETE,
                placement_id="placement-final",
                backend_id="backend-final",
            ),
        )
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    data_lines = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert data_lines[-1] == "[DONE]"
    chunks = [json.loads(line) for line in data_lines[:-1]]
    assert chunks[-2]["choices"] == []
    assert chunks[-1]["choices"] == [{"index": 0, "delta": {}, "finish_reason": "length"}]


@pytest.mark.asyncio
async def test_post_token_stream_error_is_structured_without_replay(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    inference.stream = FakeStream(
        (
            StreamEvent(
                kind=StreamEventKind.CONTENT,
                request_id="unused",
                content="partial",
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="p",
                backend_id="b",
            ),
            StreamEvent(
                kind=StreamEventKind.ERROR,
                request_id="unused",
                error=AdapterError(
                    code=AdapterErrorCode.STREAM_INTERRUPTED,
                    message="secret backend detail",
                    retryable=True,
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                ),
                emitted_content=True,
                phase=StreamPhase.AFTER_CONTENT,
                placement_id="p",
                backend_id="b",
            ),
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert "partial" in response.text
    assert '"type":"stream_error"' in response.text
    chunks = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert chunks[-1]["error"]["partial_result"] == {
        "error_code": "stream_interrupted",
        "phase": "after_content",
        "emitted_content": True,
    }
    assert "secret backend detail" not in response.text
    assert "[DONE]" not in response.text
    assert (
        sum(
            chunk.get("choices", [{}])[0].get("delta", {}).get("content") == "partial"
            for chunk in chunks
        )
        == 1
    )
    assert inference.stream.closed


@pytest.mark.asyncio
async def test_first_stream_prepare_error_matches_nonstream_typed_partial_result(
    inference: FakeInferenceService,
) -> None:
    inference.stream = FakeStream(
        (
            StreamEvent(
                kind=StreamEventKind.ERROR,
                request_id="unused",
                error=AdapterError(
                    code=AdapterErrorCode.MODEL_UNAVAILABLE,
                    message="safe typed preparation failure",
                ),
                emitted_content=False,
                phase=StreamPhase.BEFORE_CONTENT,
                prepare_rejections=(
                    PrepareRejection(placement_id="placement-a", reason=PrepareRejectionCode.STALE),
                    PrepareRejection(
                        placement_id="placement-b",
                        reason=PrepareRejectionCode.CAPABILITY,
                    ),
                ),
            ),
        )
    )
    transport = httpx.ASGITransport(app=create_app(inference=inference))
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["partial_result"] == {
        "prepare_rejections": [
            {"placement_id": "placement-a", "reason": "stale"},
            {"placement_id": "placement-b", "reason": "capability_missing"},
        ]
    }
    assert "safe typed preparation failure" not in response.text
    assert inference.stream.closed


@pytest.mark.asyncio
async def test_embeddings_rerank_and_thinking_fail_closed(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        embeddings = await client.post(
            "/openai/v1/embeddings",
            headers={"X-OMLXC-Request-ID": "strict.embed-1"},
            json={"model": "local/model", "input": ["a", "b"], "profile": "batch"},
        )
        rerank = await client.post(
            "/api/v1/rerank",
            headers={"X-OMLXC-Request-ID": "strict.rerank-1"},
            json={"model": "local/reranker", "query": "q", "documents": ["a", "b"]},
        )
        thinking = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "profile": "quality",
                "thinking": True,
            },
        )

    assert embeddings.status_code == 200
    assert [item["index"] for item in embeddings.json()["data"]] == [0, 1]
    assert embeddings.headers["content-type"].startswith("application/json")
    assert embeddings.headers["X-OMLXC-Request-ID"] == "strict.embed-1"
    assert embeddings.headers["X-OMLXC-Placement"] == "placement-a"
    assert embeddings.headers["X-OMLXC-Backend"] == inference.final_backend_id
    assert embeddings.headers["X-OMLXC-Profile"] == inference.final_profile.value
    assert rerank.status_code == 200
    assert rerank.json()["request_id"] == "strict.rerank-1"
    assert rerank.json()["data"][0] == {"index": 0, "relevance_score": 1.0}
    assert rerank.headers["content-type"].startswith("application/json")
    assert rerank.headers["X-OMLXC-Request-ID"] == "strict.rerank-1"
    assert rerank.headers["X-OMLXC-Placement"] == inference.final_placement_id
    assert rerank.headers["X-OMLXC-Backend"] == inference.final_backend_id
    assert rerank.headers["X-OMLXC-Profile"] == inference.final_profile.value
    assert thinking.status_code == 400
    assert thinking.json()["error"]["type"] == "unsupported_feature"


@pytest.mark.asyncio
async def test_openai_errors_are_sanitized_and_request_bodies_are_bounded(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async def failed_chat(route: object, request: ChatRequest, *, deadline: float) -> ChatExecution:
        del route, deadline
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=False,
            placement_id="placement-a",
            attempted_placements=("placement-a",),
            error=ExecutionError(
                ExecutionErrorCode.BACKEND_FAILURE,
                False,
                reason="Authorization: Bearer do-not-leak",
            ),
        )

    inference.chat = failed_chat  # type: ignore[method-assign]
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        failed = await client.post(
            "/openai/v1/chat/completions",
            headers={"X-OMLXC-Request-ID": "strict.error-1"},
            json={"model": "local/model", "messages": [{"role": "user", "content": "x"}]},
        )
        oversized = await client.post(
            "/openai/v1/embeddings",
            json={"model": "local/model", "input": "x" * 1_100_001},
        )

    assert failed.status_code == 503
    assert failed.json()["error"]["message"] == "local inference failed"
    assert failed.headers["X-OMLXC-Request-ID"] == "strict.error-1"
    assert "X-OMLXC-Placement" not in failed.headers
    assert "X-OMLXC-Backend" not in failed.headers
    assert "X-OMLXC-Profile" not in failed.headers
    assert "do-not-leak" not in failed.text
    assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_prepare_rejections_are_ordered_typed_and_sanitized(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async def rejected_chat(
        route: object, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        del route, deadline
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=False,
            placement_id="placement-b",
            attempted_placements=("placement-a", "placement-b"),
            error=ExecutionError(
                ExecutionErrorCode.NO_CANDIDATE,
                False,
                prepare_rejections=(
                    ("placement-a", RejectionCode.STALE),
                    ("placement-b", RejectionCode.CAPABILITY),
                ),
            ),
        )

    inference.chat = rejected_chat  # type: ignore[method-assign]
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={"model": "local/model", "messages": [{"role": "user", "content": "x"}]},
        )

    assert response.status_code == 409
    assert response.json()["error"]["partial_result"] == {
        "prepare_rejections": [
            {"placement_id": "placement-a", "reason": "stale"},
            {"placement_id": "placement-b", "reason": "capability_missing"},
        ]
    }
    assert "X-OMLXC-Placement" not in response.headers


@pytest.mark.asyncio
async def test_prepare_rejection_api_uses_stable_opaque_id_for_unsafe_config_id(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    unsafe_id = "node/private/model"
    expected_id = f"opaque:{hashlib.sha256(unsafe_id.encode()).hexdigest()[:12]}"

    async def rejected_chat(
        route: object, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        del route, deadline
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=False,
            placement_id=unsafe_id,
            attempted_placements=(unsafe_id,),
            error=ExecutionError(
                ExecutionErrorCode.NO_CANDIDATE,
                False,
                prepare_rejections=((unsafe_id, RejectionCode.UNAVAILABLE),),
            ),
        )

    inference.chat = rejected_chat  # type: ignore[method-assign]
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={"model": "local/model", "messages": [{"role": "user", "content": "x"}]},
        )

    assert response.status_code == 409
    assert response.json()["error"]["partial_result"] == {
        "prepare_rejections": [{"placement_id": expected_id, "reason": "unavailable"}]
    }
    assert unsafe_id not in response.text


@pytest.mark.asyncio
async def test_incomplete_success_metadata_fails_closed_without_route_headers(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async def incomplete_chat(
        route: object, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        del route, deadline
        return ChatExecution(
            request_id=request.request_id,
            model_id=request.model,
            success=True,
            placement_id="observed-placement",
            attempted_placements=("observed-placement",),
            result=ChatResult(request_id=request.request_id, success=True, content="answer"),
        )

    inference.chat = incomplete_chat  # type: ignore[method-assign]
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            headers={"X-OMLXC-Request-ID": "strict.incomplete-1"},
            json={"model": "local/model", "messages": [{"role": "user", "content": "x"}]},
        )

    assert response.status_code == 503
    assert response.headers["X-OMLXC-Request-ID"] == "strict.incomplete-1"
    assert "X-OMLXC-Placement" not in response.headers
    assert "X-OMLXC-Backend" not in response.headers
    assert "X-OMLXC-Profile" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "message", "status", "error_type"),
    [
        (AdapterErrorCode.TIMEOUT, "timeout", 504, "timeout"),
        (AdapterErrorCode.UNSUPPORTED, "unsupported", 400, "unsupported_feature"),
        (AdapterErrorCode.MODEL_UNAVAILABLE, "no_capacity", 409, "insufficient_capacity"),
    ],
)
async def test_first_stream_error_reuses_typed_http_mapping(
    inference: FakeInferenceService,
    code: AdapterErrorCode,
    message: str,
    status: int,
    error_type: str,
) -> None:
    inference.stream = FakeStream(
        (
            StreamEvent(
                kind=StreamEventKind.ERROR,
                request_id="unused",
                error=AdapterError(code=code, message=message),
                emitted_content=False,
                phase=StreamPhase.BEFORE_CONTENT,
            ),
        )
    )
    transport = httpx.ASGITransport(app=create_app(inference=inference))
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "local/model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == status
    assert response.json()["error"]["type"] == error_type
    assert inference.stream.closed
