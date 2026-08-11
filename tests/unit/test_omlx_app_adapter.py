"""oMLX App HTTP mapping, safety, and failure contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import anyio
import httpx
import pytest
from pydantic import ValidationError

from omlxc.domain.protocols import (
    AdapterErrorCode,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    ImageContentBlock,
    ImageURL,
    OperationStatus,
    StreamEventKind,
    TextContentBlock,
    TuneRequest,
    TuneScope,
    TuneSettings,
)


def make_adapter(
    handler: httpx.AsyncBaseTransport | httpx.MockTransport,
    *,
    clock: object | None = None,
) -> object:
    from omlxc.adapters.omlx_app import OmlxAppAdapter

    arguments: dict[str, object] = {
        "backend_id": "mbp-omlx",
        "base_url": "http://omlx.invalid",
        "probe_model_id": "model-a",
        "transport": handler,
    }
    if clock is not None:
        arguments["clock"] = clock
    return OmlxAppAdapter(**arguments)


def chat_request(*, content: str = "hello") -> ChatRequest:
    return ChatRequest(
        request_id="req-chat",
        model="model-a",
        messages=(ChatMessage(role="user", content=content),),
    )


@pytest.mark.asyncio
async def test_injected_client_is_used_and_not_closed_by_adapter() -> None:
    from omlxc.adapters.omlx_app import OmlxAppAdapter

    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OmlxAppAdapter(
        backend_id="mbp-omlx",
        base_url="http://omlx.invalid",
        client=client,
    )

    result = await adapter.chat(chat_request())
    await adapter.aclose()

    assert result.content == "ok"
    assert calls == 1
    assert client.is_closed is False
    await client.aclose()


@pytest.mark.asyncio
async def test_owned_client_is_closed_by_adapter() -> None:
    from omlxc.adapters.omlx_app import OmlxAppAdapter

    adapter = OmlxAppAdapter(
        backend_id="mbp-omlx",
        base_url="http://omlx.invalid",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
    )

    await adapter.aclose()

    with pytest.raises(RuntimeError, match="closed"):
        await adapter.chat(chat_request())


def test_adapter_rejects_invalid_base_url_and_ambiguous_http_injection() -> None:
    from omlxc.adapters.omlx_app import OmlxAppAdapter

    with pytest.raises(ValueError, match="http"):
        OmlxAppAdapter(backend_id="mbp-omlx", base_url="file:///tmp/socket")

    client = httpx.AsyncClient()
    transport = httpx.MockTransport(lambda _request: httpx.Response(200))
    with pytest.raises(ValueError, match="mutually exclusive"):
        OmlxAppAdapter(
            backend_id="mbp-omlx",
            client=client,
            transport=transport,
        )
    anyio.run(client.aclose)


@pytest.mark.asyncio
async def test_discovery_uses_injected_clock_and_four_bounded_timeout_components() -> None:
    requests: list[httpx.Request] = []
    observed_at = datetime(2026, 8, 11, 12, 34, tzinfo=UTC)

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"status": "running", "version": "0.5.7"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": []})
        if request.url.path == "/v1/models/status":
            return httpx.Response(404)
        raise AssertionError(request.url.path)

    adapter = make_adapter(httpx.MockTransport(handler), clock=lambda: observed_at)

    snapshot = await adapter.discover()  # type: ignore[attr-defined]

    assert snapshot.observed_at == observed_at
    timeout = requests[0].extensions["timeout"]
    assert timeout == {"connect": 2.0, "read": 30.0, "write": 10.0, "pool": 2.0}
    assert all(value is not None and 0 < value <= 30 for value in timeout.values())


@pytest.mark.asyncio
async def test_cancel_scope_propagates_through_http_calls() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        await anyio.sleep_forever()
        raise AssertionError("unreachable")

    adapter = make_adapter(httpx.MockTransport(handler))

    with pytest.raises(TimeoutError):
        with anyio.fail_after(0.01):
            await adapter.list_models()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unreachable_discovery_is_typed_and_not_ready() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic refusal", request=request)

    adapter = make_adapter(httpx.MockTransport(handler))

    snapshot = await adapter.discover()  # type: ignore[attr-defined]

    assert snapshot.reachable is False
    assert snapshot.generation_ready is False
    assert snapshot.errors[0].code is AdapterErrorCode.UNREACHABLE


def test_vision_accepts_openai_image_blocks_and_rejects_unsafe_shapes() -> None:
    image = ImageContentBlock(
        image_url=ImageURL(url="data:image/png;base64,aGVsbG8=", detail="low")
    )
    message = ChatMessage(
        role="user",
        content=(TextContentBlock(text="describe"), image),
    )

    assert message.model_dump(mode="json")["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,aGVsbG8=", "detail": "low"},
    }
    with pytest.raises(ValidationError, match="base64"):
        ImageURL(url="data:image/png;base64,not-base64!")
    with pytest.raises(ValidationError, match="userinfo"):
        ImageURL(url="https://operator:secret@example.invalid/image.png")
    with pytest.raises(ValidationError, match="http"):
        ImageURL(url="file:///Users/operator/private.png")


@pytest.mark.asyncio
async def test_vision_payload_is_openai_compatible_and_thinking_is_forced_off() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "cat"}, "finish_reason": "stop"}]},
        )

    adapter = make_adapter(httpx.MockTransport(handler))
    request = ChatRequest(
        request_id="req-vision",
        model="vision-a",
        messages=(
            ChatMessage(
                role="user",
                content=(
                    TextContentBlock(text="describe"),
                    ImageContentBlock(image_url=ImageURL(url="https://example.invalid/image.png")),
                ),
            ),
        ),
    )

    result = await adapter.chat(request)  # type: ignore[attr-defined]
    payload = captured[0].read().decode("utf-8")

    assert result.content == "cat"
    assert '"type":"image_url"' in payload
    assert '"url":"https://example.invalid/image.png"' in payload
    assert '"enable_thinking":false' in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 405, 501])
async def test_lifecycle_unsupported_endpoints_return_typed_results(status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/v1/models", "/v1/models/status"}:
            return httpx.Response(200, json={"data": [{"id": "model-a", "loaded": False}]})
        return httpx.Response(status, json={"detail": "not supported"})

    adapter = make_adapter(httpx.MockTransport(handler))

    result = await adapter.load_model("model-a")  # type: ignore[attr-defined]

    assert result.status is OperationStatus.UNSUPPORTED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED


@pytest.mark.asyncio
async def test_lifecycle_missing_model_returns_typed_unavailable_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    adapter = make_adapter(httpx.MockTransport(handler))

    result = await adapter.load_model("missing")  # type: ignore[attr-defined]

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.MODEL_UNAVAILABLE


@pytest.mark.asyncio
async def test_load_and_unload_use_observed_legacy_routes_and_idempotency_header() -> None:
    requests: list[httpx.Request] = []
    loaded = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal loaded
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "model-a", "loaded": loaded}]})
        if request.url.path == "/v1/models/status":
            return httpx.Response(200, json={"models": []})
        if request.url.path == "/v1/models/model-a/load":
            loaded = True
            return httpx.Response(200, json={"status": "loaded"})
        if request.url.path == "/v1/models/model-a/unload":
            loaded = False
            return httpx.Response(200, json={"status": "unloaded"})
        raise AssertionError(request.url.path)

    adapter = make_adapter(httpx.MockTransport(handler))

    loaded_result = await adapter.load_model(  # type: ignore[attr-defined]
        "model-a", idempotency_key="idem-model"
    )
    unloaded_result = await adapter.unload_model(  # type: ignore[attr-defined]
        "model-a", idempotency_key="idem-model"
    )

    writes = [request for request in requests if request.method == "POST"]
    assert [request.url.path for request in writes] == [
        "/v1/models/model-a/load",
        "/v1/models/model-a/unload",
    ]
    assert all(request.headers["idempotency-key"] == "idem-model" for request in writes)
    assert loaded_result.status is OperationStatus.SUCCEEDED
    assert unloaded_result.status is OperationStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_tune_is_idempotent_and_uses_observed_global_and_model_routes() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/admin/api/global-settings" and request.method == "GET":
            return httpx.Response(200, json={"max_tokens": 64})
        if request.url.path == "/admin/api/models" and request.method == "GET":
            return httpx.Response(
                200,
                json={"models": [{"id": "model-a", "settings": {"max_tokens": 32}}]},
            )
        return httpx.Response(200, json={"status": "ok"})

    adapter = make_adapter(httpx.MockTransport(handler))

    unchanged = await adapter.tune(  # type: ignore[attr-defined]
        TuneRequest(scope=TuneScope.GLOBAL, settings=TuneSettings(max_tokens=64))
    )
    changed = await adapter.tune(  # type: ignore[attr-defined]
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="model-a",
            settings=TuneSettings(max_tokens=64),
            idempotency_key="idem-tune",
        )
    )

    writes = [request for request in requests if request.method in {"POST", "PUT"}]
    assert unchanged.status is OperationStatus.UNCHANGED
    assert changed.changed_fields == ("max_tokens",)
    assert [request.method for request in writes] == ["PUT"]
    assert writes[0].url.path == "/admin/api/models/model-a/settings"
    assert writes[0].headers["idempotency-key"] == "idem-tune"


@pytest.mark.asyncio
async def test_tune_unsupported_endpoint_returns_typed_result() -> None:
    adapter = make_adapter(
        httpx.MockTransport(lambda _request: httpx.Response(404, json={"detail": "missing"}))
    )

    result = await adapter.tune(  # type: ignore[attr-defined]
        TuneRequest(scope=TuneScope.GLOBAL, settings=TuneSettings(max_tokens=64))
    )

    assert result.status is OperationStatus.UNSUPPORTED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.UNSUPPORTED


@pytest.mark.asyncio
async def test_tune_missing_model_returns_typed_unavailable_result() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    adapter = make_adapter(httpx.MockTransport(handler))

    result = await adapter.tune(  # type: ignore[attr-defined]
        TuneRequest(
            scope=TuneScope.MODEL,
            model_id="missing",
            settings=TuneSettings(max_tokens=64),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.MODEL_UNAVAILABLE


@pytest.mark.asyncio
async def test_embedding_success_is_typed() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    adapter = make_adapter(httpx.MockTransport(handler))

    result = await adapter.embed(  # type: ignore[attr-defined]
        EmbeddingRequest(request_id="req-embed", model="embed-a", input=("hello",))
    )

    assert result.status is OperationStatus.SUCCEEDED
    assert result.embeddings == ((0.1, 0.2),)
    assert result.usage is not None
    assert result.usage.total_tokens == 2


@pytest.mark.asyncio
async def test_embedding_rejects_invalid_vector_shape_as_typed_bad_response() -> None:
    adapter = make_adapter(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"index": 0, "embedding": [0.1, "invalid"]}]},
            )
        )
    )

    result = await adapter.embed(  # type: ignore[attr-defined]
        EmbeddingRequest(request_id="req-embed", model="embed-a", input="hello")
    )

    assert result.status is OperationStatus.FAILED
    assert result.error is not None
    assert result.error.code is AdapterErrorCode.BAD_RESPONSE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(200, content=b""), AdapterErrorCode.BAD_RESPONSE),
        (httpx.Response(200, content=b"not-json"), AdapterErrorCode.BAD_RESPONSE),
        (httpx.Response(500, json={"detail": "boom"}), AdapterErrorCode.BAD_RESPONSE),
    ],
)
async def test_non_stream_chat_maps_empty_non_json_and_http_errors(
    response: httpx.Response, code: AdapterErrorCode
) -> None:
    adapter = make_adapter(httpx.MockTransport(lambda _request: response))

    result = await adapter.chat(chat_request())  # type: ignore[attr-defined]

    assert result.success is False
    assert result.error is not None
    assert result.error.code is code


@pytest.mark.asyncio
async def test_http_timeout_is_structured_without_swallowing_cancellation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    adapter = make_adapter(httpx.MockTransport(handler))

    result = await adapter.chat(chat_request())  # type: ignore[attr-defined]

    assert result.error is not None
    assert result.error.code is AdapterErrorCode.TIMEOUT
    assert result.error.retryable is True


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        raise httpx.ReadError("synthetic disconnect")


@pytest.mark.asyncio
async def test_stream_http_error_is_typed_before_any_content() -> None:
    adapter = make_adapter(
        httpx.MockTransport(lambda _request: httpx.Response(503, json={"detail": "down"}))
    )

    events = [event async for event in adapter.stream_chat(chat_request())]  # type: ignore[attr-defined]

    assert len(events) == 1
    assert events[0].kind is StreamEventKind.ERROR
    assert events[0].emitted_content is False
    assert events[0].error is not None
    assert events[0].error.http_status == 503


@pytest.mark.asyncio
async def test_stream_filters_reasoning_tags_even_when_split_across_chunks() -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"<thi"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"nk>hidden"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"</th"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"ink>visible"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    adapter = make_adapter(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                content=body,
                headers={"content-type": "text/event-stream"},
            )
        )
    )

    events = [event async for event in adapter.stream_chat(chat_request())]  # type: ignore[attr-defined]
    rendered = "".join(event.content for event in events)

    assert rendered == "visible"
    assert "hidden" not in rendered


def test_adapter_redaction_is_recursive_and_exception_repr_is_safe() -> None:
    from omlxc.adapters.security import AdapterFailure, redact_adapter_data

    sensitive = {
        "Authorization": "Bearer synthetic-secret",
        "nested": [
            {"apiKey": "synthetic-key"},
            "https://operator:synthetic-password@example.invalid/path",
            "/Users/operator/models/private-model",
            "/Volumes/Private/models/model-a",
        ],
    }

    redacted = redact_adapter_data(sensitive)
    failure = AdapterFailure.from_detail(
        code=AdapterErrorCode.BAD_RESPONSE,
        message="backend response invalid",
        detail=sensitive,
    )
    rendered = f"{redacted!r} {failure!s} {failure!r}"

    for secret in (
        "synthetic-secret",
        "synthetic-key",
        "synthetic-password",
        "/Users/operator/models/private-model",
        "/Volumes/Private/models/model-a",
    ):
        assert secret not in rendered
    assert "[REDACTED]" in rendered


def test_adapter_rejects_base_url_userinfo_without_echoing_credentials() -> None:
    from omlxc.adapters.omlx_app import OmlxAppAdapter

    with pytest.raises(ValueError) as captured:
        OmlxAppAdapter(
            backend_id="mbp-omlx",
            base_url="https://operator:synthetic-password@example.invalid",
        )

    assert "synthetic-password" not in str(captured.value)
