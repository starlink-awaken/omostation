"""Typed, infrastructure-neutral contracts shared by backend adapters."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, runtime_checkable
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .models import DomainModel

MAX_CHAT_TOOLS = 256
# OpenAI-compatible coding clients can generate one bounded, composite tool
# description substantially larger than a human-authored function summary.
# The HTTP ingress still caps the complete request body; keep this per-tool
# limit below that boundary so a valid catalog can reach routing without
# weakening request-size protection.
MAX_CHAT_TOOL_DESCRIPTION_LENGTH = 131_072


class AdapterCapability(StrEnum):
    CHAT = "chat"
    STREAMING = "streaming"
    VISION = "vision"
    EMBEDDING = "embedding"
    MODEL_LIFECYCLE = "model_lifecycle"
    TUNING = "tuning"


class AdapterErrorCode(StrEnum):
    UNREACHABLE = "unreachable"
    INCOMPATIBLE = "incompatible"
    UNSUPPORTED = "unsupported"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_REQUEST = "invalid_request"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    PARTIAL_FAILURE = "partial_failure"
    BAD_RESPONSE = "bad_response"
    STREAM_INTERRUPTED = "stream_interrupted"


class ModelRuntimeState(StrEnum):
    AVAILABLE = "available"
    LOADED = "loaded"
    UNKNOWN = "unknown"


class OperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    UNCHANGED = "unchanged"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class StreamEventKind(StrEnum):
    CONTENT = "content"
    TOOL_CALL = "tool_call"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"


class StreamPhase(StrEnum):
    BEFORE_CONTENT = "before_content"
    AFTER_CONTENT = "after_content"
    COMPLETE = "complete"


class TuneScope(StrEnum):
    GLOBAL = "global"
    MODEL = "model"


class PrepareRejectionCode(StrEnum):
    MODEL = "model_mismatch"
    AUTHORIZATION = "authorization_denied"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CAPABILITY = "capability_missing"
    CONTEXT = "context_exceeded"
    MEMORY = "memory_denied"
    NO_CAPACITY = "no_capacity"
    LOCAL_SECURITY = "local_security_denied"


class PrepareRejection(DomainModel):
    placement_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    reason: PrepareRejectionCode


class AdapterError(DomainModel):
    code: AdapterErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
    http_status: int | None = Field(default=None, ge=100, le=599)
    endpoint: str | None = None
    emitted_content: bool = False
    phase: StreamPhase = StreamPhase.BEFORE_CONTENT

    @model_validator(mode="after")
    def validate_replay_state(self) -> AdapterError:
        expected = StreamPhase.AFTER_CONTENT if self.emitted_content else StreamPhase.BEFORE_CONTENT
        if self.phase is not expected:
            raise ValueError("adapter error phase must match emitted_content replay state")
        return self


class CapabilitySnapshot(DomainModel):
    backend_id: str = Field(min_length=1)
    reachable: bool
    compatible: bool
    model_available: bool
    generation_ready: bool
    observed_at: datetime
    protocol_version: str | None = None
    capabilities: frozenset[AdapterCapability] = frozenset()
    errors: tuple[AdapterError, ...] = ()

    @model_validator(mode="after")
    def validate_readiness_implications(self) -> CapabilitySnapshot:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.generation_ready and not (
            self.reachable and self.compatible and self.model_available
        ):
            raise ValueError("generation_ready requires reachability, compatibility, and a model")
        return self


class ModelRuntime(DomainModel):
    id: str = Field(min_length=1)
    display_name: str | None = None
    state: ModelRuntimeState
    loaded: bool | None
    capabilities: frozenset[AdapterCapability] = frozenset()
    context_limit: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_loaded_state(self) -> ModelRuntime:
        expected = {
            ModelRuntimeState.LOADED: True,
            ModelRuntimeState.AVAILABLE: False,
            ModelRuntimeState.UNKNOWN: None,
        }[self.state]
        if self.loaded is not expected:
            raise ValueError("loaded must agree with runtime state")
        return self


class TextContentBlock(DomainModel):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1)


class ImageURL(DomainModel):
    url: str = Field(min_length=1)
    detail: Literal["auto", "low", "high"] = "auto"

    @field_validator("url")
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        if value.startswith("data:image/"):
            header, separator, payload = value.partition(",")
            if not separator or not header.endswith(";base64") or not payload:
                raise ValueError("image data URL must be base64 encoded")
            try:
                base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("image data URL contains invalid base64") from exc
            return value

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("image URL must use http, https, or an image data URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("image URL must not contain userinfo")
        return value


class ImageContentBlock(DomainModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL


ChatContentBlock = Annotated[TextContentBlock | ImageContentBlock, Field(discriminator="type")]


class ChatToolFunctionCall(DomainModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    arguments: str = Field(max_length=262_144)

    @field_validator("arguments")
    @classmethod
    def require_json_object(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("tool call arguments must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("tool call arguments must encode an object")
        return value


class ChatToolCall(DomainModel):
    id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9._:-]+$")
    type: Literal["function"] = "function"
    function: ChatToolFunctionCall


class ChatToolFunction(DomainModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    description: str = Field(default="", max_length=MAX_CHAT_TOOL_DESCRIPTION_LENGTH)
    parameters: dict[str, object]
    strict: bool = Field(default=False, exclude_if=lambda value: not value)

    @field_validator("parameters")
    @classmethod
    def bound_parameters(cls, value: dict[str, object]) -> dict[str, object]:
        try:
            encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("tool parameters must be JSON compatible") from exc
        if len(encoded) > 262_144:
            raise ValueError("tool parameters exceed the size limit")
        return value


class ChatTool(DomainModel):
    type: Literal["function"] = "function"
    function: ChatToolFunction


class ChatToolChoiceFunction(DomainModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class ChatToolChoice(DomainModel):
    type: Literal["function"] = "function"
    function: ChatToolChoiceFunction


ToolChoice = Literal["auto", "none", "required"] | ChatToolChoice


class ToolFunctionDelta(DomainModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    arguments: str | None = Field(default=None, max_length=262_144)

    @model_validator(mode="after")
    def require_fragment(self) -> ToolFunctionDelta:
        if self.name is None and self.arguments is None:
            raise ValueError("tool function delta must contain a fragment")
        return self


class ToolCallDelta(DomainModel):
    index: int = Field(ge=0, le=127)
    id: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    type: Literal["function"] | None = None
    function: ToolFunctionDelta | None = None

    @model_validator(mode="after")
    def require_fragment(self) -> ToolCallDelta:
        if self.id is None and self.type is None and self.function is None:
            raise ValueError("tool call delta must contain a fragment")
        return self


class ChatMessage(DomainModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | tuple[ChatContentBlock, ...] | None
    tool_calls: tuple[ChatToolCall, ...] = Field(default=(), max_length=128)
    tool_call_id: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9._:-]+$"
    )

    @model_validator(mode="after")
    def validate_role_fields(self) -> ChatMessage:
        empty_content = self.content is None or self.content == "" or self.content == ()
        if self.role in {"system", "user"}:
            if empty_content or self.tool_calls or self.tool_call_id is not None:
                raise ValueError("system and user messages require content only")
        elif self.role == "assistant":
            if empty_content and not self.tool_calls:
                raise ValueError("assistant messages require content or tool calls")
            if self.tool_call_id is not None:
                raise ValueError("assistant messages cannot include tool_call_id")
        elif empty_content or self.tool_calls or self.tool_call_id is None:
            raise ValueError("tool messages require content and tool_call_id")
        return self


class ChatRequest(DomainModel):
    request_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    messages: tuple[ChatMessage, ...] = Field(min_length=1)
    max_tokens: int = Field(default=64, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    tools: tuple[ChatTool, ...] = Field(default=(), max_length=MAX_CHAT_TOOLS)
    tool_choice: ToolChoice | None = None

    @model_validator(mode="after")
    def validate_tool_choice(self) -> ChatRequest:
        if self.tool_choice is not None and not self.tools:
            raise ValueError("tool_choice requires tools")
        return self


class TokenUsage(DomainModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ChatResult(DomainModel):
    request_id: str = Field(min_length=1)
    success: bool
    content: str = ""
    tool_calls: tuple[ChatToolCall, ...] = Field(default=(), max_length=128)
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    error: AdapterError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> ChatResult:
        if self.success == (self.error is not None):
            raise ValueError("successful results cannot have errors and failures require one")
        if self.success and not self.content and not self.tool_calls:
            raise ValueError("successful chat results require content or tool calls")
        return self


class EmbeddingRequest(DomainModel):
    request_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input: str | tuple[str, ...]

    @field_validator("input")
    @classmethod
    def require_input(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, str) and not value:
            raise ValueError("embedding input must not be empty")
        if isinstance(value, tuple) and (not value or any(not item for item in value)):
            raise ValueError("embedding inputs must not be empty")
        return value


class EmbeddingResult(DomainModel):
    request_id: str = Field(min_length=1)
    status: OperationStatus
    embeddings: tuple[tuple[float, ...], ...] = ()
    usage: TokenUsage | None = None
    error: AdapterError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> EmbeddingResult:
        if self.status is OperationStatus.SUCCEEDED:
            if not self.embeddings or self.error is not None:
                raise ValueError("successful embedding results require vectors and no error")
        elif self.status in {OperationStatus.UNSUPPORTED, OperationStatus.FAILED}:
            if self.error is None or self.embeddings:
                raise ValueError("failed embedding results require an error and no vectors")
        else:
            raise ValueError("embedding result status is invalid")
        return self


class LifecycleResult(DomainModel):
    model_id: str = Field(min_length=1)
    status: OperationStatus
    changed: bool
    idempotency_key: str | None = None
    error: AdapterError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> LifecycleResult:
        if self.status is OperationStatus.SUCCEEDED:
            valid = self.changed and self.error is None
        elif self.status is OperationStatus.UNCHANGED:
            valid = not self.changed and self.error is None
        else:
            valid = not self.changed and self.error is not None
        if not valid:
            raise ValueError("lifecycle status, changed, and error fields are inconsistent")
        return self


class TuneSettings(DomainModel):
    max_context_window: int | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    ttl_seconds: int | None = Field(default=None, ge=0)
    is_pinned: bool | None = None


class TuneRequest(DomainModel):
    scope: TuneScope
    settings: TuneSettings
    model_id: str | None = None
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def require_model_for_model_scope(self) -> TuneRequest:
        if self.scope is TuneScope.MODEL and not self.model_id:
            raise ValueError("model scope tuning requires model_id")
        if self.scope is TuneScope.GLOBAL and self.model_id is not None:
            raise ValueError("global tuning cannot include model_id")
        return self


class TuneResult(DomainModel):
    scope: TuneScope
    model_id: str | None = None
    status: OperationStatus
    changed_fields: tuple[str, ...] = ()
    idempotency_key: str | None = None
    error: AdapterError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> TuneResult:
        if self.status is OperationStatus.SUCCEEDED:
            valid = bool(self.changed_fields) and self.error is None
        elif self.status is OperationStatus.UNCHANGED:
            valid = not self.changed_fields and self.error is None
        else:
            valid = not self.changed_fields and self.error is not None
        if not valid:
            raise ValueError("tune status, changed_fields, and error fields are inconsistent")
        return self


class StreamEvent(DomainModel):
    kind: StreamEventKind
    request_id: str = Field(min_length=1)
    content: str = ""
    tool_calls: tuple[ToolCallDelta, ...] = Field(default=(), max_length=128)
    usage: TokenUsage | None = None
    finish_reason: str | None = None
    error: AdapterError | None = None
    emitted_content: bool
    phase: StreamPhase
    placement_id: str | None = None
    backend_id: str | None = None
    prepare_rejections: tuple[PrepareRejection, ...] = ()

    @model_validator(mode="after")
    def validate_event(self) -> StreamEvent:
        if self.kind is StreamEventKind.ERROR:
            if self.error is None:
                raise ValueError("stream error events require an error")
            if (
                self.error.emitted_content is not self.emitted_content
                or self.error.phase is not self.phase
            ):
                raise ValueError("stream error replay state must match the event")
        elif self.error is not None:
            raise ValueError("non-error stream events cannot include an error")
        if self.prepare_rejections and (
            self.kind is not StreamEventKind.ERROR
            or self.phase is not StreamPhase.BEFORE_CONTENT
            or self.emitted_content
        ):
            raise ValueError("prepare rejections require a pre-content stream error")

        if self.kind is StreamEventKind.CONTENT and (
            not self.content
            or not self.emitted_content
            or self.phase is not StreamPhase.AFTER_CONTENT
        ):
            raise ValueError("content events require emitted content and after-content phase")
        if self.kind is StreamEventKind.TOOL_CALL and (
            not self.tool_calls
            or not self.emitted_content
            or self.phase is not StreamPhase.AFTER_CONTENT
        ):
            raise ValueError("tool call events require deltas and after-content phase")
        if self.kind is not StreamEventKind.TOOL_CALL and self.tool_calls:
            raise ValueError("only tool call events can include tool call deltas")
        if self.kind is StreamEventKind.USAGE and self.usage is None:
            raise ValueError("usage events require usage")
        if self.kind is StreamEventKind.DONE and self.phase is not StreamPhase.COMPLETE:
            raise ValueError("done events require complete phase")
        return self


@runtime_checkable
class BackendAdapter(Protocol):
    async def discover(self) -> CapabilitySnapshot: ...

    async def list_models(self) -> tuple[ModelRuntime, ...]: ...

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult: ...

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> LifecycleResult: ...

    async def tune(self, request: TuneRequest) -> TuneResult: ...

    async def chat(self, request: ChatRequest) -> ChatResult: ...

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult: ...

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]: ...
