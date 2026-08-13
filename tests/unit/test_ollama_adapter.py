"""Native Ollama adapter tests; all traffic is handled by MockTransport."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from omlxc.adapters.ollama import OllamaAdapter
from omlxc.domain.protocols import (
    AdapterErrorCode,
    BackendAdapter,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    ImageContentBlock,
    ImageURL,
    ModelRuntimeState,
    OperationStatus,
    StreamEventKind,
    StreamPhase,
    TextContentBlock,
    TuneRequest,
    TuneScope,
    TuneSettings,
)


def _tag(model: str, digest: str = "sha256:abc") -> dict[str, object]:
    return {"name": model, "model": model, "digest": digest}


def _request(request_id: str = "req") -> ChatRequest:
    return ChatRequest(
        request_id=request_id,
        model="library/model:latest",
        messages=(ChatMessage(role="user", content="hello"),),
        max_tokens=7,
        temperature=0.25,
    )


def _adapter(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: object,
) -> OllamaAdapter:
    return OllamaAdapter(
        backend_id="ollama-test",
        base_url="https://ollama.invalid",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://ollama.invalid",
        "https://user:secret@ollama.invalid",
        "https://ollama.invalid/api",
        "https://ollama.invalid/?token=secret",
        "https://ollama.invalid/#fragment",
        "https://ollama.invalid/\n",
    ],
)
def test_base_url_accepts_only_clean_http_root(url: str) -> None:
    from omlxc.adapters.ollama import OllamaAdapter

    with pytest.raises(ValueError):
        OllamaAdapter(backend_id="ollama", base_url=url)


@pytest.mark.parametrize(
    "model_id",
    ["-flag", "white space", "user@host", "$(touch pwned)", "../model", "a/../b", "a\\b"],
)
@pytest.mark.asyncio
async def test_model_identifier_rejects_shell_userinfo_and_traversal(model_id: str) -> None:
    adapter = _adapter(lambda request: httpx.Response(500))

    result = await adapter.load_model(model_id)

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.INVALID_REQUEST


@pytest.mark.parametrize("keep_alive", [True, "10m", 0, -1, 86401])
def test_keep_alive_is_a_bounded_integer(keep_alive: object) -> None:
    from omlxc.adapters.ollama import OllamaAdapter

    with pytest.raises((TypeError, ValueError)):
        OllamaAdapter(
            backend_id="ollama",
            base_url="https://ollama.invalid",
            keep_alive_seconds=keep_alive,  # type: ignore[arg-type]
        )


def test_constructor_rejects_invalid_probe_and_conflicting_http_injection() -> None:
    from omlxc.adapters.ollama import OllamaAdapter

    with pytest.raises(ValueError):
        OllamaAdapter(backend_id="ollama", probe_model_id="../model")
    client = httpx.AsyncClient()
    try:
        with pytest.raises(ValueError):
            OllamaAdapter(
                backend_id="ollama",
                client=client,
                transport=httpx.MockTransport(lambda request: httpx.Response(200)),
            )
    finally:
        asyncio.run(client.aclose())


@pytest.mark.asyncio
async def test_version_must_be_2xx_strict_json_with_semantic_version() -> None:
    responses = iter(
        [
            httpx.Response(200, content=b""),
            httpx.Response(200, json={"version": "latest"}),
            httpx.Response(503, json={"version": "0.12.6"}),
        ]
    )
    adapter = _adapter(lambda request: next(responses))

    snapshots = [await adapter.discover() for _ in range(3)]

    assert all(item.reachable for item in snapshots)
    assert all(not item.compatible for item in snapshots)
    assert all(item.errors[0].code is AdapterErrorCode.INCOMPATIBLE for item in snapshots)


@pytest.mark.asyncio
async def test_discovery_transport_failure_is_typed_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("remote secret")

    adapter = _adapter(handler)
    snapshot = await adapter.discover()

    assert snapshot.reachable is False
    assert snapshot.errors[0].code is AdapterErrorCode.TIMEOUT
    assert "secret" not in snapshot.model_dump_json()


@pytest.mark.asyncio
async def test_tags_success_and_ps_failure_produces_unknown_not_available() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            return httpx.Response(503, content=b"secret remote body")
        raise AssertionError(request.url.path)

    adapter = _adapter(handler)
    models = await adapter.list_models()

    assert [(model.id, model.state, model.loaded) for model in models] == [
        ("library/model:latest", ModelRuntimeState.UNKNOWN, None)
    ]


@pytest.mark.asyncio
async def test_ps_only_loaded_model_is_preserved() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("catalog:latest")]})
        return httpx.Response(200, json={"models": [_tag("loaded-only:latest", "sha256:def")]})

    adapter = _adapter(handler)
    models = await adapter.list_models()

    assert [(model.id, model.loaded) for model in models] == [
        ("catalog:latest", False),
        ("loaded-only:latest", True),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tags,ps",
    [
        ([_tag("same:latest"), _tag("same:latest", "sha256:def")], []),
        ([_tag("a:latest"), _tag("b:latest")], []),
        ([_tag("a:latest")], [_tag("other:latest")]),
    ],
)
async def test_identity_alias_or_digest_ambiguity_fails_closed(
    tags: list[dict[str, object]], ps: list[dict[str, object]]
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        rows = tags if request.url.path == "/api/tags" else ps
        return httpx.Response(200, json={"models": rows})

    adapter = _adapter(handler)
    with pytest.raises(Exception) as captured:
        await adapter.list_models()

    assert "sha256:abc" not in f"{captured.value!s} {captured.value!r}"


@pytest.mark.asyncio
async def test_chat_payload_is_native_minimal_with_thinking_disabled() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"content": "visible"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 4,
                "eval_count": 2,
            },
        )

    adapter = _adapter(handler, keep_alive_seconds=42)
    result = await adapter.chat(_request())

    assert result.success is True
    assert result.content == "visible"
    assert captured == {
        "model": "library/model:latest",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "think": False,
        "options": {"num_predict": 7, "temperature": 0.25},
        "keep_alive": 42,
    }
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_chat_tools_use_native_schema_and_normalize_tool_call_arguments() -> None:
    from omlxc.domain.protocols import ChatTool, ChatToolFunction

    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "read", "arguments": {"path": "README.md"}}}
                    ],
                },
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 4,
                "eval_count": 2,
            },
        )

    adapter = _adapter(handler)
    request = _request().model_copy(
        update={
            "tools": (
                ChatTool(
                    function=ChatToolFunction(
                        name="read", parameters={"type": "object", "properties": {}}
                    )
                ),
            ),
            "tool_choice": "auto",
        }
    )
    result = await adapter.chat(request)

    assert captured["tools"][0]["function"]["name"] == "read"  # type: ignore[index]
    assert "tool_choice" not in captured
    assert result.tool_calls[0].function.arguments == '{"path":"README.md"}'
    assert result.tool_calls[0].id.startswith("call_")


@pytest.mark.asyncio
async def test_chat_converts_only_validated_data_images_without_fetching() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"content": "ok"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )

    adapter = _adapter(handler)
    data_image = "data:image/png;base64,aGVsbG8="
    request = ChatRequest(
        request_id="vision",
        model="vision:latest",
        messages=(
            ChatMessage(
                role="user",
                content=(
                    TextContentBlock(text="describe"),
                    ImageContentBlock(image_url=ImageURL(url=data_image)),
                ),
            ),
        ),
    )

    result = await adapter.chat(request)

    assert result.success is True
    assert captured["messages"] == [{"role": "user", "content": "describe", "images": ["aGVsbG8="]}]


@pytest.mark.asyncio
async def test_chat_rejects_remote_image_without_issuing_http_request() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    adapter = _adapter(handler)
    request = ChatRequest(
        request_id="vision",
        model="vision:latest",
        messages=(
            ChatMessage(
                role="user",
                content=(
                    ImageContentBlock(
                        image_url=ImageURL(url="https://metadata.invalid/latest/token")
                    ),
                ),
            ),
        ),
    )

    result = await adapter.chat(request)

    assert result.success is False
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED
    assert calls == 0


@pytest.mark.asyncio
async def test_unclosed_reasoning_fails_closed() -> None:
    adapter = _adapter(
        lambda request: httpx.Response(
            200,
            json={"message": {"content": "visible<think>secret"}, "done": True},
        )
    )

    result = await adapter.chat(_request())

    assert result.success is False
    assert result.content == ""
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 405, 501])
async def test_embed_current_endpoint_maps_unsupported_statuses(status: int) -> None:
    adapter = _adapter(lambda request: httpx.Response(status, content=b"secret"))
    result = await adapter.embed(
        EmbeddingRequest(request_id="embed", model="embed:latest", input="hello")
    )

    assert result.status is OperationStatus.UNSUPPORTED
    assert result.error is not None
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_embed_preserves_batch_order_and_validates_shape_and_finiteness() -> None:
    bodies: list[object] = [
        {"embeddings": [[1.0, 2.0], [3.0, 4.0]], "prompt_eval_count": 3},
        {"embeddings": [[1.0], [2.0, 3.0]]},
        b'{"embeddings":[[NaN],[2.0]]}',
        {"embeddings": [[]]},
        {"embeddings": [[1.0]]},
    ]
    response_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal response_index
        del request
        body = bodies[response_index]
        response_index += 1
        if isinstance(body, bytes):
            return httpx.Response(200, content=body)
        return httpx.Response(200, json=body)

    adapter = _adapter(handler)
    batch = EmbeddingRequest(request_id="batch", model="embed:latest", input=("a", "b"))

    good = await adapter.embed(batch)
    bad = [await adapter.embed(batch) for _ in range(3)]
    wrong_count = await adapter.embed(batch)

    assert good.embeddings == ((1.0, 2.0), (3.0, 4.0))
    assert all(item.status is OperationStatus.FAILED for item in bad)
    assert wrong_count.status is OperationStatus.FAILED


@pytest.mark.asyncio
async def test_load_and_unload_use_generate_and_fresh_inventory_verification() -> None:
    ps_loaded = False
    payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ps_loaded
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            rows = [_tag("library/model:latest")] if ps_loaded else []
            return httpx.Response(200, json={"models": rows})
        payload = json.loads(request.content)
        payloads.append(payload)
        ps_loaded = payload["keep_alive"] != 0
        return httpx.Response(200, json={"done": True, "response": ""})

    adapter = _adapter(handler, keep_alive_seconds=90)
    loaded = await adapter.load_model("library/model:latest", idempotency_key="load")
    unloaded = await adapter.unload_model("library/model:latest", idempotency_key="unload")

    assert loaded.status is OperationStatus.SUCCEEDED
    assert unloaded.status is OperationStatus.SUCCEEDED
    assert payloads == [
        {"model": "library/model:latest", "prompt": "", "stream": False, "keep_alive": 90},
        {"model": "library/model:latest", "prompt": "", "stream": False, "keep_alive": 0},
    ]


@pytest.mark.asyncio
async def test_unknown_lifecycle_state_never_writes() -> None:
    writes = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal writes
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            return httpx.Response(503)
        writes += 1
        return httpx.Response(200)

    adapter = _adapter(handler)
    result = await adapter.load_model("library/model:latest")

    assert result.status is OperationStatus.FAILED
    assert writes == 0


@pytest.mark.asyncio
async def test_lifecycle_missing_model_is_typed_without_writing() -> None:
    writes = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal writes
        if request.url.path in {"/api/tags", "/api/ps"}:
            return httpx.Response(200, json={"models": []})
        writes += 1
        return httpx.Response(200)

    adapter = _adapter(handler)
    result = await adapter.load_model("missing:latest")

    assert result.error is not None
    assert result.error.code is AdapterErrorCode.MODEL_UNAVAILABLE
    assert writes == 0


@pytest.mark.asyncio
async def test_post_operation_verification_mismatch_is_partial_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(200, json={"done": True})

    adapter = _adapter(handler)
    result = await adapter.load_model("library/model:latest")

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.PARTIAL_FAILURE


@pytest.mark.asyncio
async def test_post_operation_verification_transport_failure_is_partial_failure() -> None:
    operation_sent = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal operation_sent
        if request.url.path == "/api/tags":
            if operation_sent:
                raise httpx.ReadError("verification failed")
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        operation_sent = True
        return httpx.Response(200, json={"done": True})

    adapter = _adapter(handler)
    result = await adapter.load_model("library/model:latest")

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.PARTIAL_FAILURE


@pytest.mark.asyncio
async def test_tune_maps_only_model_ttl_to_bounded_keep_alive() -> None:
    payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [_tag("library/model:latest")]})
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True})

    adapter = _adapter(handler)
    result = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="library/model:latest",
            settings=TuneSettings(ttl_seconds=123),
        )
    )
    unsupported = await adapter.tune(
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="library/model:latest",
            settings=TuneSettings(temperature=1.0),
        )
    )

    assert result.status is OperationStatus.SUCCEEDED
    assert result.changed_fields == ("ttl_seconds",)
    assert payloads[0]["keep_alive"] == 123
    assert unsupported.status is OperationStatus.UNSUPPORTED
    assert len(payloads) == 1


class TrackingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...], *, error: bool = False) -> None:
        self.chunks = chunks
        self.error = error
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            yield chunk
        if self.error:
            raise httpx.ReadError("secret token /Users/private/model")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_stream_handles_chunked_utf8_blank_lines_tail_and_closes_resource() -> None:
    stream = TrackingStream(
        (
            b'{"message":{"content":"\xe4',
            b'\xbd\xa0\xe5\xa5\xbd"},"done":false}\r\n\r\n',
            b'{"message":{"content":""},"done":true,"done_reason":"stop",',
            b'"prompt_eval_count":2,"eval_count":1}',
        )
    )
    adapter = _adapter(lambda request: httpx.Response(200, stream=stream))

    events = [event async for event in adapter.stream_chat(_request("stream"))]

    assert [event.kind for event in events] == [
        StreamEventKind.CONTENT,
        StreamEventKind.USAGE,
        StreamEventKind.DONE,
    ]
    assert events[0].content == "你好"
    assert events[-1].finish_reason == "stop"
    assert stream.closed is True


@pytest.mark.asyncio
async def test_stream_unclosed_reasoning_and_eof_without_done_fail_closed() -> None:
    bodies = iter(
        [
            b'{"message":{"content":"visible<think>secret"},"done":false}\n'
            b'{"message":{"content":""},"done":true}\n',
            b'{"message":{"content":"visible"},"done":false}\n',
        ]
    )
    adapter = _adapter(lambda request: httpx.Response(200, content=next(bodies)))

    unclosed = [event async for event in adapter.stream_chat(_request("unclosed"))]
    eof = [event async for event in adapter.stream_chat(_request("eof"))]

    assert unclosed[-1].kind is StreamEventKind.ERROR
    assert "secret" not in "".join(event.model_dump_json() for event in unclosed)
    assert eof[-1].kind is StreamEventKind.ERROR
    assert eof[-1].emitted_content is True
    assert eof[-1].phase is StreamPhase.AFTER_CONTENT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b'{"message":{"content":"hello"}}\n',
        b'{"message":{"content":[]},"done":false}\n',
        b'{"message":{"content":""},"done":true}\n{"message":{"content":"late"},"done":false}\n',
    ],
)
async def test_stream_record_shape_and_trailing_data_fail_closed(body: bytes) -> None:
    adapter = _adapter(lambda request: httpx.Response(200, content=body))

    events = [event async for event in adapter.stream_chat(_request("bad-record"))]

    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].error is not None
    assert events[-1].error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
async def test_chat_and_stream_http_errors_are_typed_without_body_echo() -> None:
    adapter = _adapter(lambda request: httpx.Response(503, content=b"remote secret"))

    chat = await adapter.chat(_request("http-chat"))
    stream = [event async for event in adapter.stream_chat(_request("http-stream"))]

    assert chat.error is not None
    assert stream[-1].error is not None
    assert "secret" not in chat.model_dump_json()
    assert "secret" not in stream[-1].model_dump_json()


@pytest.mark.asyncio
async def test_stream_read_error_tracks_first_token_boundary_and_redacts_exception() -> None:
    streams = iter(
        [
            TrackingStream((), error=True),
            TrackingStream((b'{"message":{"content":"hello"},"done":false}\n',), error=True),
        ]
    )
    adapter = _adapter(lambda request: httpx.Response(200, stream=next(streams)))

    before = [event async for event in adapter.stream_chat(_request("before"))]
    after = [event async for event in adapter.stream_chat(_request("after"))]

    assert before[-1].error is not None
    assert before[-1].error.code is AdapterErrorCode.STREAM_INTERRUPTED
    assert before[-1].emitted_content is False
    assert after[-1].emitted_content is True
    rendered = "".join(event.model_dump_json() for event in before + after)
    assert "secret" not in rendered
    assert "/Users" not in rendered


@pytest.mark.asyncio
async def test_stream_cancellation_propagates_and_closes_resource() -> None:
    started = asyncio.Event()

    class BlockingStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            started.set()
            await asyncio.Event().wait()
            yield b"unreachable"

        async def aclose(self) -> None:
            self.closed = True

    stream = BlockingStream()
    adapter = _adapter(lambda request: httpx.Response(200, stream=stream))

    async def consume() -> None:
        async for _ in adapter.stream_chat(_request("cancel")):
            pass

    task = asyncio.create_task(consume())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert stream.closed is True


def test_ollama_adapter_satisfies_canonical_protocol_and_safe_repr() -> None:
    adapter = _adapter(lambda request: httpx.Response(500))

    assert isinstance(adapter, BackendAdapter)
    assert "ollama.invalid" not in repr(adapter)
