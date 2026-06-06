"""Unified observability — pipeline tracing, metrics aggregation, dashboard data.

Port of agentmesh engine observability/index.ts (PipelineTracer) and
dashboard.ts / dashboard-monitor.ts data structures.
"""

from __future__ import annotations

import asyncio
import enum
import time

from .engine_metrics import MetricsCollector, create_metrics
from .engine_tracing import TraceContext


class TraceStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelineEventType(enum.StrEnum):
    PIPELINE_START = "PIPELINE_START"
    PIPELINE_STEP = "PIPELINE_STEP"
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
    PIPELINE_ERROR = "PIPELINE_ERROR"


OBSERVABILITY_VERSION = "1.0"


class TraceRecord:
    __slots__ = ("pipeline_id", "step_index", "tool", "action", "started_at", "status", "ended_at", "duration_ms", "input_summary", "output_summary", "collab_task_id")

    def __init__(
        self,
        pipeline_id: str,
        step_index: int,
        tool: str,
        action: str,
        started_at: str,
        status: TraceStatus = TraceStatus.RUNNING,
        ended_at: str | None = None,
        duration_ms: float | None = None,
        input_summary: str = "",
        output_summary: str = "",
        collab_task_id: str | None = None,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.step_index = step_index
        self.tool = tool
        self.action = action
        self.started_at = started_at
        self.status = status
        self.ended_at = ended_at
        self.duration_ms = duration_ms
        self.input_summary = input_summary
        self.output_summary = output_summary
        self.collab_task_id = collab_task_id


class DashboardEvent:
    __slots__ = ("timestamp", "level", "message")

    def __init__(self, timestamp: float, level: str, message: str) -> None:
        self.timestamp = timestamp
        self.level = level
        self.message = message


class PipelineTracer:
    """Records pipeline step traces with lifecycle management."""

    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self._traces: dict[str, list[TraceRecord]] = {}
        self._metrics = metrics or create_metrics()
        self._hermes_url = "http://localhost:9800"
        self._kos_url: str | None = None

    def configure(self, hermes_ops_url: str = "http://localhost:9800", kos_collab_url: str | None = None) -> None:
        self._hermes_url = hermes_ops_url
        self._kos_url = kos_collab_url

    def record(self, event: TraceRecord) -> TraceRecord:
        self._traces.setdefault(event.pipeline_id, []).append(event)
        self._metrics.increment("pipeline_steps_total", {"tool": event.tool})
        return event

    def start_step(self, pipeline_id: str, step_index: int, tool: str, action: str, input_summary: str = "") -> TraceRecord:
        return self.record(TraceRecord(
            pipeline_id=pipeline_id, step_index=step_index, tool=tool, action=action,
            started_at=_now(), input_summary=input_summary,
        ))

    def _find(self, pipeline_id: str, step_index: int) -> TraceRecord | None:
        for s in self._traces.get(pipeline_id, []):
            if s.step_index == step_index and s.status == TraceStatus.RUNNING:
                return s
        return None

    def _finalize(self, step: TraceRecord, status: TraceStatus, output: str) -> None:
        step.ended_at = _now()
        step.duration_ms = time.time() * 1000
        step.status = status
        step.output_summary = output

    def complete_step(self, pipeline_id: str, step_index: int, output_summary: str = "") -> TraceRecord | None:
        step = self._find(pipeline_id, step_index)
        if step is None:
            return None
        self._finalize(step, TraceStatus.COMPLETED, output_summary)
        self._notify("event", {"type": "PIPELINE_STEP_COMPLETED", "payload": {"pipeline_id": pipeline_id, "step_index": step_index, "output": output_summary}})
        self._notify_collab(step.collab_task_id, step_index, "completed", output_summary)
        self._metrics.increment("pipeline_steps_completed")
        return step

    def fail_step(self, pipeline_id: str, step_index: int, error_summary: str = "") -> TraceRecord | None:
        step = self._find(pipeline_id, step_index)
        if step is None:
            return None
        self._finalize(step, TraceStatus.FAILED, error_summary)
        self._notify("event", {"type": "PIPELINE_STEP_FAILED", "payload": {"pipeline_id": pipeline_id, "step_index": step_index, "output": error_summary}})
        self._notify_collab(step.collab_task_id, step_index, "failed", error_summary)
        self._metrics.increment("pipeline_steps_failed")
        return step

    def get_trace(self, pipeline_id: str) -> list[TraceRecord]:
        return list(self._traces.get(pipeline_id, []))

    def get_all_traces(self) -> dict[str, list[TraceRecord]]:
        return dict(self._traces)

    def clear_traces(self, pipeline_id: str | None = None) -> None:
        if pipeline_id:
            self._traces.pop(pipeline_id, None)
        else:
            self._traces.clear()

    @property
    def metrics(self) -> MetricsCollector:
        return self._metrics

    def _notify(self, path: str, payload: dict[str, object]) -> None:
        asyncio.ensure_future(_async_post(f"{self._hermes_url}/{path}", payload))

    def _notify_collab(self, task_id: str | None, step_index: int, status: str, output: str) -> None:
        if not task_id or not self._kos_url:
            return
        asyncio.ensure_future(_async_post(self._kos_url, {
            "task_id": task_id, "step": step_index, "status": status, "output": output,
        }))


class Observability:
    """Unified observability combining pipeline tracing, metrics, and context traces."""

    def __init__(self) -> None:
        self.pipeline_tracer = PipelineTracer()
        self.metrics = self.pipeline_tracer.metrics
        self.active_traces: dict[str, TraceContext] = {}
        self.events: list[DashboardEvent] = []
        self._max_events = 50

    def create_trace(self, trace_id: str | None = None) -> TraceContext:
        ctx = TraceContext(trace_id)
        self.active_traces[ctx.trace_id] = ctx
        return ctx

    def add_event(self, message: str, level: str = "info") -> None:
        self.events.append(DashboardEvent(timestamp=time.time(), level=level, message=message))
        if len(self.events) > self._max_events:
            self.events.pop(0)

    def get_dashboard_data(self) -> dict[str, object]:
        snap = self.metrics.snapshot()
        return {
            "metrics": {
                "counters": snap.counters,
                "gauges": snap.gauges,
                "timers": {k: vars(v) for k, v in snap.timers.items()},
                "histograms": {k: vars(v) for k, v in snap.histograms.items()},
            },
            "pipeline_traces": {
                pid: [{"step_index": r.step_index, "tool": r.tool, "status": r.status.value, "duration_ms": r.duration_ms} for r in recs[-10:]]
                for pid, recs in self.pipeline_tracer.get_all_traces().items()
            },
            "active_trace_count": len(self.active_traces),
            "events": [{"timestamp": e.timestamp, "level": e.level, "message": e.message} for e in self.events[-20:]],
            "timestamp": time.time(),
        }

    def clear(self) -> None:
        self.pipeline_tracer.clear_traces()
        self.active_traces.clear()
        self.events.clear()
        self.metrics.reset()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


async def _async_post(url: str, payload: dict[str, object]) -> None:
    try:
        import httpx  # type: ignore[import-untyped]
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception:
        pass


def create_observability() -> Observability:
    return Observability()
