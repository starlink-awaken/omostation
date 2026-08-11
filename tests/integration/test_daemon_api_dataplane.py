from __future__ import annotations

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
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TokenUsage,
)


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
            placement_id="placement-a",
            attempted_placements=("placement-a",),
            result=ChatResult(
                request_id=request.request_id,
                success=True,
                content="answer",
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
            ),
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
            placement_id="placement-a",
            attempted_placements=("placement-a",),
            embeddings=tuple((float(index), 1.0) for index in range(count)),
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
        )


@pytest.fixture
def inference() -> FakeInferenceService:
    return FakeInferenceService()


@pytest.fixture
def transport(inference: FakeInferenceService) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=create_app(inference=inference))


@pytest.mark.asyncio
async def test_openai_models_and_nonstream_chat_shape_preserve_typed_image(
    transport: httpx.ASGITransport, inference: FakeInferenceService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        models = await client.get("/openai/v1/models")
        chat = await client.post(
            "/openai/v1/chat/completions",
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
            },
        )

    assert models.json() == {
        "object": "list",
        "data": [{"id": "local/model", "object": "model", "owned_by": "omlxc"}],
    }
    payload = chat.json()
    assert chat.status_code == 200
    assert payload["object"] == "chat.completion"
    assert payload["model"] == "local/model"
    assert payload["choices"][0]["message"] == {"role": "assistant", "content": "answer"}
    assert payload["usage"]["total_tokens"] == 3
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
    assert inference.stream.closed


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
    assert "secret backend detail" not in response.text
    assert "[DONE]" not in response.text
    assert response.text.count("partial") == 1
    assert inference.stream.closed


@pytest.mark.asyncio
async def test_embeddings_rerank_and_thinking_fail_closed(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        embeddings = await client.post(
            "/openai/v1/embeddings",
            json={"model": "local/model", "input": ["a", "b"]},
        )
        rerank = await client.post(
            "/api/v1/rerank",
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
    assert rerank.status_code == 200
    assert rerank.json()["data"][0] == {"index": 0, "relevance_score": 1.0}
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
            json={"model": "local/model", "messages": [{"role": "user", "content": "x"}]},
        )
        oversized = await client.post(
            "/openai/v1/embeddings",
            json={"model": "local/model", "input": "x" * 1_100_001},
        )

    assert failed.status_code == 503
    assert failed.json()["error"]["message"] == "local inference failed"
    assert "do-not-leak" not in failed.text
    assert oversized.status_code == 413


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
