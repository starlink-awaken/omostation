from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from runtime.executor.dsl_types import CallResult, CallTrace


@dataclass
class TracerStats:
    total_traces: int = 0
    pending_traces: int = 0
    agent_calls: int = 0
    skill_calls: int = 0
    tool_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0


@dataclass
class _PendingTrace:
    trace_id: str = ""
    parent_trace_id: str = ""
    step_name: str = ""
    call_type: str = "agent"
    target: str = ""
    start_time: float = 0.0
    input_summary: dict[str, Any] = field(default_factory=dict)


class ExecutionTracer:
    def __init__(self, events_enabled: bool = True) -> None:
        self._traces: dict[str, CallTrace] = {}
        self._pending: dict[str, _PendingTrace] = {}
        self._events_enabled = events_enabled

    def start_trace(
        self, step_name: str, call_type: str, target: str
    ) -> str:
        trace_id = uuid.uuid4().hex[:32]
        pending = _PendingTrace(
            trace_id=trace_id,
            step_name=step_name,
            call_type=call_type,
            target=target,
            start_time=time.time(),
        )
        self._pending[trace_id] = pending
        return trace_id

    def end_trace(self, trace_id: str, result: CallResult) -> CallTrace:
        pending = self._pending.pop(trace_id, None)
        if not pending:
            raise ValueError(f"Trace not found: {trace_id}")

        end_time = time.time()
        duration_ms = (end_time - pending.start_time) * 1000

        trace = CallTrace(
            trace_id=pending.trace_id,
            parent_trace_id=pending.parent_trace_id,
            step_name=pending.step_name,
            call_type=pending.call_type,
            target=pending.target,
            start_time=pending.start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=result.success,
            error=result.error,
            tokens_used=result.tokens_used,
            retry_count=result.retry_count,
            input_summary=pending.input_summary if hasattr(pending, "input_summary") else {},
            output_summary=result.outputs or {},
        )
        self._traces[trace_id] = trace
        return trace

    def get_traces(self) -> list[CallTrace]:
        return list(self._traces.values())

    def get_trace(self, trace_id: str) -> CallTrace | None:
        return self._traces.get(trace_id)

    def clear(self) -> None:
        self._traces.clear()
        self._pending.clear()

    def get_stats(self) -> TracerStats:
        stats = TracerStats(
            total_traces=len(self._traces),
            pending_traces=len(self._pending),
        )
        for trace in self._traces.values():
            if trace.call_type == "agent":
                stats.agent_calls += 1
            elif trace.call_type == "skill":
                stats.skill_calls += 1
            elif trace.call_type == "tool":
                stats.tool_calls += 1
            if trace.success:
                stats.successful_calls += 1
            else:
                stats.failed_calls += 1
            stats.total_duration_ms += trace.duration_ms
            stats.total_tokens += trace.tokens_used or 0
        return stats

    def get_traces_by_target(self, target: str) -> list[CallTrace]:
        return [t for t in self._traces.values() if t.target == target]

    def get_traces_by_type(self, call_type: str) -> list[CallTrace]:
        return [t for t in self._traces.values() if t.call_type == call_type]

    def get_failed_traces(self) -> list[CallTrace]:
        return [t for t in self._traces.values() if not t.success]


def create_execution_tracer(events_enabled: bool = True) -> ExecutionTracer:
    return ExecutionTracer(events_enabled=events_enabled)
