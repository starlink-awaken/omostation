"""Typed ports between the HTTP surface and daemon-owned services."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Protocol

from omlxc.dataplane import ChatExecution, EmbeddingExecution, RerankExecution
from omlxc.domain import Job, ModelSpec, Node, RouteDecision, RouteRequest
from omlxc.domain.protocols import ChatRequest, EmbeddingRequest, StreamEvent
from omlxc.events import EventSubscription
from omlxc.storage import DurableEventRecord


class ControlService(Protocol):
    async def health(self) -> Mapping[str, object]: ...

    async def list_nodes(self, *, after: str | None, limit: int) -> tuple[Node, ...]: ...

    async def list_models(self, *, after: str | None, limit: int) -> tuple[ModelSpec, ...]: ...

    async def plan_route(self, request: RouteRequest) -> RouteDecision: ...

    async def list_jobs(self, *, after: str | None, limit: int) -> tuple[Job, ...]: ...

    async def get_job(self, job_id: str) -> Job | None: ...

    async def load_model(self, model_id: str, *, idempotency_key: str) -> Job: ...

    async def unload_model(self, model_id: str, *, idempotency_key: str) -> Job: ...

    async def cancel_job(self, job_id: str) -> Job | None: ...

    async def metrics_summary(self) -> Mapping[str, object]: ...


class InferenceService(Protocol):
    async def list_openai_models(self) -> tuple[str, ...]: ...

    async def chat(
        self, route: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> ChatExecution: ...

    def stream_chat(
        self, route: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> AsyncIterator[StreamEvent]: ...

    async def embed(
        self, route: RouteRequest, request: EmbeddingRequest, *, deadline: float
    ) -> EmbeddingExecution: ...

    async def rerank(
        self, *, request_id: str, query: str, documents: tuple[str, ...]
    ) -> RerankExecution: ...


class EventService(Protocol):
    async def replay_events(
        self, *, after_sequence: int, limit: int
    ) -> tuple[DurableEventRecord, ...]: ...

    def subscribe_events(self) -> EventSubscription: ...
