"""Bounded typed HTTP client for the private ``omlxcd`` Unix socket."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Never, Self, cast
from urllib.parse import quote
from uuid import uuid4

import httpx
from pydantic import JsonValue, ValidationError

from omlxc.domain import EXIT_INTERNAL, error_exit_code

from .models import DaemonEnvelope, DaemonEvent, RemoteError

JSON_MEDIA_TYPE = "application/json"
NDJSON_MEDIA_TYPE = "application/x-ndjson"
QueryParams = Mapping[str, str | int]


class DaemonClientError(RuntimeError):
    """A sanitized daemon/client failure with the stable CLI exit mapping."""

    def __init__(self, error: RemoteError, *, request_id: str) -> None:
        super().__init__(error.message)
        self.error = error
        self.request_id = request_id

    @property
    def exit_code(self) -> int:
        return error_exit_code(self.error.code)


class DaemonClient:
    """The only CLI/TUI transport to daemon-owned state and operations."""

    def __init__(
        self,
        socket_path: Path,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        request_id_factory: Callable[[], str] | None = None,
        timeout: httpx.Timeout | None = None,
        max_event_bytes: int = 65_536,
        max_stream_bytes: int = 8_388_608,
    ) -> None:
        if max_event_bytes <= 0 or max_stream_bytes < max_event_bytes:
            raise ValueError("event stream limits are invalid")
        selected_transport = transport or httpx.AsyncHTTPTransport(
            uds=str(socket_path),
            retries=0,
        )
        selected_timeout = timeout or httpx.Timeout(
            connect=2.0,
            read=30.0,
            write=30.0,
            pool=2.0,
        )
        self.socket_path = socket_path
        self._http = httpx.AsyncClient(
            transport=selected_transport,
            timeout=selected_timeout,
            base_url="http://omlxc",
            follow_redirects=False,
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._request_id_factory = request_id_factory or (lambda: uuid4().hex)
        self._max_event_bytes = max_event_bytes
        self._max_stream_bytes = max_stream_bytes

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def health(self) -> DaemonEnvelope:
        return await self._request("GET", "/api/v1/health")

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        return await self._request(
            "GET", "/api/v1/nodes", params=_page_params(after=after, limit=limit)
        )

    async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        return await self._request(
            "GET", "/api/v1/models", params=_page_params(after=after, limit=limit)
        )

    async def jobs(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        return await self._request(
            "GET", "/api/v1/jobs", params=_page_params(after=after, limit=limit)
        )

    async def job(self, job_id: str) -> DaemonEnvelope:
        return await self._request("GET", f"/api/v1/jobs/{quote(job_id, safe='')}")

    async def plan_route(self, body: Mapping[str, JsonValue]) -> DaemonEnvelope:
        return await self._request("POST", "/api/v1/routes/plan", json=dict(body))

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        return await self._model_operation("load", model_id, idempotency_key)

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        return await self._model_operation("unload", model_id, idempotency_key)

    async def cancel_job(self, job_id: str) -> DaemonEnvelope:
        return await self._request("POST", f"/api/v1/jobs/{quote(job_id, safe='')}/cancel")

    async def metrics(self) -> DaemonEnvelope:
        return await self._request("GET", "/api/v1/metrics/summary")

    async def openai_models(self) -> tuple[str, ...]:
        """Run the read-only OpenAI compatibility smoke endpoint."""
        request_id = self._new_request_id()
        response = await self._raw_request(
            "GET",
            "/openai/v1/models",
            request_id=request_id,
        )
        self._validate_identity(response, request_id)
        if _media_type(response) != JSON_MEDIA_TYPE:
            raise _malformed(request_id)
        if response.status_code != 200:
            self._raise_envelope(response, request_id)
        try:
            payload = cast(dict[str, Any], response.json())
            data = cast(list[dict[str, Any]], payload["data"])
            identifiers = tuple(str(item["id"]) for item in data)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise _malformed(request_id) from exc
        if payload.get("object") != "list" or not all(identifiers):
            raise _malformed(request_id)
        return identifiers

    async def stream_events(self, *, after: int = 0) -> AsyncIterator[DaemonEvent]:
        if after < 0:
            raise ValueError("event cursor cannot be negative")
        request_id = self._new_request_id()
        total = 0
        buffer = bytearray()
        try:
            async with self._http.stream(
                "GET",
                "/api/v1/events",
                params={"after": after},
                headers={"X-OMLXC-Request-ID": request_id},
            ) as response:
                self._validate_identity(response, request_id)
                if response.status_code < 200 or response.status_code >= 300:
                    await response.aread()
                    self._raise_envelope(response, request_id)
                if _media_type(response) != NDJSON_MEDIA_TYPE:
                    raise _malformed(request_id)
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._max_stream_bytes:
                        raise _malformed(request_id, "event stream exceeds the size limit")
                    buffer.extend(chunk)
                    while (newline := buffer.find(b"\n")) >= 0:
                        line = bytes(buffer[:newline])
                        del buffer[: newline + 1]
                        if line:
                            yield self._event(line, request_id)
                    if len(buffer) > self._max_event_bytes:
                        raise _malformed(request_id, "event record exceeds the size limit")
                if buffer:
                    yield self._event(bytes(buffer), request_id)
        except DaemonClientError:
            raise
        except httpx.TimeoutException as exc:
            raise _timeout(request_id) from exc
        except httpx.RequestError as exc:
            raise _unavailable(request_id) from exc

    async def _model_operation(
        self, operation: str, model_id: str, key: str | None
    ) -> DaemonEnvelope:
        identifier = key or self._idempotency_key(operation)
        return await self._request(
            "POST",
            f"/api/v1/models/{quote(model_id, safe='')}/{operation}",
            headers={"Idempotency-Key": identifier},
        )

    def _idempotency_key(self, operation: str) -> str:
        micros = int(self._clock().timestamp() * 1_000_000)
        return f"cli-{operation}-{micros}-{self._new_request_id()}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: QueryParams | None = None,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> DaemonEnvelope:
        request_id = self._new_request_id()
        response = await self._raw_request(
            method,
            path,
            request_id=request_id,
            params=params,
            headers=headers,
            json=json,
        )
        self._validate_identity(response, request_id)
        if _media_type(response) != JSON_MEDIA_TYPE:
            raise _malformed(request_id)
        envelope = self._parse_envelope(response, request_id)
        successful = 200 <= response.status_code < 300
        if successful and envelope.error is None:
            return envelope
        if not successful and envelope.error is not None:
            raise DaemonClientError(envelope.error, request_id=request_id)
        raise _malformed(request_id)

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        request_id: str,
        params: QueryParams | None = None,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> httpx.Response:
        merged_headers = {"X-OMLXC-Request-ID": request_id}
        if headers is not None:
            merged_headers.update(headers)
        try:
            return await self._http.request(
                method,
                path,
                params=params,
                headers=merged_headers,
                json=json,
            )
        except httpx.TimeoutException as exc:
            raise _timeout(request_id) from exc
        except httpx.RequestError as exc:
            raise _unavailable(request_id) from exc

    def _parse_envelope(self, response: httpx.Response, request_id: str) -> DaemonEnvelope:
        try:
            envelope = DaemonEnvelope.model_validate_json(response.content)
        except ValidationError as exc:
            raise _malformed(request_id) from exc
        if envelope.request_id != request_id:
            raise _malformed(request_id)
        return envelope

    def _raise_envelope(self, response: httpx.Response, request_id: str) -> Never:
        if _media_type(response) != JSON_MEDIA_TYPE:
            raise _malformed(request_id)
        envelope = self._parse_envelope(response, request_id)
        if envelope.error is None:
            raise _malformed(request_id)
        raise DaemonClientError(envelope.error, request_id=request_id)

    def _validate_identity(self, response: httpx.Response, request_id: str) -> None:
        if response.headers.get("X-OMLXC-Request-ID") != request_id:
            raise _malformed(request_id)

    def _event(self, line: bytes, stream_request_id: str) -> DaemonEvent:
        if len(line) > self._max_event_bytes:
            raise _malformed(stream_request_id, "event record exceeds the size limit")
        try:
            decoded = json.loads(line)
            if not isinstance(decoded, dict):
                raise ValueError("event is not an object")
            payload = cast(dict[str, object], decoded)
            if not payload.get("request_id"):
                payload["request_id"] = stream_request_id
            return DaemonEvent.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise _malformed(stream_request_id) from exc

    def _new_request_id(self) -> str:
        value = self._request_id_factory()
        if not value or len(value) > 64:
            raise RuntimeError("request ID factory returned an invalid value")
        return value


def _page_params(*, after: str | None, limit: int) -> dict[str, str | int]:
    if limit < 1 or limit > 100:
        raise ValueError("page limit must be between 1 and 100")
    result: dict[str, str | int] = {"limit": limit}
    if after is not None:
        result["after"] = after
    return result


def _media_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").partition(";")[0].strip().lower()


def _malformed(request_id: str, message: str = "invalid daemon response") -> DaemonClientError:
    return DaemonClientError(
        RemoteError(code="E900", message=message, retryable=False),
        request_id=request_id,
    )


def _unavailable(request_id: str) -> DaemonClientError:
    return DaemonClientError(
        RemoteError(code="E200", message="daemon is unavailable", retryable=True),
        request_id=request_id,
    )


def _timeout(request_id: str) -> DaemonClientError:
    return DaemonClientError(
        RemoteError(code="E305", message="daemon request timed out", retryable=True),
        request_id=request_id,
    )


def internal_client_error(message: str, *, request_id: str) -> DaemonClientError:
    """Build a sanitized local failure for CLI/TUI application boundaries."""
    error = RemoteError(code="E900", message=message, retryable=False)
    failure = DaemonClientError(error, request_id=request_id)
    assert failure.exit_code == EXIT_INTERNAL
    return failure
