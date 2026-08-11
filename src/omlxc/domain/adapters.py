"""Infrastructure-neutral backend adapter contract."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from .models import BackendInstance, HealthSnapshot, Job, Placement, RouteRequest


@runtime_checkable
class BackendAdapter(Protocol):
    async def discover(self) -> BackendInstance: ...

    async def health(self) -> HealthSnapshot: ...

    async def list_models(self) -> tuple[Placement, ...]: ...

    async def load_model(self, placement_id: str) -> Job: ...

    async def unload_model(self, placement_id: str) -> Job: ...

    def infer(self, request: RouteRequest) -> AsyncIterator[Mapping[str, JsonValue]]: ...

    def normalize_request(self, request: RouteRequest) -> Mapping[str, JsonValue]: ...

    async def collect_metrics(self) -> Mapping[str, float | int]: ...

    def explain_capabilities(self) -> Mapping[str, str]: ...
