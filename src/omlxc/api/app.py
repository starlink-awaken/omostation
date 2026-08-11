"""Private versioned HTTP API served exclusively over a Unix socket."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Annotated, Any, Literal, cast
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import Response

from omlxc.dataplane import ExecutionErrorCode
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import (
    ChatContentBlock,
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    StreamEvent,
    StreamEventKind,
    TokenUsage,
)
from omlxc.events import EventSubscriptionClosed, RuntimeEvent
from omlxc.storage import DurableEventRecord

from .contracts import ControlService, EventService, InferenceService

SCHEMA_VERSION = 1
MAX_PAGE_SIZE = 100
MAX_BODY_BYTES = 1_048_576
MAX_TEXT_LENGTH = 100_000
MAX_DOCUMENTS = 256
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoutePlanBody(ApiModel):
    model_id: str = Field(min_length=1, max_length=512)
    profile: RouteProfile = RouteProfile.INTERACTIVE
    required_capabilities: frozenset[str] = Field(default_factory=frozenset, max_length=32)
    context_tokens: int = Field(default=0, ge=0, le=10_000_000)
    thinking_requested: bool = False


class OpenAIChatMessage(ApiModel):
    role: Literal["system", "user", "assistant"]
    content: str | tuple[ChatContentBlock, ...]


class OpenAIChatBody(ApiModel):
    model: str = Field(min_length=1, max_length=512)
    messages: tuple[OpenAIChatMessage, ...] = Field(min_length=1, max_length=256)
    stream: bool = False
    max_tokens: int = Field(default=64, gt=0, le=1_000_000)
    temperature: float = Field(default=0.0, ge=0, le=2)
    profile: RouteProfile = RouteProfile.INTERACTIVE
    thinking: bool = False
    reasoning: bool = False
    timeout_seconds: float = Field(default=120.0, gt=0, le=3600)

    @field_validator("messages")
    @classmethod
    def bound_message_text(
        cls, value: tuple[OpenAIChatMessage, ...]
    ) -> tuple[OpenAIChatMessage, ...]:
        total = 0
        for message in value:
            if isinstance(message.content, str):
                total += len(message.content)
            else:
                for block in message.content:
                    total += len(block.text) if block.type == "text" else len(block.image_url.url)
        if total > MAX_TEXT_LENGTH:
            raise ValueError("message content exceeds the size limit")
        return value


class OpenAIEmbeddingBody(ApiModel):
    model: str = Field(min_length=1, max_length=512)
    input: str | tuple[str, ...]
    profile: RouteProfile = RouteProfile.INTERACTIVE
    timeout_seconds: float = Field(default=120.0, gt=0, le=3600)

    @field_validator("input")
    @classmethod
    def bound_input(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        items = (value,) if isinstance(value, str) else value
        if not items or len(items) > 256 or any(not item for item in items):
            raise ValueError("embedding input is invalid")
        if sum(len(item) for item in items) > MAX_TEXT_LENGTH:
            raise ValueError("embedding input exceeds the size limit")
        return value


class RerankBody(ApiModel):
    model: str = Field(min_length=1, max_length=512)
    query: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    documents: tuple[str, ...] = Field(min_length=1, max_length=MAX_DOCUMENTS)

    @field_validator("documents")
    @classmethod
    def bound_documents(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not document for document in value) or sum(map(len, value)) > MAX_TEXT_LENGTH:
            raise ValueError("rerank documents are invalid")
        return value


def create_app(
    *,
    control: ControlService | None = None,
    inference: InferenceService | None = None,
    events: EventService | None = None,
    request_id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    """Create an injectable app with no implicit network or hardware access."""
    app = FastAPI(title="omlxcd", version="1", docs_url=None, redoc_url=None)
    ids = request_id_factory or (lambda: uuid4().hex)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        supplied = request.headers.get("X-OMLXC-Request-ID")
        request_id = supplied or str(ids())
        if REQUEST_ID.fullmatch(request_id) is None:
            request_id = str(ids())
            return _error_response(request_id, 400, "E100", "invalid request ID")
        request.state.request_id = request_id
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_BODY_BYTES:
                        return _error_response(
                            request_id, 413, "E100", "request body exceeds the size limit"
                        )
                except ValueError:
                    return _error_response(request_id, 400, "E100", "invalid content length")
        try:
            response = cast(Response, await call_next(request))
        except ApiError as exc:
            response = _error_response(request_id, exc.status, exc.code, exc.message)
        except Exception:
            response = _error_response(request_id, 500, "E900", "internal service error")
        response.headers["X-OMLXC-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _error: RequestValidationError) -> JSONResponse:
        return _error_response(_request_id(request), 422, "E100", "request validation failed")

    @app.get("/api/v1/health")
    async def health(request: Request) -> JSONResponse:
        data: Mapping[str, object]
        if control is None:
            data = {"status": "degraded", "degraded": True}
        else:
            data = await control.health()
        return _success(request, data)

    @app.get("/api/v1/nodes")
    async def nodes(
        request: Request,
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = MAX_PAGE_SIZE,
    ) -> JSONResponse:
        service = _require_control(control)
        return _success(request, _page(await service.list_nodes(after=after, limit=limit)))

    @app.get("/api/v1/models")
    async def models(
        request: Request,
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = MAX_PAGE_SIZE,
    ) -> JSONResponse:
        service = _require_control(control)
        return _success(request, _page(await service.list_models(after=after, limit=limit)))

    @app.post("/api/v1/routes/plan")
    async def route_plan(request: Request, body: RoutePlanBody) -> JSONResponse:
        service = _require_control(control)
        route = _route_request(_request_id(request), body)
        return _success(request, await service.plan_route(route))

    @app.get("/api/v1/jobs")
    async def jobs(
        request: Request,
        after: str | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = MAX_PAGE_SIZE,
    ) -> JSONResponse:
        service = _require_control(control)
        return _success(request, _page(await service.list_jobs(after=after, limit=limit)))

    @app.get("/api/v1/jobs/{job_id}")
    async def job(request: Request, job_id: str) -> JSONResponse:
        found = await _require_control(control).get_job(job_id)
        if found is None:
            raise ApiError(404, "E204", "job not found")
        return _success(request, found)

    @app.post("/api/v1/models/{model_id:path}/load", status_code=202)
    async def load_model(
        request: Request,
        model_id: str,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
        ],
    ) -> JSONResponse:
        return _success(
            request,
            await _require_control(control).load_model(model_id, idempotency_key=idempotency_key),
            status=202,
        )

    @app.post("/api/v1/models/{model_id:path}/unload", status_code=202)
    async def unload_model(
        request: Request,
        model_id: str,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
        ],
    ) -> JSONResponse:
        return _success(
            request,
            await _require_control(control).unload_model(model_id, idempotency_key=idempotency_key),
            status=202,
        )

    @app.post("/api/v1/jobs/{job_id}/cancel", status_code=202)
    async def cancel_job(request: Request, job_id: str) -> JSONResponse:
        found = await _require_control(control).cancel_job(job_id)
        if found is None:
            raise ApiError(404, "E204", "job not found")
        return _success(request, found, status=202)

    @app.get("/api/v1/metrics/summary")
    async def metrics(request: Request) -> JSONResponse:
        return _success(request, await _require_control(control).metrics_summary())

    @app.get("/api/v1/events")
    async def event_stream(
        request: Request,
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> StreamingResponse:
        service = _require_events(events)
        subscription = service.subscribe_events()

        async def lines() -> AsyncIterator[bytes]:
            seen: set[str] = set()
            try:
                cursor = after
                while True:
                    records = await service.replay_events(
                        after_sequence=cursor, limit=MAX_PAGE_SIZE
                    )
                    if not records:
                        break
                    for record in records:
                        seen.add(record.event_id)
                        cursor = record.sequence
                        yield _durable_line(record)
                while not await request.is_disconnected():
                    try:
                        event = await subscription.receive()
                    except EventSubscriptionClosed:
                        return
                    if event.event_id not in seen:
                        seen.add(event.event_id)
                        yield _runtime_line(event)
            finally:
                await subscription.close()

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.get("/openai/v1/models")
    async def openai_models() -> JSONResponse:
        service = _require_inference(inference)
        identifiers = await service.list_openai_models()
        return JSONResponse(
            {
                "object": "list",
                "data": [
                    {"id": identifier, "object": "model", "owned_by": "omlxc"}
                    for identifier in identifiers
                ],
            }
        )

    @app.post("/openai/v1/chat/completions")
    async def openai_chat(request: Request, body: OpenAIChatBody) -> Response:
        request_id = _request_id(request)
        if body.thinking or body.reasoning:
            return _openai_error(request_id, 400, "unsupported_feature")
        service = _require_inference(inference)
        route = RouteRequest(
            request_id=request_id,
            model_id=body.model,
            profile=body.profile,
            required_capabilities=frozenset({"chat", *(("streaming",) if body.stream else ())}),
            context_tokens=0,
        )
        chat_request = ChatRequest(
            request_id=request_id,
            model=body.model,
            messages=tuple(
                ChatMessage(role=message.role, content=message.content) for message in body.messages
            ),
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
        if not body.stream:
            execution = await service.chat(route, chat_request, deadline=body.timeout_seconds)
            if not execution.success or execution.result is None:
                return _execution_error(request_id, execution.error)
            result = execution.result
            return JSONResponse(
                {
                    "id": f"chatcmpl-{request_id}",
                    "object": "chat.completion",
                    "model": body.model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": result.content},
                            "finish_reason": result.finish_reason or "stop",
                        }
                    ],
                    "usage": _usage(result.usage),
                },
                headers={"X-OMLXC-Request-ID": request_id},
            )
        source = service.stream_chat(route, chat_request, deadline=body.timeout_seconds)
        try:
            first = await anext(source)
        except StopAsyncIteration:
            return _openai_error(request_id, 503, "backend_unavailable")
        if first.kind is StreamEventKind.ERROR and not first.emitted_content:
            await _close_iterator(source)
            return _openai_error(request_id, 503, "backend_unavailable")

        async def sse() -> AsyncIterator[bytes]:
            try:
                yield _sse_event(request_id, body.model, first)
                if first.kind is StreamEventKind.ERROR:
                    return
                async for event in source:
                    yield _sse_event(request_id, body.model, event)
                    if event.kind in {StreamEventKind.ERROR, StreamEventKind.DONE}:
                        return
            finally:
                await _close_iterator(source)

        headers = {
            "X-OMLXC-Request-ID": request_id,
            "X-OMLXC-Profile": body.profile.value,
        }
        if first.placement_id is not None:
            headers["X-OMLXC-Placement"] = first.placement_id
        if first.backend_id is not None:
            headers["X-OMLXC-Backend"] = first.backend_id
        return StreamingResponse(sse(), media_type="text/event-stream", headers=headers)

    @app.post("/openai/v1/embeddings")
    async def embeddings(request: Request, body: OpenAIEmbeddingBody) -> JSONResponse:
        request_id = _request_id(request)
        service = _require_inference(inference)
        route = RouteRequest(
            request_id=request_id,
            model_id=body.model,
            profile=body.profile,
            required_capabilities=frozenset({"embedding"}),
            context_tokens=0,
        )
        embedding_request = EmbeddingRequest(
            request_id=request_id, model=body.model, input=body.input
        )
        execution = await service.embed(route, embedding_request, deadline=body.timeout_seconds)
        if execution.error is not None:
            return _execution_error(request_id, execution.error)
        return JSONResponse(
            {
                "object": "list",
                "model": body.model,
                "data": [
                    {"object": "embedding", "embedding": list(vector), "index": index}
                    for index, vector in enumerate(execution.embeddings)
                ],
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            }
        )

    @app.post("/api/v1/rerank")
    async def rerank(request: Request, body: RerankBody) -> JSONResponse:
        request_id = _request_id(request)
        execution = await _require_inference(inference).rerank(
            request_id=request_id, query=body.query, documents=body.documents
        )
        if execution.error is not None:
            raise ApiError(503, "E300", "local rerank failed")
        return _success(
            request,
            [{"index": item.index, "relevance_score": item.score} for item in execution.items],
        )

    return app


def _request_id(request: Request) -> str:
    return cast(str, request.state.request_id)


def _success(request: Request, data: object, *, status: int = 200) -> JSONResponse:
    return JSONResponse(
        {"schema_version": SCHEMA_VERSION, "request_id": _request_id(request), "data": _json(data)},
        status_code=status,
    )


def _error_response(request_id: str, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "error": {"code": code, "message": message, "retryable": False},
        },
        status_code=status,
        headers={"X-OMLXC-Request-ID": request_id},
    )


def _openai_error(request_id: str, status: int, error_type: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": "local inference failed", "type": error_type, "code": error_type}},
        status_code=status,
        headers={"X-OMLXC-Request-ID": request_id},
    )


def _execution_error(request_id: str, error: Any) -> JSONResponse:
    code = getattr(error, "code", ExecutionErrorCode.BACKEND_FAILURE)
    if code in {ExecutionErrorCode.NO_CANDIDATE, ExecutionErrorCode.NO_CAPACITY}:
        return _openai_error(request_id, 409, "insufficient_capacity")
    if code is ExecutionErrorCode.TIMEOUT:
        return _openai_error(request_id, 504, "timeout")
    if code is ExecutionErrorCode.UNSUPPORTED:
        return _openai_error(request_id, 400, "unsupported_feature")
    return _openai_error(request_id, 503, "backend_unavailable")


def _require_control(service: ControlService | None) -> ControlService:
    if service is None:
        raise ApiError(503, "E200", "daemon runtime unavailable")
    return service


def _require_inference(service: InferenceService | None) -> InferenceService:
    if service is None:
        raise ApiError(503, "E200", "local inference unavailable")
    return service


def _require_events(service: EventService | None) -> EventService:
    if service is None:
        raise ApiError(503, "E200", "event service unavailable")
    return service


def _route_request(request_id: str, body: RoutePlanBody) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        model_id=body.model_id,
        profile=body.profile,
        required_capabilities=body.required_capabilities,
        context_tokens=body.context_tokens,
        thinking_requested=body.thinking_requested,
    )


def _page(items: Sequence[object]) -> dict[str, object]:
    return {"items": list(items), "next_cursor": getattr(items[-1], "id", None) if items else None}


def _json(value: object) -> object:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _json(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(Sequence[object], value)
        return [_json(item) for item in sequence]
    return value


def _usage(usage: TokenUsage | None) -> dict[str, int]:
    current = usage or TokenUsage()
    return current.model_dump(mode="json")


def _sse_event(request_id: str, model: str, event: StreamEvent) -> bytes:
    if event.kind is StreamEventKind.DONE:
        return b"data: [DONE]\n\n"
    if event.kind is StreamEventKind.ERROR:
        payload: dict[str, object] = {
            "error": {
                "message": "local stream failed",
                "type": "stream_error",
                "code": "stream_error",
            }
        }
    elif event.kind is StreamEventKind.USAGE:
        payload = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [],
            "usage": _usage(event.usage),
        }
    else:
        payload = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {"content": event.content}, "finish_reason": None}],
        }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return f"data: {encoded}\n\n".encode()


async def _close_iterator(iterator: AsyncIterator[object]) -> None:
    close = getattr(iterator, "aclose", None)
    if close is not None:
        await close()


def _durable_line(record: DurableEventRecord) -> bytes:
    payload = {
        "schema_version": record.schema_version,
        "cursor": record.sequence,
        "event_id": record.event_id,
        "timestamp": record.observed_at.isoformat(),
        "priority": record.priority,
        "kind": record.kind,
        "payload": json.loads(record.payload_json),
        "job_id": record.job_id,
        "resource_id": record.resource_id,
    }
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def _runtime_line(event: RuntimeEvent) -> bytes:
    payload = {
        "schema_version": event.schema_version,
        "cursor": None,
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat(),
        "priority": event.priority.value,
        "kind": event.kind,
        "payload": json.loads(event.payload_json()),
        "request_id": event.request_id,
        "job_id": event.job_id,
        "resource_id": event.resource_id,
    }
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()
