"""Task 8 typed Unix-socket client contracts."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import httpx
import pytest


def _client_api():  # type: ignore[no-untyped-def]
    return import_module("omlxc.client")


def _request_id(request: httpx.Request) -> str:
    return request.headers["X-OMLXC-Request-ID"]


def _json_response(
    request: httpx.Request,
    *,
    data: object | None = None,
    error: dict[str, object] | None = None,
    status: int = 200,
    request_id: str | None = None,
    content_type: str = "application/json",
) -> httpx.Response:
    identifier = request_id or _request_id(request)
    payload: dict[str, object] = {"schema_version": 1, "request_id": identifier}
    if error is None:
        payload["data"] = data
    else:
        payload["error"] = error
    return httpx.Response(
        status,
        headers={
            "content-type": content_type,
            "X-OMLXC-Request-ID": identifier,
        },
        json=payload,
    )


@pytest.mark.asyncio
async def test_client_accepts_strict_success_envelope_and_closes_transport() -> None:
    api = _client_api()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _json_response(request, data={"status": "ready", "degraded": False})

    transport = httpx.MockTransport(handler)
    client = api.DaemonClient(
        Path("/unused/omlxcd.sock"),
        transport=transport,
        clock=lambda: datetime(2026, 8, 11, tzinfo=UTC),
    )
    async with client:
        envelope = await client.health()

    assert envelope.schema_version == 1
    assert envelope.request_id == _request_id(seen[0])
    assert envelope.data == {"status": "ready", "degraded": False}
    assert seen[0].url.path == "/api/v1/health"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "expected_exit"),
    [
        ("E100", 2),
        ("E200", 3),
        ("E400", 4),
        ("E305", 5),
        ("E500", 6),
        ("E700", 7),
        ("E900", 10),
    ],
)
async def test_client_maps_typed_daemon_errors_to_public_exit_codes(
    code: str, expected_exit: int
) -> None:
    api = _client_api()

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            error={"code": code, "message": "safe failure", "retryable": False},
            status=503,
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(api.DaemonClientError) as caught:
            await client.health()

    assert caught.value.exit_code == expected_exit
    assert caught.value.error.code == code
    assert "traceback" not in str(caught.value).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["content_type", "request_id", "envelope"])
async def test_client_fails_closed_on_malformed_responses(failure: str) -> None:
    api = _client_api()

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "content_type":
            return _json_response(request, data={}, content_type="text/plain")
        if failure == "request_id":
            return _json_response(request, data={}, request_id="wrong-request")
        response = _json_response(request, data={})
        payload = response.json()
        payload["error"] = {"code": "E900", "message": "ambiguous"}
        return httpx.Response(
            200,
            headers=response.headers,
            json=payload,
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(api.DaemonClientError) as caught:
            await client.health()

    assert caught.value.exit_code == 10
    assert caught.value.error.code == "E900"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception_factory", "expected_exit"),
    [
        (lambda request: httpx.ConnectError("private detail", request=request), 3),
        (lambda request: httpx.ReadTimeout("private detail", request=request), 5),
    ],
)
async def test_client_maps_socket_and_timeout_failures_without_leaking_detail(
    exception_factory: Callable[[httpx.Request], Exception], expected_exit: int
) -> None:
    api = _client_api()

    def handler(request: httpx.Request) -> httpx.Response:
        raise exception_factory(request)

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(api.DaemonClientError) as caught:
            await client.health()

    assert caught.value.exit_code == expected_exit
    assert "private detail" not in str(caught.value)


@pytest.mark.asyncio
async def test_openai_model_smoke_is_typed_and_maps_daemon_envelope_errors() -> None:
    api = _client_api()

    def success(request: httpx.Request) -> httpx.Response:
        identifier = _request_id(request)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "X-OMLXC-Request-ID": identifier,
            },
            json={
                "object": "list",
                "data": [{"id": "local/model-a", "object": "model", "owned_by": "omlxc"}],
            },
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(success)
    ) as client:
        assert await client.openai_models() == ("local/model-a",)

    def unavailable(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            error={"code": "E200", "message": "local inference unavailable"},
            status=503,
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(unavailable)
    ) as client:
        with pytest.raises(api.DaemonClientError) as caught:
            await client.openai_models()

    assert caught.value.exit_code == 3


class ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks
        self.closed = False

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_event_stream_decodes_split_ndjson_adds_request_id_and_closes() -> None:
    api = _client_api()
    first = {
        "schema_version": 1,
        "cursor": 4,
        "event_id": "event-4",
        "timestamp": "2026-08-11T00:00:00+00:00",
        "priority": "high",
        "kind": "job.running",
        "payload": {"state": "running"},
        "job_id": "job-1",
        "resource_id": None,
    }
    second = {
        "schema_version": 1,
        "cursor": 5,
        "event_id": "event-5",
        "timestamp": "2026-08-11T00:00:01+00:00",
        "priority": "normal",
        "kind": "job.succeeded",
        "payload": {"state": "succeeded"},
        "job_id": "job-1",
        "resource_id": None,
    }
    encoded = (json.dumps(first) + "\n" + json.dumps(second) + "\n").encode()
    stream = ChunkedStream((encoded[:17], encoded[17:91], encoded[91:]))

    def handler(request: httpx.Request) -> httpx.Response:
        identifier = _request_id(request)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/x-ndjson",
                "X-OMLXC-Request-ID": identifier,
            },
            stream=stream,
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"), transport=httpx.MockTransport(handler)
    ) as client:
        iterator = client.stream_events(after=3)
        events = [await anext(iterator), await anext(iterator)]
        await iterator.aclose()

    assert [event.cursor for event in events] == [4, 5]
    assert all(event.request_id for event in events)
    assert stream.closed


@pytest.mark.asyncio
async def test_event_stream_rejects_oversized_record_and_closes_response() -> None:
    api = _client_api()
    stream = ChunkedStream((b"{" + b"x" * 80 + b"}\n",))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/x-ndjson",
                "X-OMLXC-Request-ID": _request_id(request),
            },
            stream=stream,
        )

    async with api.DaemonClient(
        Path("/unused/omlxcd.sock"),
        transport=httpx.MockTransport(handler),
        max_event_bytes=64,
    ) as client:
        iterator = client.stream_events()
        with pytest.raises(api.DaemonClientError) as caught:
            await anext(iterator)

    assert caught.value.exit_code == 10
    assert stream.closed
