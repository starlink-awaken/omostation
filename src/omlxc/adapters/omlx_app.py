"""Async HTTP adapter for the local oMLX App API."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from typing import cast
from urllib.parse import quote, urlsplit

import httpx

from omlxc.domain.protocols import (
    AdapterCapability,
    AdapterError,
    AdapterErrorCode,
    CapabilitySnapshot,
    ChatMessage,
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
    TuneScope,
)

from .security import AdapterFailure

_UNSUPPORTED_STATUSES = frozenset({404, 405, 501})
_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_TIMEOUT = httpx.Timeout(connect=2.0, read=30.0, write=10.0, pool=2.0)


def _object_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _object_list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return cast(list[object], value)


def _partial_tag_length(value: str, tag: str) -> int:
    lowered = value.lower()
    for length in range(min(len(value), len(tag) - 1), 0, -1):
        if lowered[-length:] == tag[:length]:
            return length
    return 0


class _ReasoningFilter:
    """Remove think blocks without leaking tags split across SSE chunks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_think = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        output: list[str] = []
        while self._buffer:
            lowered = self._buffer.lower()
            if self._inside_think:
                close_at = lowered.find("</think>")
                if close_at >= 0:
                    self._buffer = self._buffer[close_at + len("</think>") :]
                    self._inside_think = False
                    continue
                keep = _partial_tag_length(self._buffer, "</think>")
                self._buffer = self._buffer[-keep:] if keep else ""
                return "".join(output)

            open_at = lowered.find("<think")
            if open_at >= 0:
                output.append(self._buffer[:open_at])
                end_at = self._buffer.find(">", open_at)
                if end_at < 0:
                    self._buffer = self._buffer[open_at:]
                    return "".join(output)
                self._buffer = self._buffer[end_at + 1 :]
                self._inside_think = True
                continue

            keep = _partial_tag_length(self._buffer, "<think")
            if keep:
                output.append(self._buffer[:-keep])
                self._buffer = self._buffer[-keep:]
            else:
                output.append(self._buffer)
                self._buffer = ""
            return "".join(output)
        return "".join(output)

    def finish(self) -> str:
        if self._inside_think:
            self._buffer = ""
            return ""
        remaining = self._buffer
        self._buffer = ""
        return remaining


class OmlxAppAdapter:
    """Map the observed oMLX App 0.5.x HTTP surface to shared contracts."""

    def __init__(
        self,
        *,
        backend_id: str,
        base_url: str = "http://127.0.0.1:8000",
        probe_model_id: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must use http or https")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not contain userinfo")
        if client is not None and transport is not None:
            raise ValueError("client and transport are mutually exclusive")
        self._backend_id = backend_id
        self._base_url = httpx.URL(base_url.rstrip("/") + "/")
        self._probe_model_id = probe_model_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(transport=transport)
        self._timeout = _TIMEOUT

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _url(self, path: str) -> httpx.URL:
        return self._base_url.join(path.removeprefix("/"))

    async def _send(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(
                method,
                self._url(path),
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.TIMEOUT,
                message="oMLX App request timed out",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc
        except httpx.TransportError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.UNREACHABLE,
                message="oMLX App transport is unreachable",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc

    @staticmethod
    def _json_object(response: httpx.Response, *, endpoint: str) -> dict[str, object]:
        if not response.content:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App returned an empty response",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        try:
            parsed = cast(object, json.loads(response.content))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App returned non-JSON data",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            ) from exc
        if not isinstance(parsed, dict):
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App returned an unexpected JSON shape",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        return cast(dict[str, object], parsed)

    @staticmethod
    def _http_error(response: httpx.Response, *, endpoint: str) -> AdapterFailure:
        code = (
            AdapterErrorCode.UNSUPPORTED
            if response.status_code in _UNSUPPORTED_STATUSES
            else AdapterErrorCode.BAD_RESPONSE
        )
        return AdapterFailure.from_detail(
            code=code,
            message=(
                "oMLX App endpoint is unsupported"
                if code is AdapterErrorCode.UNSUPPORTED
                else "oMLX App returned an HTTP error"
            ),
            detail={},
            retryable=response.status_code >= 500,
            http_status=response.status_code,
            endpoint=endpoint,
        )

    async def discover(self) -> CapabilitySnapshot:
        observed_at = self._clock()
        errors: list[AdapterError] = []
        try:
            status_response = await self._send("GET", "/api/status")
        except AdapterFailure as failure:
            return CapabilitySnapshot(
                backend_id=self._backend_id,
                reachable=False,
                compatible=False,
                model_available=False,
                generation_ready=False,
                observed_at=observed_at,
                errors=(failure.error,),
            )

        reachable = True
        protocol_version: str | None = None
        if status_response.is_success:
            try:
                status = self._json_object(status_response, endpoint="/api/status")
                raw_version = status.get("version")
                protocol_version = raw_version if isinstance(raw_version, str) else None
            except AdapterFailure as failure:
                errors.append(failure.error)

        try:
            models = await self.list_models()
            compatible = True
        except AdapterFailure as failure:
            errors.append(failure.error)
            models = ()
            compatible = False

        model_available = bool(models)
        generation_ready = False
        probe_id = self._probe_model_id
        if probe_id is None:
            probe_id = next((model.id for model in models if model.loaded), None)
        loaded_ids = {model.id for model in models if model.loaded}
        if compatible and probe_id is not None and probe_id in loaded_ids:
            probe = await self.chat(
                ChatRequest(
                    request_id="omlx-readiness-probe",
                    model=probe_id,
                    messages=(ChatMessage(role="user", content="Reply O only"),),
                    max_tokens=1,
                    temperature=0.0,
                )
            )
            generation_ready = probe.success and bool(probe.content)
            if probe.error is not None:
                errors.append(probe.error)

        capabilities: set[AdapterCapability] = set()
        if compatible:
            capabilities.update({AdapterCapability.CHAT, AdapterCapability.STREAMING})
        return CapabilitySnapshot(
            backend_id=self._backend_id,
            reachable=reachable,
            compatible=compatible,
            model_available=model_available,
            generation_ready=generation_ready,
            observed_at=observed_at,
            protocol_version=protocol_version,
            capabilities=frozenset(capabilities),
            errors=tuple(errors),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        endpoint = "/v1/models"
        response = await self._send("GET", endpoint)
        if not response.is_success:
            raise self._http_error(response, endpoint=endpoint)
        document = self._json_object(response, endpoint=endpoint)
        raw_models = document.get("data")
        if not isinstance(raw_models, list):
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.INCOMPATIBLE,
                message="oMLX App model inventory is incompatible",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )

        status_by_id: dict[str, bool] = {}
        status_response = await self._send("GET", "/v1/models/status")
        if status_response.is_success and status_response.content:
            status_document = self._json_object(status_response, endpoint="/v1/models/status")
            status_models = _object_list(status_document.get("models"))
            if status_models is not None:
                for raw_item in status_models:
                    item = _object_mapping(raw_item)
                    if item is None:
                        continue
                    model_id = item.get("id")
                    loaded = item.get("loaded")
                    if isinstance(model_id, str) and isinstance(loaded, bool):
                        status_by_id[model_id] = loaded

        models: list[ModelRuntime] = []
        typed_models = cast(list[object], raw_models)
        for raw_item in typed_models:
            item = _object_mapping(raw_item)
            if item is None:
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            raw_loaded = status_by_id.get(model_id, item.get("loaded", False))
            loaded = raw_loaded if isinstance(raw_loaded, bool) else False
            display_name = item.get("name")
            context_limit = item.get("context_limit")
            models.append(
                ModelRuntime(
                    id=model_id,
                    display_name=display_name if isinstance(display_name, str) else None,
                    state=(ModelRuntimeState.LOADED if loaded else ModelRuntimeState.AVAILABLE),
                    loaded=loaded,
                    context_limit=context_limit if isinstance(context_limit, int) else None,
                )
            )
        return tuple(models)

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return await self._change_model_state(model_id, load=True, idempotency_key=idempotency_key)

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult:
        return await self._change_model_state(model_id, load=False, idempotency_key=idempotency_key)

    async def _change_model_state(
        self, model_id: str, *, load: bool, idempotency_key: str | None
    ) -> LifecycleResult:
        models = await self.list_models()
        model = next((item for item in models if item.id == model_id), None)
        if model is None:
            error = AdapterError(
                code=AdapterErrorCode.MODEL_UNAVAILABLE,
                message="model is not present in the oMLX App inventory",
            )
            return LifecycleResult(
                model_id=model_id,
                status=OperationStatus.FAILED,
                changed=False,
                idempotency_key=idempotency_key,
                error=error,
            )
        if model.loaded is load:
            return LifecycleResult(
                model_id=model_id,
                status=OperationStatus.UNCHANGED,
                changed=False,
                idempotency_key=idempotency_key,
            )

        action = "load" if load else "unload"
        endpoint = f"/v1/models/{quote(model_id, safe='')}/{action}"
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        try:
            response = await self._send("POST", endpoint, payload={}, headers=headers)
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
        except AdapterFailure as failure:
            status = (
                OperationStatus.UNSUPPORTED
                if failure.error.code is AdapterErrorCode.UNSUPPORTED
                else OperationStatus.FAILED
            )
            return LifecycleResult(
                model_id=model_id,
                status=status,
                changed=False,
                idempotency_key=idempotency_key,
                error=failure.error,
            )
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    async def tune(self, request: TuneRequest) -> TuneResult:
        if request.scope is TuneScope.GLOBAL:
            read_endpoint = write_endpoint = "/admin/api/global-settings"
            write_method = "POST"
            current_response = await self._send("GET", read_endpoint)
            current = (
                self._json_object(current_response, endpoint=read_endpoint)
                if current_response.is_success
                else None
            )
        else:
            read_endpoint = "/admin/api/models"
            model_id = cast(str, request.model_id)
            write_endpoint = f"/admin/api/models/{quote(model_id, safe='')}/settings"
            write_method = "PUT"
            current_response = await self._send("GET", read_endpoint)
            current = None
            if current_response.is_success:
                catalog = self._json_object(current_response, endpoint=read_endpoint)
                raw_models = _object_list(catalog.get("models"))
                if raw_models is not None:
                    for raw_item in raw_models:
                        item = _object_mapping(raw_item)
                        if item is not None and item.get("id") == model_id:
                            settings = item.get("settings")
                            current = (
                                dict(settings_mapping)
                                if (settings_mapping := _object_mapping(settings)) is not None
                                else {}
                            )
                            break

        if not current_response.is_success:
            failure = self._http_error(current_response, endpoint=read_endpoint)
            return self._tune_failure(request, failure.error)
        if current is None:
            error = AdapterError(
                code=AdapterErrorCode.MODEL_UNAVAILABLE,
                message="model tuning target is unavailable",
            )
            return self._tune_failure(request, error)

        target = cast(dict[str, object], request.settings.model_dump(exclude_unset=True))
        changes = {key: value for key, value in target.items() if current.get(key) != value}
        if not changes:
            return TuneResult(
                scope=request.scope,
                model_id=request.model_id,
                status=OperationStatus.UNCHANGED,
                idempotency_key=request.idempotency_key,
            )

        headers = {"Idempotency-Key": request.idempotency_key} if request.idempotency_key else None
        try:
            response = await self._send(
                write_method, write_endpoint, payload=changes, headers=headers
            )
            if not response.is_success:
                raise self._http_error(response, endpoint=write_endpoint)
        except AdapterFailure as failure:
            return self._tune_failure(request, failure.error)
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=OperationStatus.SUCCEEDED,
            changed_fields=tuple(sorted(changes)),
            idempotency_key=request.idempotency_key,
        )

    @staticmethod
    def _tune_failure(request: TuneRequest, error: AdapterError) -> TuneResult:
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=(
                OperationStatus.UNSUPPORTED
                if error.code is AdapterErrorCode.UNSUPPORTED
                else OperationStatus.FAILED
            ),
            idempotency_key=request.idempotency_key,
            error=error,
        )

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict[str, object]:
        return cast(dict[str, object], message.model_dump(mode="json"))

    def _chat_payload(self, request: ChatRequest, *, stream: bool) -> dict[str, object]:
        return {
            "model": request.model,
            "messages": [self._message_payload(message) for message in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
            "enable_thinking": False,
            "thinking_budget_enabled": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }

    async def chat(self, request: ChatRequest) -> ChatResult:
        endpoint = "/v1/chat/completions"
        try:
            response = await self._send(
                "POST", endpoint, payload=self._chat_payload(request, stream=False)
            )
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            content, finish_reason = self._parse_chat_choice(document)
            usage = self._parse_usage(document.get("usage"))
        except AdapterFailure as failure:
            return ChatResult(
                request_id=request.request_id,
                success=False,
                error=failure.error,
            )
        return ChatResult(
            request_id=request.request_id,
            success=True,
            content=self._strip_reasoning(content),
            finish_reason=finish_reason,
            usage=usage,
        )

    @staticmethod
    def _parse_chat_choice(document: Mapping[str, object]) -> tuple[str, str | None]:
        choices = document.get("choices")
        typed_choices = _object_list(choices)
        if not typed_choices:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App chat response has no choice",
                detail={},
            )
        choice = _object_mapping(typed_choices[0])
        if choice is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App chat response has no choice",
                detail={},
            )
        message = _object_mapping(choice.get("message"))
        if message is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App chat response has no message",
                detail={},
            )
        content = message.get("content")
        if not isinstance(content, str):
            content = ""
        finish_reason = choice.get("finish_reason")
        return content, finish_reason if isinstance(finish_reason, str) else None

    @staticmethod
    def _strip_reasoning(content: str) -> str:
        filtered = _ReasoningFilter()
        return filtered.feed(_THINK_BLOCK.sub("", content)) + filtered.finish()

    @staticmethod
    def _parse_usage(value: object) -> TokenUsage | None:
        mapping = _object_mapping(value)
        if mapping is None:
            return None

        def count(key: str) -> int:
            raw = mapping.get(key, 0)
            return raw if isinstance(raw, int) and raw >= 0 else 0

        return TokenUsage(
            prompt_tokens=count("prompt_tokens"),
            completion_tokens=count("completion_tokens"),
            total_tokens=count("total_tokens"),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        endpoint = "/v1/embeddings"
        payload: dict[str, object] = {"model": request.model, "input": request.input}
        try:
            response = await self._send("POST", endpoint, payload=payload)
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            embeddings = self._parse_embeddings(document)
        except AdapterFailure as failure:
            return EmbeddingResult(
                request_id=request.request_id,
                status=(
                    OperationStatus.UNSUPPORTED
                    if failure.error.code is AdapterErrorCode.UNSUPPORTED
                    else OperationStatus.FAILED
                ),
                error=failure.error,
            )
        return EmbeddingResult(
            request_id=request.request_id,
            status=OperationStatus.SUCCEEDED,
            embeddings=embeddings,
            usage=self._parse_usage(document.get("usage")),
        )

    @staticmethod
    def _parse_embeddings(document: Mapping[str, object]) -> tuple[tuple[float, ...], ...]:
        data = document.get("data")
        typed_data = _object_list(data)
        if not typed_data:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App embedding response has no vectors",
                detail={},
            )
        vectors: list[tuple[float, ...]] = []
        for raw_item in typed_data:
            item = _object_mapping(raw_item)
            if item is None:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="oMLX App embedding item is invalid",
                    detail={},
                )
            raw_vector = item.get("embedding")
            typed_vector = _object_list(raw_vector)
            if typed_vector is None or not all(
                isinstance(number, (int, float)) and not isinstance(number, bool)
                for number in typed_vector
            ):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="oMLX App embedding vector is invalid",
                    detail={},
                )
            vectors.append(tuple(float(cast(int | float, number)) for number in typed_vector))
        return tuple(vectors)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        endpoint = "/v1/chat/completions"
        emitted_content = False
        saw_data = False
        completed = False
        reasoning_filter = _ReasoningFilter()
        try:
            async with self._client.stream(
                "POST",
                self._url(endpoint),
                json=self._chat_payload(request, stream=True),
                timeout=self._timeout,
            ) as response:
                if not response.is_success:
                    yield self._stream_error(
                        request.request_id,
                        self._http_error(response, endpoint=endpoint).error,
                        emitted_content=False,
                    )
                    return
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    saw_data = True
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        completed = True
                        remaining = reasoning_filter.finish()
                        if remaining:
                            emitted_content = True
                            yield StreamEvent(
                                kind=StreamEventKind.CONTENT,
                                request_id=request.request_id,
                                content=remaining,
                                emitted_content=True,
                                phase=StreamPhase.AFTER_CONTENT,
                            )
                        yield StreamEvent(
                            kind=StreamEventKind.DONE,
                            request_id=request.request_id,
                            emitted_content=emitted_content,
                            phase=StreamPhase.COMPLETE,
                        )
                        return
                    try:
                        parsed = cast(object, json.loads(data))
                    except json.JSONDecodeError:
                        yield self._stream_error(
                            request.request_id,
                            AdapterError(
                                code=AdapterErrorCode.BAD_RESPONSE,
                                message="oMLX App stream emitted non-JSON data",
                            ),
                            emitted_content=emitted_content,
                        )
                        return
                    if not isinstance(parsed, dict):
                        yield self._stream_error(
                            request.request_id,
                            AdapterError(
                                code=AdapterErrorCode.BAD_RESPONSE,
                                message="oMLX App stream emitted an unexpected JSON shape",
                            ),
                            emitted_content=emitted_content,
                        )
                        return
                    document = cast(dict[str, object], parsed)
                    usage = self._parse_usage(document.get("usage"))
                    if usage is not None:
                        yield StreamEvent(
                            kind=StreamEventKind.USAGE,
                            request_id=request.request_id,
                            usage=usage,
                            emitted_content=emitted_content,
                            phase=(
                                StreamPhase.AFTER_CONTENT
                                if emitted_content
                                else StreamPhase.BEFORE_CONTENT
                            ),
                        )
                    content, finish_reason = self._parse_stream_choice(document)
                    content = reasoning_filter.feed(content)
                    if content:
                        emitted_content = True
                        yield StreamEvent(
                            kind=StreamEventKind.CONTENT,
                            request_id=request.request_id,
                            content=content,
                            finish_reason=finish_reason,
                            emitted_content=True,
                            phase=StreamPhase.AFTER_CONTENT,
                        )
        except httpx.TimeoutException:
            error = AdapterError(
                code=AdapterErrorCode.TIMEOUT,
                message="oMLX App stream timed out",
                retryable=not emitted_content,
            )
            yield self._stream_error(request.request_id, error, emitted_content=emitted_content)
            return
        except httpx.TransportError:
            error = AdapterError(
                code=AdapterErrorCode.STREAM_INTERRUPTED,
                message="oMLX App stream was interrupted",
                retryable=not emitted_content,
                emitted_content=emitted_content,
                phase=(
                    StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                ),
            )
            yield self._stream_error(request.request_id, error, emitted_content=emitted_content)
            return

        if not completed:
            error = AdapterError(
                code=(
                    AdapterErrorCode.STREAM_INTERRUPTED
                    if saw_data
                    else AdapterErrorCode.BAD_RESPONSE
                ),
                message=(
                    "oMLX App stream ended before completion"
                    if saw_data
                    else "oMLX App stream returned an empty body"
                ),
                retryable=not emitted_content,
                emitted_content=emitted_content,
                phase=(
                    StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                ),
            )
            yield self._stream_error(request.request_id, error, emitted_content=emitted_content)

    @staticmethod
    def _parse_stream_choice(document: Mapping[str, object]) -> tuple[str, str | None]:
        choices = document.get("choices")
        typed_choices = _object_list(choices)
        if not typed_choices:
            return "", None
        choice = _object_mapping(typed_choices[0])
        if choice is None:
            return "", None
        delta = _object_mapping(choice.get("delta"))
        content = delta.get("content") if delta is not None else ""
        finish_reason = choice.get("finish_reason")
        return (
            content if isinstance(content, str) else "",
            finish_reason if isinstance(finish_reason, str) else None,
        )

    @staticmethod
    def _stream_error(
        request_id: str, error: AdapterError, *, emitted_content: bool
    ) -> StreamEvent:
        phase = StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
        normalized = error.model_copy(update={"emitted_content": emitted_content, "phase": phase})
        return StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id=request_id,
            error=normalized,
            emitted_content=emitted_content,
            phase=phase,
        )
