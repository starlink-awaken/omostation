"""Async native HTTP adapter for an Ollama backend."""

from __future__ import annotations

import base64
import binascii
import math
import re
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit

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
    ImageContentBlock,
    LifecycleResult,
    ModelRuntime,
    ModelRuntimeState,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TextContentBlock,
    TokenUsage,
    TuneRequest,
    TuneResult,
    TuneScope,
)

from .ndjson import NDJSONDecodeError, NDJSONDecoder, NDJSONLimitError
from .reasoning import ReasoningFilter
from .security import AdapterFailure

_UNSUPPORTED_STATUSES = frozenset({404, 405, 501})
_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_MODEL_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TIMEOUT = httpx.Timeout(connect=2.0, read=60.0, write=10.0, pool=2.0)
DEFAULT_KEEP_ALIVE_SECONDS = 300
MAX_KEEP_ALIVE_SECONDS = 86_400
DEFAULT_MAX_RESPONSE_BYTES = 4_194_304
DEFAULT_MAX_NDJSON_RECORD_BYTES = 1_048_576
DEFAULT_MAX_STREAM_BYTES = 16_777_216
DEFAULT_MAX_EMBEDDING_INPUTS = 256
DEFAULT_MAX_EMBEDDING_DIMENSION = 65_536
DEFAULT_MAX_EMBEDDING_SCALARS = 1_048_576
DEFAULT_MAX_IMAGES = 8
DEFAULT_MAX_IMAGE_BYTES = 20_971_520
DEFAULT_MAX_TOTAL_IMAGE_BYTES = 33_554_432


def _mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return cast(list[object], value)


def _valid_model_id(value: str) -> bool:
    return len(value) <= 256 and _MODEL_ID.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class _Identity:
    model_id: str
    aliases: frozenset[str]
    digest: str | None
    context_limit: int | None = None


@dataclass(slots=True)
class _ImageBudget:
    count: int = 0
    decoded_bytes: int = 0


@dataclass(frozen=True, slots=True)
class _StreamTerminal:
    content: str
    usage: TokenUsage
    finish_reason: str


class OllamaAdapter:
    """Map Ollama's documented native API onto the canonical adapter contract."""

    def __init__(
        self,
        *,
        backend_id: str,
        base_url: str = "http://127.0.0.1:11434",
        probe_model_id: str | None = None,
        keep_alive_seconds: int = DEFAULT_KEEP_ALIVE_SECONDS,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_ndjson_record_bytes: int = DEFAULT_MAX_NDJSON_RECORD_BYTES,
        max_stream_bytes: int = DEFAULT_MAX_STREAM_BYTES,
        max_embedding_inputs: int = DEFAULT_MAX_EMBEDDING_INPUTS,
        max_embedding_dimension: int = DEFAULT_MAX_EMBEDDING_DIMENSION,
        max_embedding_scalars: int = DEFAULT_MAX_EMBEDDING_SCALARS,
        max_images: int = DEFAULT_MAX_IMAGES,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
        max_total_image_bytes: int = DEFAULT_MAX_TOTAL_IMAGE_BYTES,
    ) -> None:
        if _CONTROL.search(base_url):
            raise ValueError("base_url must not contain control characters")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must use http or https")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not contain userinfo")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("base_url must be an origin root without query or fragment")
        if probe_model_id is not None and not _valid_model_id(probe_model_id):
            raise ValueError("probe_model_id is invalid")
        if (
            type(keep_alive_seconds) is not int
            or not 1 <= keep_alive_seconds <= MAX_KEEP_ALIVE_SECONDS
        ):
            raise ValueError("keep_alive_seconds must be an integer from 1 to 86400")
        if client is not None and transport is not None:
            raise ValueError("client and transport are mutually exclusive")
        limits = (
            max_response_bytes,
            max_ndjson_record_bytes,
            max_stream_bytes,
            max_embedding_inputs,
            max_embedding_dimension,
            max_embedding_scalars,
            max_images,
            max_image_bytes,
            max_total_image_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in limits):
            raise ValueError("adapter resource limits must be positive integers")
        if max_stream_bytes < max_ndjson_record_bytes:
            raise ValueError("stream byte limit must cover one NDJSON record")
        if max_embedding_scalars < max_embedding_dimension:
            raise ValueError("embedding scalar limit must cover one vector")
        if max_total_image_bytes < max_image_bytes:
            raise ValueError("total image limit must cover one image")
        self._backend_id = backend_id
        self._base_url = httpx.URL(base_url.rstrip("/") + "/")
        self._probe_model_id = probe_model_id
        self._keep_alive_seconds = keep_alive_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(transport=transport)
        self._timeout = _TIMEOUT
        self._max_response_bytes = max_response_bytes
        self._max_ndjson_record_bytes = max_ndjson_record_bytes
        self._max_stream_bytes = max_stream_bytes
        self._max_embedding_inputs = max_embedding_inputs
        self._max_embedding_dimension = max_embedding_dimension
        self._max_embedding_scalars = max_embedding_scalars
        self._max_images = max_images
        self._max_image_bytes = max_image_bytes
        self._max_total_image_bytes = max_total_image_bytes

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
    ) -> httpx.Response:
        response: httpx.Response | None = None
        try:
            request = self._client.build_request(
                method,
                self._url(path),
                json=payload,
                timeout=self._timeout,
            )
            response = await self._client.send(request, stream=True)
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > self._max_response_bytes:
                    content.clear()
                    raise AdapterFailure.from_detail(
                        code=AdapterErrorCode.OUTPUT_LIMIT,
                        message="Ollama response exceeded the configured byte limit",
                        detail={},
                        http_status=response.status_code,
                        endpoint=path,
                    )
                content.extend(chunk)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=bytes(content),
                request=request,
            )
        except AdapterFailure:
            raise
        except httpx.TimeoutException as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.TIMEOUT,
                message="Ollama request timed out",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc
        except httpx.TransportError as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.UNREACHABLE,
                message="Ollama transport is unreachable",
                detail={},
                retryable=True,
                endpoint=path,
            ) from exc
        finally:
            if response is not None:
                await response.aclose()

    @staticmethod
    def _json_object(response: httpx.Response, *, endpoint: str) -> dict[str, object]:
        if not response.content:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="Ollama returned an empty response",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        try:
            value = cast(object, response.json())
        except (ValueError, UnicodeDecodeError) as exc:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="Ollama returned non-JSON data",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            ) from exc
        mapping = _mapping(value)
        if mapping is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="Ollama returned an unexpected JSON shape",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        return dict(mapping)

    @staticmethod
    def _http_error(response: httpx.Response, *, endpoint: str) -> AdapterFailure:
        unsupported = response.status_code in _UNSUPPORTED_STATUSES
        return AdapterFailure.from_detail(
            code=(AdapterErrorCode.UNSUPPORTED if unsupported else AdapterErrorCode.BAD_RESPONSE),
            message=(
                "Ollama endpoint is unsupported" if unsupported else "Ollama returned an HTTP error"
            ),
            detail={},
            retryable=response.status_code >= 500,
            http_status=response.status_code,
            endpoint=endpoint,
        )

    async def discover(self) -> CapabilitySnapshot:
        observed_at = self._clock()
        endpoint = "/api/version"
        try:
            response = await self._send("GET", endpoint)
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
        if not response.is_success:
            return self._incompatible(observed_at, response.status_code)
        try:
            document = self._json_object(response, endpoint=endpoint)
        except AdapterFailure:
            return self._incompatible(observed_at, response.status_code)
        raw_version = document.get("version")
        version = raw_version if isinstance(raw_version, str) else None
        if version is None or _SEMVER.fullmatch(version) is None:
            return self._incompatible(observed_at, response.status_code, version)

        errors: list[AdapterError] = []
        try:
            models = await self.list_models()
            compatible = True
        except AdapterFailure as failure:
            errors.append(failure.error)
            models = ()
            compatible = False
        probe_id = self._probe_model_id
        if probe_id is None:
            probe_id = next((model.id for model in models if model.loaded is True), None)
        loaded_ids = {model.id for model in models if model.loaded is True}
        generation_ready = False
        if compatible and probe_id is not None and probe_id in loaded_ids:
            probe = await self.chat(
                ChatRequest(
                    request_id="ollama-readiness-probe",
                    model=probe_id,
                    messages=(ChatMessage(role="user", content="Reply O only"),),
                    max_tokens=1,
                    temperature=0.0,
                )
            )
            generation_ready = probe.success and bool(probe.content)
            if probe.error is not None:
                errors.append(probe.error)
        capabilities: frozenset[AdapterCapability] = (
            frozenset(
                {
                    AdapterCapability.CHAT,
                    AdapterCapability.STREAMING,
                    AdapterCapability.VISION,
                    AdapterCapability.EMBEDDING,
                    AdapterCapability.MODEL_LIFECYCLE,
                    AdapterCapability.TUNING,
                }
            )
            if compatible
            else frozenset()
        )
        return CapabilitySnapshot(
            backend_id=self._backend_id,
            reachable=True,
            compatible=compatible,
            model_available=bool(models),
            generation_ready=generation_ready,
            observed_at=observed_at,
            protocol_version=version,
            capabilities=capabilities,
            errors=tuple(errors),
        )

    def _incompatible(
        self, observed_at: datetime, status: int, version: str | None = None
    ) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            backend_id=self._backend_id,
            reachable=True,
            compatible=False,
            model_available=False,
            generation_ready=False,
            observed_at=observed_at,
            protocol_version=version,
            errors=(
                AdapterError(
                    code=AdapterErrorCode.INCOMPATIBLE,
                    message="Ollama version response is incompatible",
                    http_status=status,
                ),
            ),
        )

    async def list_models(self) -> tuple[ModelRuntime, ...]:
        tags = await self._inventory("/api/tags")
        try:
            running = await self._inventory("/api/ps")
        except AdapterFailure:
            return tuple(
                ModelRuntime(id=item.model_id, state=ModelRuntimeState.UNKNOWN, loaded=None)
                for item in tags
            )
        return self._merge_inventory(tags, running)

    async def _inventory(self, endpoint: str) -> tuple[_Identity, ...]:
        response = await self._send("GET", endpoint)
        if not response.is_success:
            raise self._http_error(response, endpoint=endpoint)
        document = self._json_object(response, endpoint=endpoint)
        raw_models = _list(document.get("models"))
        if raw_models is None:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.INCOMPATIBLE,
                message="Ollama model inventory is incompatible",
                detail={},
                http_status=response.status_code,
                endpoint=endpoint,
            )
        identities: list[_Identity] = []
        aliases_seen: set[str] = set()
        digests_seen: set[str] = set()
        for raw_item in raw_models:
            item = _mapping(raw_item)
            if item is None:
                raise self._identity_failure(endpoint)
            raw_name = item.get("name")
            raw_model = item.get("model")
            names = [value for value in (raw_name, raw_model) if isinstance(value, str)]
            aliases = frozenset(names)
            if not aliases or any(not _valid_model_id(alias) for alias in aliases):
                raise self._identity_failure(endpoint)
            model_id = raw_model if isinstance(raw_model, str) else cast(str, raw_name)
            digest_value = item.get("digest")
            digest = digest_value if isinstance(digest_value, str) and digest_value else None
            if aliases_seen.intersection(aliases) or (
                digest is not None and digest in digests_seen
            ):
                raise self._identity_failure(endpoint)
            aliases_seen.update(aliases)
            if digest is not None:
                digests_seen.add(digest)
            context = item.get("context_length")
            context_limit = (
                context
                if isinstance(context, int) and not isinstance(context, bool) and context > 0
                else None
            )
            identities.append(
                _Identity(
                    model_id=model_id,
                    aliases=aliases,
                    digest=digest,
                    context_limit=context_limit,
                )
            )
        return tuple(identities)

    @staticmethod
    def _identity_failure(endpoint: str) -> AdapterFailure:
        return AdapterFailure.from_detail(
            code=AdapterErrorCode.INCOMPATIBLE,
            message="Ollama model identity is ambiguous",
            detail={},
            endpoint=endpoint,
        )

    def _merge_inventory(
        self, tags: tuple[_Identity, ...], running: tuple[_Identity, ...]
    ) -> tuple[ModelRuntime, ...]:
        alias_owner: dict[str, int] = {}
        digest_owner: dict[str, int] = {}
        for index, item in enumerate(tags):
            for alias in item.aliases:
                alias_owner[alias] = index
            if item.digest is not None:
                digest_owner[item.digest] = index
        loaded_indices: set[int] = set()
        extras: list[_Identity] = []
        for item in running:
            matches = {alias_owner[alias] for alias in item.aliases if alias in alias_owner}
            if item.digest is not None and item.digest in digest_owner:
                matches.add(digest_owner[item.digest])
            if len(matches) > 1:
                raise self._identity_failure("/api/ps")
            if matches:
                index = next(iter(matches))
                tag = tags[index]
                if item.aliases.isdisjoint(tag.aliases):
                    raise self._identity_failure("/api/ps")
                if item.digest is not None and tag.digest is not None and item.digest != tag.digest:
                    raise self._identity_failure("/api/ps")
                if index in loaded_indices:
                    raise self._identity_failure("/api/ps")
                loaded_indices.add(index)
            else:
                if any(
                    item.aliases.intersection(extra.aliases)
                    or (
                        item.digest is not None
                        and extra.digest is not None
                        and item.digest == extra.digest
                    )
                    for extra in extras
                ):
                    raise self._identity_failure("/api/ps")
                extras.append(item)
        models = [
            ModelRuntime(
                id=item.model_id,
                state=(
                    ModelRuntimeState.LOADED
                    if index in loaded_indices
                    else ModelRuntimeState.AVAILABLE
                ),
                loaded=index in loaded_indices,
                context_limit=item.context_limit,
            )
            for index, item in enumerate(tags)
        ]
        models.extend(
            ModelRuntime(
                id=item.model_id,
                state=ModelRuntimeState.LOADED,
                loaded=True,
                context_limit=item.context_limit,
            )
            for item in extras
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
        if not _valid_model_id(model_id):
            return self._lifecycle_failure(
                model_id,
                idempotency_key,
                AdapterError(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="Ollama model identifier is invalid",
                ),
            )
        try:
            models = await self.list_models()
        except AdapterFailure as failure:
            return self._lifecycle_failure(model_id, idempotency_key, failure.error)
        model = next((item for item in models if item.id == model_id), None)
        if model is None:
            return self._lifecycle_failure(
                model_id,
                idempotency_key,
                AdapterError(
                    code=AdapterErrorCode.MODEL_UNAVAILABLE,
                    message="model is not present in the Ollama inventory",
                ),
            )
        if model.loaded is None:
            return self._lifecycle_failure(
                model_id,
                idempotency_key,
                AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="model loaded state is indeterminate",
                    retryable=True,
                ),
            )
        if model.loaded is load:
            return LifecycleResult(
                model_id=model_id,
                status=OperationStatus.UNCHANGED,
                changed=False,
                idempotency_key=idempotency_key,
            )
        payload: dict[str, object] = {
            "model": model_id,
            "prompt": "",
            "stream": False,
            "keep_alive": self._keep_alive_seconds if load else 0,
        }
        try:
            response = await self._send("POST", "/api/generate", payload=payload)
            if not response.is_success:
                raise self._http_error(response, endpoint="/api/generate")
        except AdapterFailure as failure:
            return self._lifecycle_failure(model_id, idempotency_key, failure.error)
        try:
            document = self._json_object(response, endpoint="/api/generate")
            if document.get("done") is not True:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama lifecycle response is incomplete",
                    detail={},
                    endpoint="/api/generate",
                )
            fresh = await self.list_models()
        except AdapterFailure:
            return self._lifecycle_failure(
                model_id,
                idempotency_key,
                AdapterError(
                    code=AdapterErrorCode.PARTIAL_FAILURE,
                    message="Ollama lifecycle operation could not be verified",
                ),
            )
        verified = next((item for item in fresh if item.id == model_id), None)
        if verified is None or verified.loaded is not load:
            return self._lifecycle_failure(
                model_id,
                idempotency_key,
                AdapterError(
                    code=AdapterErrorCode.PARTIAL_FAILURE,
                    message="Ollama lifecycle operation could not be verified",
                ),
            )
        return LifecycleResult(
            model_id=model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _lifecycle_failure(
        model_id: str, idempotency_key: str | None, error: AdapterError
    ) -> LifecycleResult:
        return LifecycleResult(
            model_id=model_id,
            status=(
                OperationStatus.UNSUPPORTED
                if error.code is AdapterErrorCode.UNSUPPORTED
                else OperationStatus.FAILED
            ),
            changed=False,
            idempotency_key=idempotency_key,
            error=error,
        )

    async def tune(self, request: TuneRequest) -> TuneResult:
        values = request.settings.model_dump(exclude_unset=True)
        if "is_pinned" in values:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="Ollama does not expose verifiable permanent pin tuning",
                ),
            )
        if request.scope is not TuneScope.MODEL or set(values) != {"ttl_seconds"}:
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="Ollama supports only model TTL refresh tuning",
                ),
            )
        model_id = cast(str, request.model_id)
        if not _valid_model_id(model_id):
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="Ollama model identifier is invalid",
                ),
            )
        ttl = values.get("ttl_seconds")
        if (
            isinstance(ttl, bool)
            or not isinstance(ttl, int)
            or not 1 <= ttl <= MAX_KEEP_ALIVE_SECONDS
        ):
            return self._tune_failure(
                request,
                AdapterError(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="Ollama TTL must be an integer from 1 to 86400",
                ),
            )
        keep_alive = ttl
        try:
            models = await self.list_models()
            model = next((item for item in models if item.id == model_id), None)
            if model is None:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.MODEL_UNAVAILABLE,
                    message="Ollama tuning model is unavailable",
                    detail={},
                )
            if model.loaded is not True:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama tuning requires a confirmed loaded model",
                    detail={},
                )
            response = await self._send(
                "POST",
                "/api/generate",
                payload={
                    "model": model_id,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": keep_alive,
                },
            )
            if not response.is_success:
                raise self._http_error(response, endpoint="/api/generate")
            document = self._json_object(response, endpoint="/api/generate")
            if document.get("done") is not True:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama tuning response is incomplete",
                    detail={},
                )
            fresh = await self.list_models()
            if not any(item.id == model_id and item.loaded is True for item in fresh):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.PARTIAL_FAILURE,
                    message="Ollama tuning could not be verified",
                    detail={},
                )
        except AdapterFailure as failure:
            return self._tune_failure(request, failure.error)
        return TuneResult(
            scope=request.scope,
            model_id=request.model_id,
            status=OperationStatus.SUCCEEDED,
            changed_fields=("ttl_seconds",),
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

    def _message_payload(self, message: ChatMessage, *, budget: _ImageBudget) -> dict[str, object]:
        if isinstance(message.content, str):
            return {"role": message.role, "content": message.content}
        text_parts: list[str] = []
        images: list[str] = []
        for block in message.content:
            if isinstance(block, TextContentBlock):
                text_parts.append(block.text)
                continue
            assert isinstance(block, ImageContentBlock)
            url = block.image_url.url
            if not url.startswith("data:image/"):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.UNSUPPORTED,
                    message="Ollama native vision accepts only validated image data URLs",
                    detail={},
                )
            header, separator, payload = url.partition(",")
            if not separator or not header.endswith(";base64") or not payload:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="Ollama image data is invalid",
                    detail={},
                )
            remaining_bytes = self._max_total_image_bytes - budget.decoded_bytes
            encoded_limit = 4 * ((min(self._max_image_bytes, remaining_bytes) + 2) // 3)
            if budget.count >= self._max_images or len(payload) > encoded_limit:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.OUTPUT_LIMIT,
                    message="Ollama image input exceeded the configured limit",
                    detail={},
                )
            try:
                decoded = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.INVALID_REQUEST,
                    message="Ollama image data is invalid",
                    detail={},
                ) from exc
            budget.count += 1
            budget.decoded_bytes += len(decoded)
            if (
                len(decoded) > self._max_image_bytes
                or budget.count > self._max_images
                or budget.decoded_bytes > self._max_total_image_bytes
            ):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.OUTPUT_LIMIT,
                    message="Ollama image input exceeded the configured limit",
                    detail={},
                )
            images.append(payload)
        result: dict[str, object] = {"role": message.role, "content": "\n".join(text_parts)}
        if images:
            result["images"] = images
        return result

    def _chat_payload(self, request: ChatRequest, *, stream: bool) -> dict[str, object]:
        if not _valid_model_id(request.model):
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.INVALID_REQUEST,
                message="Ollama model identifier is invalid",
                detail={},
            )
        budget = _ImageBudget()
        return {
            "model": request.model,
            "messages": [
                self._message_payload(message, budget=budget) for message in request.messages
            ],
            "stream": stream,
            "think": False,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
            "keep_alive": self._keep_alive_seconds,
        }

    async def chat(self, request: ChatRequest) -> ChatResult:
        endpoint = "/api/chat"
        try:
            payload = self._chat_payload(request, stream=False)
            response = await self._send("POST", endpoint, payload=payload)
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            if document.get("done") is not True:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama chat response is incomplete",
                    detail={},
                )
            message = _mapping(document.get("message"))
            content = message.get("content") if message is not None else None
            if not isinstance(content, str):
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama chat response has no visible content field",
                    detail={},
                )
            self._reject_observable_thinking(document, message)
            safe_content, saw_reasoning, unclosed = self._strip_reasoning(content)
            if saw_reasoning or unclosed:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.INCOMPATIBLE,
                    message="Ollama returned observable reasoning despite think=false",
                    detail={},
                )
            if not safe_content:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama chat response has no safe visible content",
                    detail={},
                )
            usage = self._terminal_usage(document)
            finish_reason = self._done_reason(document)
        except AdapterFailure as failure:
            return ChatResult(request_id=request.request_id, success=False, error=failure.error)
        return ChatResult(
            request_id=request.request_id,
            success=True,
            content=safe_content,
            finish_reason=finish_reason,
            usage=usage,
        )

    @staticmethod
    def _strip_reasoning(content: str) -> tuple[str, bool, bool]:
        reasoning_filter = ReasoningFilter()
        safe = reasoning_filter.feed(content)
        remaining, unclosed = reasoning_filter.finish()
        return safe + remaining, reasoning_filter.saw_reasoning, unclosed

    @staticmethod
    def _reject_observable_thinking(
        document: Mapping[str, object], message: Mapping[str, object] | None
    ) -> None:
        for container in (document, message):
            if container is None or "thinking" not in container:
                continue
            value = container["thinking"]
            if value is not None and value != "":
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.INCOMPATIBLE,
                    message="Ollama returned observable reasoning despite think=false",
                    detail={},
                )

    @staticmethod
    def _terminal_usage(document: Mapping[str, object]) -> TokenUsage:
        counts: list[int] = []
        for key in ("prompt_eval_count", "eval_count"):
            value = document.get(key)
            if type(value) is not int or value < 0:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama terminal usage is invalid",
                    detail={},
                )
            counts.append(value)
        return TokenUsage(
            prompt_tokens=counts[0],
            completion_tokens=counts[1],
            total_tokens=sum(counts),
        )

    @staticmethod
    def _done_reason(document: Mapping[str, object]) -> str:
        value = document.get("done_reason")
        if not isinstance(value, str) or not value:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="Ollama terminal done reason is invalid",
                detail={},
            )
        return value

    @staticmethod
    def _usage(document: Mapping[str, object]) -> TokenUsage:
        def count(key: str) -> int:
            value = document.get(key, 0)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                else 0
            )

        prompt = count("prompt_eval_count")
        completion = count("eval_count")
        return TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        endpoint = "/api/embed"
        if not _valid_model_id(request.model):
            error = AdapterError(
                code=AdapterErrorCode.INVALID_REQUEST,
                message="Ollama model identifier is invalid",
            )
            return EmbeddingResult(
                request_id=request.request_id,
                status=OperationStatus.FAILED,
                error=error,
            )
        expected = 1 if isinstance(request.input, str) else len(request.input)
        if expected > self._max_embedding_inputs:
            return EmbeddingResult(
                request_id=request.request_id,
                status=OperationStatus.FAILED,
                error=AdapterError(
                    code=AdapterErrorCode.OUTPUT_LIMIT,
                    message="Ollama embedding input count exceeded the configured limit",
                ),
            )
        try:
            response = await self._send(
                "POST", endpoint, payload={"model": request.model, "input": request.input}
            )
            if not response.is_success:
                raise self._http_error(response, endpoint=endpoint)
            document = self._json_object(response, endpoint=endpoint)
            embeddings = self._parse_embeddings(document, expected=expected)
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
            usage=self._usage(document),
        )

    def _parse_embeddings(
        self, document: Mapping[str, object], *, expected: int
    ) -> tuple[tuple[float, ...], ...]:
        raw_vectors = _list(document.get("embeddings"))
        if raw_vectors is None or len(raw_vectors) != expected:
            raise AdapterFailure.from_detail(
                code=AdapterErrorCode.BAD_RESPONSE,
                message="Ollama embedding response count is invalid",
                detail={},
            )
        vectors: list[tuple[float, ...]] = []
        dimension: int | None = None
        scalar_count = 0
        for raw_vector in raw_vectors:
            vector = _list(raw_vector)
            if not vector:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama embedding vector is empty",
                    detail={},
                )
            if len(vector) > self._max_embedding_dimension:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.OUTPUT_LIMIT,
                    message="Ollama embedding dimension exceeded the configured limit",
                    detail={},
                )
            scalar_count += len(vector)
            if scalar_count > self._max_embedding_scalars:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.OUTPUT_LIMIT,
                    message="Ollama embedding scalar count exceeded the configured limit",
                    detail={},
                )
            numbers: list[float] = []
            for value in vector:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise AdapterFailure.from_detail(
                        code=AdapterErrorCode.BAD_RESPONSE,
                        message="Ollama embedding vector is invalid",
                        detail={},
                    )
                numbers.append(float(value))
            if dimension is None:
                dimension = len(numbers)
            elif len(numbers) != dimension:
                raise AdapterFailure.from_detail(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama embedding dimensions are inconsistent",
                    detail={},
                )
            vectors.append(tuple(numbers))
        return tuple(vectors)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        endpoint = "/api/chat"
        emitted_content = False
        saw_document = False
        terminal: _StreamTerminal | None = None
        reasoning_filter = ReasoningFilter()
        decoder = NDJSONDecoder(
            max_record_bytes=self._max_ndjson_record_bytes,
            max_total_bytes=self._max_stream_bytes,
        )
        try:
            payload = self._chat_payload(request, stream=True)
        except AdapterFailure as failure:
            yield self._stream_error(request.request_id, failure.error, emitted_content=False)
            return
        try:
            async with self._client.stream(
                "POST", self._url(endpoint), json=payload, timeout=self._timeout
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
                        documents = decoder.feed(chunk)
                        saw_document = saw_document or bool(documents)
                        events, emitted_content, terminal, failed = self._stream_documents(
                            request_id=request.request_id,
                            documents=documents,
                            reasoning_filter=reasoning_filter,
                            emitted_content=emitted_content,
                            terminal=terminal,
                        )
                        for event in events:
                            yield event
                        if failed:
                            return
                    documents = decoder.finish()
                    saw_document = saw_document or bool(documents)
                    events, emitted_content, terminal, failed = self._stream_documents(
                        request_id=request.request_id,
                        documents=documents,
                        reasoning_filter=reasoning_filter,
                        emitted_content=emitted_content,
                        terminal=terminal,
                    )
                    for event in events:
                        yield event
                    if failed:
                        return
                    if terminal is not None:
                        if terminal.content:
                            emitted_content = True
                            yield StreamEvent(
                                kind=StreamEventKind.CONTENT,
                                request_id=request.request_id,
                                content=terminal.content,
                                emitted_content=True,
                                phase=StreamPhase.AFTER_CONTENT,
                            )
                        phase = (
                            StreamPhase.AFTER_CONTENT
                            if emitted_content
                            else StreamPhase.BEFORE_CONTENT
                        )
                        yield StreamEvent(
                            kind=StreamEventKind.USAGE,
                            request_id=request.request_id,
                            usage=terminal.usage,
                            finish_reason=terminal.finish_reason,
                            emitted_content=emitted_content,
                            phase=phase,
                        )
                        yield StreamEvent(
                            kind=StreamEventKind.DONE,
                            request_id=request.request_id,
                            finish_reason=terminal.finish_reason,
                            emitted_content=emitted_content,
                            phase=StreamPhase.COMPLETE,
                        )
                        return
                except NDJSONLimitError:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.OUTPUT_LIMIT,
                            message="Ollama stream exceeded the configured byte limit",
                            retryable=not emitted_content,
                        ),
                        emitted_content=emitted_content,
                    )
                    return
                except NDJSONDecodeError:
                    yield self._stream_error(
                        request.request_id,
                        AdapterError(
                            code=AdapterErrorCode.BAD_RESPONSE,
                            message="Ollama stream emitted invalid NDJSON",
                            retryable=not emitted_content,
                        ),
                        emitted_content=emitted_content,
                    )
                    return
        except httpx.TimeoutException:
            yield self._stream_error(
                request.request_id,
                AdapterError(
                    code=AdapterErrorCode.TIMEOUT,
                    message="Ollama stream timed out",
                    retryable=not emitted_content,
                ),
                emitted_content=emitted_content,
            )
            return
        except httpx.TransportError:
            yield self._stream_error(
                request.request_id,
                AdapterError(
                    code=AdapterErrorCode.STREAM_INTERRUPTED,
                    message="Ollama stream was interrupted",
                    retryable=not emitted_content,
                ),
                emitted_content=emitted_content,
            )
            return
        yield self._stream_error(
            request.request_id,
            AdapterError(
                code=(
                    AdapterErrorCode.STREAM_INTERRUPTED
                    if saw_document
                    else AdapterErrorCode.BAD_RESPONSE
                ),
                message=(
                    "Ollama stream ended before completion"
                    if saw_document
                    else "Ollama stream returned an empty body"
                ),
                retryable=not emitted_content,
            ),
            emitted_content=emitted_content,
        )

    def _stream_documents(
        self,
        *,
        request_id: str,
        documents: tuple[dict[str, object], ...],
        reasoning_filter: ReasoningFilter,
        emitted_content: bool,
        terminal: _StreamTerminal | None,
    ) -> tuple[tuple[StreamEvent, ...], bool, _StreamTerminal | None, bool]:
        events: list[StreamEvent] = []
        for document in documents:
            if terminal is not None:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama stream continued after completion",
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            done = document.get("done")
            if not isinstance(done, bool):
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama stream record has no done state",
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            message = _mapping(document.get("message"))
            if done and message is None:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama terminal record has no message",
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            content = message.get("content", "") if message is not None else ""
            if not isinstance(content, str):
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama stream content is invalid",
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            if done and message is not None and "content" not in message:
                error = AdapterError(
                    code=AdapterErrorCode.BAD_RESPONSE,
                    message="Ollama terminal record has no content field",
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            try:
                self._reject_observable_thinking(document, message)
            except AdapterFailure as failure:
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(
                                request_id, failure.error, emitted_content=emitted_content
                            ),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            visible = reasoning_filter.feed(content)
            if reasoning_filter.saw_reasoning:
                error = AdapterError(
                    code=AdapterErrorCode.INCOMPATIBLE,
                    message="Ollama returned observable reasoning despite think=false",
                    retryable=not emitted_content,
                )
                return (
                    tuple(
                        [
                            *events,
                            self._stream_error(request_id, error, emitted_content=emitted_content),
                        ]
                    ),
                    emitted_content,
                    terminal,
                    True,
                )
            if done:
                remaining, unclosed = reasoning_filter.finish()
                if unclosed:
                    error = AdapterError(
                        code=AdapterErrorCode.INCOMPATIBLE,
                        message="Ollama returned observable reasoning despite think=false",
                        retryable=not emitted_content,
                    )
                    return (
                        tuple(
                            [
                                *events,
                                self._stream_error(
                                    request_id, error, emitted_content=emitted_content
                                ),
                            ]
                        ),
                        emitted_content,
                        terminal,
                        True,
                    )
                try:
                    usage = self._terminal_usage(document)
                    finish_reason = self._done_reason(document)
                except AdapterFailure as failure:
                    return (
                        tuple(
                            [
                                *events,
                                self._stream_error(
                                    request_id,
                                    failure.error,
                                    emitted_content=emitted_content,
                                ),
                            ]
                        ),
                        emitted_content,
                        terminal,
                        True,
                    )
                terminal = _StreamTerminal(
                    content=visible + remaining,
                    usage=usage,
                    finish_reason=finish_reason,
                )
                continue
            if visible:
                emitted_content = True
                events.append(
                    StreamEvent(
                        kind=StreamEventKind.CONTENT,
                        request_id=request_id,
                        content=visible,
                        emitted_content=True,
                        phase=StreamPhase.AFTER_CONTENT,
                    )
                )
        return tuple(events), emitted_content, terminal, False

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
