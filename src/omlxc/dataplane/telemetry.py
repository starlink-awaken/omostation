"""Content-free route audit and request metric persistence bridge."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from omlxc.domain import RouteDecision
from omlxc.scheduler import RouteFailure
from omlxc.storage import MetricRecord, RouteAuditWrite, SQLiteRuntimeStore

RoutePlan = RouteDecision | RouteFailure


class TelemetrySink(Protocol):
    async def record_route(self, plan: RoutePlan) -> None: ...

    def record_metric(self, *, request_id: str, latency_ms: float, success: bool) -> bool: ...


class RouteTelemetryRecorder:
    def __init__(self, *, now: Callable[[], datetime]) -> None:
        self._now = now

    async def record_route(self, store: SQLiteRuntimeStore, plan: RoutePlan) -> None:
        if isinstance(plan, RouteDecision):
            candidates = tuple(
                f"{placement_id}@{plan.candidate_scores[placement_id]:.12f}"
                for placement_id in plan.candidates
            )
            selected = plan.selected_placement_id
        else:
            candidates = ()
            selected = None
        await store.append_route_audit(
            RouteAuditWrite(
                request_id=plan.request_id,
                observed_at=self._now(),
                selected_placement_id=selected,
                candidates=candidates,
                rejections=plan.rejected,
                config_revision=plan.config_version,
            )
        )

    def record_metric(
        self,
        store: SQLiteRuntimeStore,
        *,
        request_id: str,
        latency_ms: float,
        success: bool,
    ) -> bool:
        return store.accept_metric(MetricRecord(request_id, self._now(), latency_ms, success))


class BoundRouteTelemetry:
    """Bind the Task 5 store once so execution cannot bypass route telemetry."""

    def __init__(self, store: SQLiteRuntimeStore, recorder: RouteTelemetryRecorder) -> None:
        self._store = store
        self._recorder = recorder

    async def record_route(self, plan: RoutePlan) -> None:
        await self._recorder.record_route(self._store, plan)

    def record_metric(self, *, request_id: str, latency_ms: float, success: bool) -> bool:
        return self._recorder.record_metric(
            self._store,
            request_id=request_id,
            latency_ms=latency_ms,
            success=success,
        )
