"""Review-remediation tests for bounded and fail-closed Ollama behavior."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest

from omlxc.adapters.ollama import OllamaAdapter
from omlxc.adapters.reasoning import ReasoningFilter
from omlxc.domain.protocols import (
    AdapterErrorCode,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    ImageContentBlock,
    ImageURL,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    TextContentBlock,
    TuneRequest,
    TuneScope,
    TuneSettings,
)

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


def _adapter(handler: Handler, **kwargs: object) -> OllamaAdapter:
    return OllamaAdapter(
        backend_id="ollama-fix1",
        base_url="https://ollama.invalid",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _chat_request(
    *, model: str = "model:latest", messages: tuple[ChatMessage, ...] | None = None
) -> ChatRequest:
    return ChatRequest(
        request_id="fix1-chat",
        model=model,
        messages=messages or (ChatMessage(role="user", content="hello"),),
    )


def _terminal(*, content: str = "", **extra: object) -> dict[str, object]:
    return {
        "message": {"content": content},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 2,
        "eval_count": 1,
        **extra,
    }


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...], *, fail_after: bool = False) -> None:
        self._chunks = chunks
        self._fail_after = fail_after
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk
        if self._fail_after:
            raise httpx.ReadError("remote stream failed")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_terminal_done_rejects_record_in_later_chunk() -> None:
    terminal = json.dumps(_terminal()).encode() + b"\n"
    extra = b'{"message":{"content":"late"},"done":false}\n'
    adapter = _adapter(lambda request: httpx.Response(200, stream=ChunkStream((terminal, extra))))

    events = [event async for event in adapter.stream_chat(_chat_request())]

    assert [event.kind for event in events] == [StreamEventKind.ERROR]
    assert events[0].error is not None
    assert events[0].error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_terminal_done_waits_for_clean_eof_before_usage_and_done() -> None:
    terminal_sent = asyncio.Event()
    allow_eof = asyncio.Event()

    class TerminalThenBlock(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            terminal_sent.set()
            yield json.dumps(_terminal()).encode() + b"\n"
            await allow_eof.wait()

    adapter = _adapter(lambda request: httpx.Response(200, stream=TerminalThenBlock()))
    observed: list[StreamEvent] = []

    async def consume() -> None:
        async for event in adapter.stream_chat(_chat_request()):
            observed.append(event)

    task = asyncio.create_task(consume())
    await terminal_sent.wait()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert observed == []
    assert task.done() is False
    allow_eof.set()
    await task
    assert [event.kind for event in observed] == [
        StreamEventKind.USAGE,
        StreamEventKind.DONE,
    ]


@pytest.mark.asyncio
async def test_terminal_done_followed_by_read_error_never_emits_done() -> None:
    stream = ChunkStream((json.dumps(_terminal()).encode() + b"\n",), fail_after=True)
    adapter = _adapter(lambda request: httpx.Response(200, stream=stream))

    events = [event async for event in adapter.stream_chat(_chat_request())]

    assert [event.kind for event in events] == [StreamEventKind.ERROR]
    assert events[0].error is not None
    assert events[0].error.code is AdapterErrorCode.STREAM_INTERRUPTED
    assert stream.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "settings",
    [
        TuneSettings(is_pinned=True),
        TuneSettings(is_pinned=False),
        TuneSettings(ttl_seconds=60, is_pinned=True),
        TuneSettings(ttl_seconds=60, is_pinned=False),
    ],
)
async def test_pin_tuning_is_unsupported_and_never_writes(settings: TuneSettings) -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    adapter = _adapter(handler)
    result = await adapter.tune(
        TuneRequest(scope=TuneScope.MODEL, model_id="model:latest", settings=settings)
    )

    assert result.status is OperationStatus.UNSUPPORTED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED
    assert calls == []


def test_ndjson_record_and_total_byte_limits_stop_unbounded_accumulation() -> None:
    from omlxc.adapters.ndjson import NDJSONDecoder, NDJSONLimitError

    record_decoder = NDJSONDecoder(max_record_bytes=8, max_total_bytes=100)
    with pytest.raises(NDJSONLimitError):
        record_decoder.feed(b"x" * 9)

    total_decoder = NDJSONDecoder(max_record_bytes=16, max_total_bytes=17)
    assert total_decoder.feed(b"{}\n{}\n{}\n") == ({}, {}, {})
    with pytest.raises(NDJSONLimitError):
        total_decoder.feed(b"{}\n{}\n{}\n")


@pytest.mark.asyncio
async def test_nonstream_response_body_limit_is_output_limit_and_closes_stream() -> None:
    body = b'{"embeddings":[[1.0]]}' + b" " * 100
    stream = ChunkStream((body,))
    adapter = _adapter(lambda request: httpx.Response(200, stream=stream), max_response_bytes=32)

    result = await adapter.embed(
        EmbeddingRequest(request_id="bounded", model="embed:latest", input="hello")
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert stream.closed is True


@pytest.mark.asyncio
async def test_stream_record_and_total_limits_map_to_output_limit() -> None:
    record_adapter = _adapter(
        lambda request: httpx.Response(200, stream=ChunkStream((b"x" * 9,))),
        max_ndjson_record_bytes=8,
        max_stream_bytes=10,
    )
    record = b'{"message":{"content":""},"done":false}\n'
    total_adapter = _adapter(
        lambda request: httpx.Response(200, stream=ChunkStream((record, record, record))),
        max_ndjson_record_bytes=64,
        max_stream_bytes=100,
    )

    record_events = [event async for event in record_adapter.stream_chat(_chat_request())]
    total_events = [event async for event in total_adapter.stream_chat(_chat_request())]

    assert record_events[-1].error is not None
    assert record_events[-1].error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert total_events[-1].error is not None
    assert total_events[-1].error.code is AdapterErrorCode.OUTPUT_LIMIT


@pytest.mark.asyncio
async def test_embedding_request_count_dimension_total_and_bool_are_bounded() -> None:
    responses = iter(
        [
            {"embeddings": [[1.0, 2.0, 3.0]]},
            {"embeddings": [[1.0, 2.0], [3.0, 4.0]]},
            {"embeddings": [[True]]},
        ]
    )
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=next(responses))

    adapter = _adapter(
        handler,
        max_embedding_inputs=2,
        max_embedding_dimension=2,
        max_embedding_scalars=3,
    )
    too_many = await adapter.embed(
        EmbeddingRequest(request_id="count", model="embed:latest", input=("a", "b", "c"))
    )
    too_wide = await adapter.embed(
        EmbeddingRequest(request_id="dim", model="embed:latest", input="a")
    )
    too_many_scalars = await adapter.embed(
        EmbeddingRequest(request_id="total", model="embed:latest", input=("a", "b"))
    )
    boolean = await adapter.embed(
        EmbeddingRequest(request_id="bool", model="embed:latest", input="a")
    )

    assert too_many.error is not None
    assert too_many.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert too_wide.error is not None
    assert too_wide.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert too_many_scalars.error is not None
    assert too_many_scalars.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert boolean.error is not None
    assert boolean.error.code is AdapterErrorCode.BAD_RESPONSE
    assert calls == 3


def _image_message(payloads: tuple[bytes, ...]) -> tuple[ChatMessage, ...]:
    blocks: list[TextContentBlock | ImageContentBlock] = [TextContentBlock(text="describe")]
    blocks.extend(
        ImageContentBlock(
            image_url=ImageURL(
                url="data:image/png;base64," + base64.b64encode(payload).decode("ascii")
            )
        )
        for payload in payloads
    )
    return (ChatMessage(role="user", content=tuple(blocks)),)


@pytest.mark.asyncio
async def test_vision_single_count_and_total_decoded_limits_prevent_http() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    adapter = _adapter(
        handler,
        max_images=2,
        max_image_bytes=3,
        max_total_image_bytes=4,
    )
    single = await adapter.chat(_chat_request(messages=_image_message((b"1234",))))
    count = await adapter.chat(_chat_request(messages=_image_message((b"1", b"2", b"3"))))
    total = await adapter.chat(
        _chat_request(
            messages=_image_message(
                (
                    b"12",
                    b"345",
                )
            )
        )
    )

    assert single.error is not None and single.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert count.error is not None and count.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert total.error is not None and total.error.code is AdapterErrorCode.OUTPUT_LIMIT
    assert calls == 0


def test_reasoning_filter_exposes_observed_reasoning_without_changing_filter_output() -> None:
    reasoning_filter = ReasoningFilter()

    assert reasoning_filter.feed("<think>hidden</think>visible") == "visible"
    assert reasoning_filter.finish() == ("", False)
    assert reasoning_filter.saw_reasoning is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _terminal(content="visible", thinking="top-hidden"),
        {**_terminal(content="visible"), "message": {"content": "visible", "thinking": "hidden"}},
        _terminal(content="<think>hidden</think>visible"),
        _terminal(content="visible<think>hidden"),
    ],
)
async def test_nonstream_observable_thinking_is_typed_failure(
    response: dict[str, object],
) -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json=response))

    result = await adapter.chat(_chat_request())

    assert result.success is False
    assert result.error is not None
    assert result.error.code in {AdapterErrorCode.INCOMPATIBLE, AdapterErrorCode.BAD_RESPONSE}
    assert result.content == ""
    assert "hidden" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_stream_observable_thinking_fails_with_existing_content_phase() -> None:
    body = (
        b'{"message":{"content":"visible"},"done":false}\n'
        + json.dumps(
            {
                **_terminal(),
                "message": {"content": "", "thinking": "hidden"},
            }
        ).encode()
        + b"\n"
    )
    adapter = _adapter(lambda request: httpx.Response(200, content=body))

    events = [event async for event in adapter.stream_chat(_chat_request())]

    assert [event.kind for event in events] == [
        StreamEventKind.CONTENT,
        StreamEventKind.ERROR,
    ]
    assert events[-1].error is not None
    assert events[-1].error.code is AdapterErrorCode.INCOMPATIBLE
    assert events[-1].emitted_content is True


@pytest.mark.asyncio
async def test_generation_probe_is_not_ready_when_thinking_is_observed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.32.6"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "model:latest", "model": "model:latest", "digest": "sha256:a"}
                    ]
                },
            )
        if request.url.path == "/api/ps":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "model:latest", "model": "model:latest", "digest": "sha256:a"}
                    ]
                },
            )
        return httpx.Response(200, json=_terminal(content="<think>hidden</think>O"))

    adapter = _adapter(handler, probe_model_id="model:latest")

    snapshot = await adapter.discover()

    assert snapshot.generation_ready is False
    assert snapshot.errors
    assert snapshot.errors[-1].code is AdapterErrorCode.INCOMPATIBLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal",
    [
        {"done": True, "done_reason": "stop", "prompt_eval_count": 1, "eval_count": 1},
        {
            "message": {},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": 1,
        },
        {"message": {"content": ""}, "done": True, "done_reason": "stop", "eval_count": 1},
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": True,
            "eval_count": 1,
        },
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": -1,
        },
        {
            "message": {"content": ""},
            "done": True,
            "prompt_eval_count": 1,
            "eval_count": 1,
        },
    ],
)
async def test_stream_terminal_requires_message_content_usage_and_done_reason(
    terminal: dict[str, object],
) -> None:
    adapter = _adapter(
        lambda request: httpx.Response(200, content=json.dumps(terminal).encode() + b"\n")
    )

    events = [event async for event in adapter.stream_chat(_chat_request())]

    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].error is not None
    assert events[-1].error.code is AdapterErrorCode.BAD_RESPONSE
