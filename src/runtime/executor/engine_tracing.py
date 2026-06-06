"""Distributed tracing — span context, parent-child relationships, export.

Port of agentmesh engine trace-types.ts, trace-context.ts, trace-exporter.ts.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

SpanTags = dict[str, str | int | bool]
SpanStatus = str  # "pending" | "success" | "error"


@dataclass
class Span:
    trace_id: str
    span_id: str
    operation_name: str
    start_time: float
    tags: SpanTags = field(default_factory=dict)
    status: SpanStatus = "pending"
    parent_span_id: str | None = None
    end_time: float | None = None
    duration: float | None = None
    error: str | None = None


@dataclass
class TraceTreeNode:
    span: Span
    children: list[TraceTreeNode] = field(default_factory=list)
    depth: int = 0


@dataclass
class TraceMetrics:
    total_spans: int = 0
    total_duration: float = 0.0
    slowest_span: Span | None = None
    error_count: int = 0
    span_count_by_operation: dict[str, int] = field(default_factory=dict)


class TraceContext:
    """Manages a single trace with parent-child span relationships."""

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.root_span_id = uuid.uuid4().hex
        self.spans: dict[str, Span] = {}
        self.created_at = time.time()
        root = Span(
            trace_id=self.trace_id,
            span_id=self.root_span_id,
            operation_name="root",
            start_time=time.time(),
            tags={"source": "orchestrator"},
            status="pending",
        )
        self.spans[self.root_span_id] = root

    def create_span(
        self,
        operation_name: str,
        parent_span_id: str | None = None,
        tags: SpanTags | None = None,
    ) -> Span:
        span = Span(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            tags=tags or {},
            status="pending",
        )
        self.spans[span.span_id] = span
        return span

    def finish_span(
        self,
        span_id: str,
        status: SpanStatus = "success",
        error: str | None = None,
    ) -> None:
        span = self.spans.get(span_id)
        if span is None:
            return
        span.end_time = time.time()
        span.duration = (span.end_time - span.start_time) * 1000.0
        span.status = status
        if error:
            span.error = error

    def get_spans(self) -> list[Span]:
        return list(self.spans.values())

    def get_root_span(self) -> Span | None:
        return self.spans.get(self.root_span_id)

    def get_trace_tree(self) -> TraceTreeNode:
        root = self.get_root_span()
        if root is None:
            return TraceTreeNode(
                span=Span(
                    trace_id=self.trace_id,
                    span_id="unknown",
                    operation_name="unknown",
                    start_time=self.created_at,
                    tags={},
                    status="pending",
                ),
                children=[],
                depth=0,
            )
        return self._build_tree(root.span_id)

    def get_metrics(self) -> TraceMetrics:
        spans = self.get_spans()
        completed = [s for s in spans if s.end_time is not None]
        root = self.get_root_span()
        total_duration = root.duration if root else 0.0
        slowest = spans[0] if spans else Span(trace_id="", span_id="", operation_name="", start_time=0)
        for s in completed:
            if (s.duration or 0) > (slowest.duration or 0):
                slowest = s
        error_count = sum(1 for s in spans if s.status == "error")
        by_op: dict[str, int] = {}
        for s in spans:
            by_op[s.operation_name] = by_op.get(s.operation_name, 0) + 1
        return TraceMetrics(
            total_spans=len(spans),
            total_duration=total_duration or 0.0,
            slowest_span=slowest,
            error_count=error_count,
            span_count_by_operation=by_op,
        )

    def _build_tree(self, span_id: str, depth: int = 0) -> TraceTreeNode:
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span not found: {span_id}")
        children = [
            self._build_tree(s.span_id, depth + 1)
            for s in self.get_spans()
            if s.parent_span_id == span_id
        ]
        return TraceTreeNode(span=span, children=children, depth=depth)


class TraceContextManager:
    """Manages multiple TraceContext instances."""

    def __init__(self) -> None:
        self._contexts: dict[str, TraceContext] = {}

    def create(self, trace_id: str | None = None) -> TraceContext:
        ctx = TraceContext(trace_id)
        self._contexts[ctx.trace_id] = ctx
        return ctx

    def get(self, trace_id: str) -> TraceContext | None:
        return self._contexts.get(trace_id)

    def delete(self, trace_id: str) -> None:
        self._contexts.pop(trace_id, None)

    def list(self) -> list[TraceContext]:
        return list(self._contexts.values())

    def size(self) -> int:
        return len(self._contexts)

    def clear(self) -> None:
        self._contexts.clear()


class TraceExporter:
    """Export TraceContext in multiple formats (JSON, Mermaid, text, markdown)."""

    def export_to_json(self, ctx: TraceContext, include_tags: bool = False, errors_only: bool = False) -> str:
        spans = ctx.get_spans()
        if errors_only:
            spans = [s for s in spans if s.status == "error"]
        data: dict[str, Any] = {
            "traceId": ctx.trace_id,
            "rootSpanId": ctx.root_span_id,
            "createdAt": ctx.created_at,
            "metrics": {
                "totalSpans": len(spans),
                "totalDuration": ctx.get_metrics().total_duration,
                "errorCount": sum(1 for s in spans if s.status == "error"),
            },
            "spans": [],
        }
        for s in spans:
            entry: dict[str, Any] = {
                "spanId": s.span_id,
                "operationName": s.operation_name,
                "startTime": s.start_time,
                "endTime": s.end_time,
                "duration": s.duration,
                "status": s.status,
            }
            if s.parent_span_id:
                entry["parentSpanId"] = s.parent_span_id
            if include_tags and s.tags:
                entry["tags"] = s.tags
            if s.error:
                entry["error"] = s.error
            data["spans"].append(entry)
        return json.dumps(data, indent=2, default=str)

    def export_to_mermaid(self, ctx: TraceContext) -> str:
        lines = ["timeline", f"    title Trace: {ctx.trace_id}"]
        tree = ctx.get_trace_tree()

        def _walk(node: TraceTreeNode, depth: int = 0) -> None:
            indent = "  " * (depth + 1)
            dur = f"{node.span.duration:.0f}ms" if node.span.duration else "running"
            icon = ""
            if node.span.status == "error":
                icon = " [ERROR]"
            elif node.span.status == "success":
                icon = " [OK]"
            lines.append(f"{indent}{node.span.operation_name} : {dur}{icon}")
            for child in node.children:
                _walk(child, depth + 1)

        _walk(tree)
        return "\n".join(lines)

    def export_to_text(self, ctx: TraceContext) -> str:
        m = ctx.get_metrics()
        ctx.get_root_span()
        lines = [
            "=" * 60,
            "  Trace Report",
            "=" * 60,
            f"  Trace ID    : {ctx.trace_id}",
            f"  Root Span   : {ctx.root_span_id}",
            f"  Created At  : {time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ctx.created_at))}",
            "",
            f"  Total Spans : {m.total_spans}",
            f"  Duration    : {m.total_duration:.0f}ms",
            f"  Errors      : {m.error_count}",
            "",
            "  Span Count by Operation:",
        ]
        for op, cnt in sorted(m.span_count_by_operation.items()):
            lines.append(f"    {op}: {cnt}")
        lines.append("")
        lines.append("  Trace Tree:")
        tree = ctx.get_trace_tree()

        def _print_tree(node: TraceTreeNode, prefix: str = "", is_last: bool = True) -> None:
            conn = "└─" if is_last else "├─"
            dur = f" ({node.span.duration:.0f}ms)" if node.span.duration else ""
            status = ""
            if node.span.status == "error":
                status = " ERROR"
                if node.span.error:
                    status += f" {node.span.error}"
            elif node.span.status == "success":
                status = " OK"
            else:
                status = " PENDING"
            lines.append(f"{prefix}{conn} {node.span.operation_name}{dur}{status}")
            child_prefix = prefix + ("  " if is_last else "│ ")
            for i, child in enumerate(node.children):
                _print_tree(child, child_prefix, i == len(node.children) - 1)

        _print_tree(tree)
        return "\n".join(lines)

    def export_to_summary(self, ctx: TraceContext) -> str:
        m = ctx.get_metrics()
        return f"Trace {ctx.trace_id}: {m.total_spans} spans, {m.total_duration:.0f}ms, {m.error_count} errors"

    def export_to_markdown(self, ctx: TraceContext) -> str:
        m = ctx.get_metrics()
        lines = [
            f"## Trace Report: {ctx.trace_id}",
            "",
            f"**Created:** {time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ctx.created_at))}",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Spans | {m.total_spans} |",
            f"| Total Duration | {m.total_duration:.0f}ms |",
            f"| Errors | {m.error_count} |",
            f"| Slowest Span | {m.slowest_span.operation_name if m.slowest_span else 'N/A'} |",
            "",
            "| Operation | Duration | Status | Error |",
            "|-----------|----------|--------|-------|",
        ]
        for s in ctx.get_spans():
            dur = f"{s.duration:.0f}ms" if s.duration else "running"
            err = s.error or ""
            lines.append(f"| {s.operation_name} | {dur} | {s.status} | {err} |")
        return "\n".join(lines)


def create_trace_context(trace_id: str | None = None) -> TraceContext:
    return TraceContext(trace_id)


def create_trace_context_manager() -> TraceContextManager:
    return TraceContextManager()


def create_trace_exporter() -> TraceExporter:
    return TraceExporter()
