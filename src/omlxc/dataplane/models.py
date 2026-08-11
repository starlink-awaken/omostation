"""Typed data-plane requests, outcomes, and extension protocols."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from omlxc.domain.protocols import BackendAdapter, ChatResult, StreamPhase


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


@dataclass(frozen=True, slots=True)
class ChatExecution:
    request_id: str
    model_id: str
    success: bool
    placement_id: str | None
    attempted_placements: tuple[str, ...]
    result: ChatResult | None = None
    error: ExecutionError | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingExecution:
    request_id: str
    model_id: str
    placement_id: str | None
    attempted_placements: tuple[str, ...]
    embeddings: tuple[tuple[float, ...], ...] = ()
    error: ExecutionError | None = None


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


def validate_vectors(vectors: tuple[tuple[float, ...], ...], *, expected_count: int) -> bool:
    if len(vectors) != expected_count or not vectors:
        return False
    dimension = len(vectors[0])
    return dimension > 0 and all(
        len(vector) == dimension and all(math.isfinite(value) for value in vector)
        for vector in vectors
    )
