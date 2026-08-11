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

from .reasoning import ReasoningFilter
from .security import AdapterFailure
from .sse import SSEDecoder

_UNSUPPORTED_STATUSES = frozenset({404, 405, 501})
_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_TIMEOUT = httpx.Timeout(connect=2.0, read=30.0, write=10.0, pool=2.0)
DEFAULT_MINIMUM_VERSION = (0, 5, 0)
DEFAULT_MAXIMUM_VERSION = (0, 6, 0)


def _object_mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _object_list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return cast(list[object], value)


def _semver_core(value: str) -> tuple[int, int, int] | None:
    matched = _SEMVER.fullmatch(value)
    if matched is None:
        return None
    return (
        int(matched.group(1)),
        int(matched.group(2)),
        int(matched.group(3)),
    )


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
        minimum_version: tuple[int, int, int] = DEFAULT_MINIMUM_VERSION,
        maximum_version: tuple[int, int, int] = DEFAULT_MAXIMUM_VERSION,
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
        if minimum_version >= maximum_version:
            raise ValueError("minimum_version must be lower than maximum_version")
        self._minimum_version = minimum_version
        self._maximum_version = maximum_version
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(transport=transport, trust_env=False)
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
        if not status_response.is_success:
            return self._incompatible_snapshot(
                observed_at=observed_at,
                http_status=status_response.status_code,
                message="oMLX App status endpoint did not succeed",
            )
        try:
            status = self._json_object(status_response, endpoint="/api/status")
        except AdapterFailure:
            return self._incompatible_snapshot(
                observed_at=observed_at,
                http_status=status_response.status_code,
                message="oMLX App status response is incompatible",
            )
        raw_status = status.get("status")
        raw_version = status.get("version")
        protocol_version = raw_version if isinstance(raw_version, str) else None
        version = _semver_core(protocol_version) if protocol_version is not None else None
        if (
            raw_status != "ok"
            or version is None
            or not (self._minimum_version <= version < self._maximum_version)
        ):
            return self._incompatible_snapshot(
                observed_at=observed_at,
                http_status=status_response.status_code,
                message="oMLX App status or version is outside the supported contract",
                protocol_version=protocol_version,
            )
        assert protocol_version is not None

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
        loaded_ids = {model.id for model in models if model.loaded is True}
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

    def _incompatible_snapshot(
        self,
        *,
        observed_at: datetime,
        http_status: int,
        message: str,
        protocol_version: str | None = None,
    ) -> CapabilitySnapshot:
        error = AdapterError(
            code=AdapterErrorCode.INCOMPATIBLE,
            message=message,
            http_status=http_status,
        )
        return CapabilitySnapshot(
            backend_id=self._backend_id,
            reachable=True,
            compatible=False,
            model_available=False,
            generation_ready=False,
            observed_at=observed_at,
            protocol_version=protocol_version,
            errors=(error,),
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
            try:
                status_document = self._json_object(status_response, endpoint="/v1/models/status")
            except AdapterFailure:
                status_document = {}
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
            raw_loaded = status_by_id.get(model_id, item.get("loaded"))
            loaded = raw_loaded if isinstance(raw_loaded, bool) else None
            display_name = item.get("name")
            context_limit = item.get("context_limit")
            models.append(
                ModelRuntime(
                    id=model_id,
                    display_name=display_name if isinstance(display_name, str) else None,
                    state=(
                        ModelRuntimeState.LOADED
                        if loaded is True
                        else ModelRuntimeState.AVAILABLE
                        if loaded is False
                        else ModelRuntimeState.UNKNOWN
                    ),
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
        if model.loaded is None:
            error = AdapterError(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="model loaded state is indeterminate",
                retryable=True,
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
        changed_fields = list(changes)
        if request.scope is TuneScope.MODEL:
            reasoning_off: dict[str, object] = {
                "enable_thinking": False,
                "thinking_budget_enabled": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            reasoning_changed = False
            for key, value in reasoning_off.items():
                if current.get(key) != value:
                    changes[key] = value
                    reasoning_changed = True
            if reasoning_changed:
                changed_fields.append("reasoning_off")
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
            changed_fields=tuple(sorted(changed_fields)),
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
            safe_content, unclosed_reasoning = self._strip_reasoning(content)
            if unclosed_reasoning:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="oMLX App chat response contains an unclosed reasoning block",
                    detail={},
                )
        except AdapterFailure as failure:
            return ChatResult(
                request_id=request.request_id,
                success=False,
                error=failure.error,
            )
        return ChatResult(
            request_id=request.request_id,
            success=True,
            content=safe_content,
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
    def _strip_reasoning(content: str) -> tuple[str, bool]:
        filtered = ReasoningFilter()
        safe = filtered.feed(content)
        remaining, unclosed = filtered.finish()
        return safe + remaining, unclosed

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
        reasoning_filter = ReasoningFilter()
        decoder = SSEDecoder()
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
                try:
                    async for chunk in response.aiter_bytes():
                        frames = decoder.feed(chunk)
                        for data in frames:
                            saw_data = True
                            events, emitted_content, completed = self._stream_frame_events(
                                request_id=request.request_id,
                                data=data,
                                reasoning_filter=reasoning_filter,
                                emitted_content=emitted_content,
                            )
                            for event in events:
                                yield event
                            if completed:
                                return
                    finish = decoder.finish()
                except UnicodeDecodeError:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.BAD_RESPONSE,
                            message="oMLX App stream emitted invalid UTF-8",
                        ),
                        emitted_content=emitted_content,
                    )
                    return
                for data in finish.events:
                    saw_data = True
                    events, emitted_content, completed = self._stream_frame_events(
                        request_id=request.request_id,
                        data=data,
                        reasoning_filter=reasoning_filter,
                        emitted_content=emitted_content,
                    )
                    for event in events:
                        yield event
                    if completed:
                        return
                if finish.incomplete_event:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.BAD_RESPONSE,
                            message="oMLX App stream ended with an incomplete SSE event",
                            retryable=not emitted_content,
                        ),
                        emitted_content=emitted_content,
                    )
                    return
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

    def _stream_frame_events(
        self,
        *,
        request_id: str,
        data: str,
        reasoning_filter: ReasoningFilter,
        emitted_content: bool,
    ) -> tuple[tuple[StreamEvent, ...], bool, bool]:
        if data.strip() == "[DONE]":
            events: list[StreamEvent] = []
            remaining, unclosed = reasoning_filter.finish()
            if unclosed:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="oMLX App stream ended with an unclosed reasoning block",
                    retryable=not emitted_content,
                )
                return (
                    (self._stream_error(request_id, error, emitted_content=emitted_content),),
                    emitted_content,
                    True,
                )
            if remaining:
                emitted_content = True
                events.append(
                    StreamEvent(
                        kind=StreamEventKind.CONTENT,
                        request_id=request_id,
                        content=remaining,
                        emitted_content=True,
                        phase=StreamPhase.AFTER_CONTENT,
                    )
                )
            events.append(
                StreamEvent(
                    kind=StreamEventKind.DONE,
                    request_id=request_id,
                    emitted_content=emitted_content,
                    phase=StreamPhase.COMPLETE,
                )
            )
            return tuple(events), emitted_content, True

        try:
            parsed = cast(object, json.loads(data))
        except json.JSONDecodeError:
            error = AdapterError(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App stream emitted non-JSON data",
            )
            return (
                (self._stream_error(request_id, error, emitted_content=emitted_content),),
                emitted_content,
                True,
            )
        if not isinstance(parsed, dict):
            error = AdapterError(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="oMLX App stream emitted an unexpected JSON shape",
            )
            return (
                (self._stream_error(request_id, error, emitted_content=emitted_content),),
                emitted_content,
                True,
            )
        document = cast(dict[str, object], parsed)
        events = []
        usage = self._parse_usage(document.get("usage"))
        if usage is not None:
            events.append(
                StreamEvent(
                    kind=StreamEventKind.USAGE,
                    request_id=request_id,
                    usage=usage,
                    emitted_content=emitted_content,
                    phase=(
                        StreamPhase.AFTER_CONTENT if emitted_content else StreamPhase.BEFORE_CONTENT
                    ),
                )
            )
        content, finish_reason = self._parse_stream_choice(document)
        content = reasoning_filter.feed(content)
        if content:
            emitted_content = True
            events.append(
                StreamEvent(
                    kind=StreamEventKind.CONTENT,
                    request_id=request_id,
                    content=content,
                    finish_reason=finish_reason,
                    emitted_content=True,
                    phase=StreamPhase.AFTER_CONTENT,
                )
            )
        return tuple(events), emitted_content, False

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
