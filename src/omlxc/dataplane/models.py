"""Typed data-plane requests, outcomes, and extension protocols."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from omlxc.domain import RouteProfile
from omlxc.domain.protocols import BackendAdapter, ChatResult, StreamPhase
from omlxc.scheduler import RejectionCode

_SAFE_PLACEMENT_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def safe_placement_id(value: str) -> str:
    if _SAFE_PLACEMENT_ID.fullmatch(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"opaque:{digest}"


def safe_prepare_rejections(
    rejections: tuple[tuple[str, RejectionCode], ...],
) -> tuple[tuple[str, RejectionCode], ...]:
    return tuple((safe_placement_id(placement_id), reason) for placement_id, reason in rejections)


class ExecutionErrorCode(StrEnum):
    NO_CANDIDATE = "no_candidate"
    NO_CAPACITY = "no_capacity"
    UNSUPPORTED = "unsupported"
    TIMEOUT = "timeout"
    INVALID_BINDING = "invalid_binding"
    BAD_RESPONSE = "bad_response"
    BACKEND_FAILURE = "backend_failure"


@dataclass(frozen=True, slots=True)
class ExecutionError:
    code: ExecutionErrorCode
    retryable: bool
    phase: StreamPhase = StreamPhase.BEFORE_CONTENT
    emitted_content: bool = False
    reason: str = ""
    prepare_rejections: tuple[tuple[str, RejectionCode], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prepare_rejections",
            safe_prepare_rejections(self.prepare_rejections),
        )


@dataclass(frozen=True, slots=True)
class ChatExecution:
    request_id: str
    model_id: str
    success: bool
    placement_id: str | None
    attempted_placements: tuple[str, ...]
    result: ChatResult | None = None
    error: ExecutionError | None = None
    backend_id: str | None = None
    profile: RouteProfile | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingExecution:
    request_id: str
    model_id: str
    placement_id: str | None
    attempted_placements: tuple[str, ...]
    embeddings: tuple[tuple[float, ...], ...] = ()
    error: ExecutionError | None = None
    backend_id: str | None = None
    profile: RouteProfile | None = None


@dataclass(frozen=True, slots=True)
class AdapterBinding:
    backend_id: str
    adapter: BackendAdapter

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("backend binding ID is required")


@dataclass(frozen=True, slots=True)
class RerankRequest:
    request_id: str
    query: str
    documents: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.request_id or not self.query or not self.documents:
            raise ValueError("rerank request identity, query, and documents are required")
        if any(not document for document in self.documents):
            raise ValueError("rerank documents must not be empty")


@dataclass(frozen=True, slots=True)
class RerankResult:
    scores: tuple[float, ...]
    placement_id: str
    backend_id: str
    profile: RouteProfile

    def __post_init__(self) -> None:
        if not self.placement_id or not self.backend_id:
            raise ValueError("rerank route metadata is required")


class Reranker(Protocol):
    async def rerank(self, request: RerankRequest) -> RerankResult: ...


@dataclass(frozen=True, slots=True)
class RankedItem:
    index: int
    score: float


@dataclass(frozen=True, slots=True)
class RerankExecution:
    request_id: str
    items: tuple[RankedItem, ...]
    error: ExecutionError | None = None
    placement_id: str | None = None
    backend_id: str | None = None
    profile: RouteProfile | None = None


def validate_vectors(vectors: tuple[tuple[float, ...], ...], *, expected_count: int) -> bool:
    if len(vectors) != expected_count or not vectors:
        return False
    dimension = len(vectors[0])
    return dimension > 0 and all(
        len(vector) == dimension and all(math.isfinite(value) for value in vector)
        for vector in vectors
    )
