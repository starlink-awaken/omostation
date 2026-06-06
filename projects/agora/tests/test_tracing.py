"""Tests for Agora tracing module."""

from __future__ import annotations

import asyncio
import time

import pytest
from agora.tracing import (
    Span,
    TraceConfig,
    TraceContext,
    Tracer,
    start_trace,
    trace_from_headers,
    tracer,
    with_span_and_timeout,
)

# ============================================================================
# TraceContext
# ============================================================================


class TestTraceContext:
    def test_create_defaults(self):
        ctx = TraceContext(trace_id="abc", parent_id="", service="test-svc")
        assert ctx.trace_id == "abc"
        assert ctx.parent_id == ""
        assert ctx.service == "test-svc"
        assert ctx.phase == ""
        assert ctx.tags == {}
        assert ctx.started_at > 0

    def test_create_with_all_fields(self):
        ctx = TraceContext(
            trace_id="tt-xyz",
            parent_id="p1",
            service="svc",
            phase="research",
            tags={"env": "test"},
        )
        assert ctx.phase == "research"
        assert ctx.tags == {"env": "test"}


# ============================================================================
# Span
# ============================================================================


class TestSpan:
    def test_create_defaults(self):
        s = Span(id="s1", type="entry", name="root")
        assert s.status == "pending"
        assert s.duration_ms == 0.0
        assert s.ended_at == 0.0
        assert s.error == ""
        assert s.events == []
        assert s.children == []

    def test_create_entry(self):
        s = Span(id="s1", type="entry", name="root")
        assert s.type == "entry"

    def test_create_internal(self):
        s = Span(id="s2", type="internal", name="process")
        assert s.type == "internal"

    def test_create_exit(self):
        s = Span(id="s3", type="exit", name="http-call")
        assert s.type == "exit"

    def test_finish_success(self):
        s = Span(id="s1", type="entry", name="root")
        time.sleep(0.001)
        s.finish("success", "")
        assert s.status == "success"
        assert s.duration_ms > 0
        assert s.ended_at > 0

    def test_finish_error(self):
        s = Span(id="s1", type="entry", name="root")
        s.finish("error", "connection refused")
        assert s.status == "error"
        assert s.error == "connection refused"

    def test_finish_without_error_string(self):
        s = Span(id="s1", type="entry", name="root")
        s.finish()  # default status = "success", error = ""
        assert s.status == "success"
        assert s.error == ""


# ============================================================================
# TraceConfig
# ============================================================================


class TestTraceConfig:
    def test_defaults(self):
        cfg = TraceConfig()
        assert cfg.enabled is True
        assert cfg.default_timeout_ms == 30000
        assert cfg.phase_timeout_ms == 300000
        assert cfg.model_timeout_ms == 60000

    def test_custom(self):
        cfg = TraceConfig(enabled=False, default_timeout_ms=5000)
        assert cfg.enabled is False
        assert cfg.default_timeout_ms == 5000
        assert cfg.phase_timeout_ms == 300000  # unchanged


# ============================================================================
# Tracer — Lifecycle
# ============================================================================


class TestTracerInit:
    def test_default_config(self):
        t = Tracer()
        assert t.config.enabled is True
        assert t.context is None
        assert t.root_span is None
        assert t.active_spans == []

    def test_custom_config(self):
        cfg = TraceConfig(enabled=False)
        t = Tracer(config=cfg)
        assert t.config.enabled is False

    def test_global_instance(self):
        assert isinstance(tracer, Tracer)


class TestTracerStartTrace:
    def test_start_basic(self):
        t = Tracer()
        ctx = t.start_trace("my-service")
        assert ctx.service == "my-service"
        assert ctx.trace_id.startswith("tt-")
        assert ctx.phase == ""
        assert t.context is ctx
        assert t.root_span is not None
        assert t.root_span.type == "entry"
        assert t.active_spans == [t.root_span]

    def test_start_with_phase(self):
        t = Tracer()
        ctx = t.start_trace("svc", "research")
        assert ctx.phase == "research"
        assert "research" in ctx.trace_id

    def test_consecutive_traces(self):
        """Starting a new trace should replace the old one."""
        t = Tracer()
        ctx1 = t.start_trace("svc1")
        ctx2 = t.start_trace("svc2")
        assert ctx1.trace_id != ctx2.trace_id
        assert t.context is ctx2


class TestTracerSetContext:
    def test_set_context(self):
        t = Tracer()
        ctx = TraceContext(trace_id="external-1", parent_id="", service="svc")
        t.set_context(ctx)
        assert t.context is ctx
        assert t.root_span is not None
        assert t.root_span.id == "external-1-resume"

    def test_set_context_overrides_previous(self):
        t = Tracer()
        t.start_trace("svc1")
        ctx2 = TraceContext(trace_id="ext-2", parent_id="", service="svc2")
        t.set_context(ctx2)
        assert t.context is ctx2

    def test_get_context(self):
        t = Tracer()
        assert t.get_context() is None
        ctx = t.start_trace("svc")
        assert t.get_context() is ctx


# ============================================================================
# Tracer — Headers
# ============================================================================


class TestTracerHeaders:
    def test_from_headers_valid(self):
        ctx = Tracer.from_headers(
            {
                "x-trace-id": "abc-123",
                "x-parent-id": "parent-1",
                "x-trace-phase": "research",
            },
            "svc",
        )
        assert ctx is not None
        assert ctx.trace_id == "abc-123"
        assert ctx.parent_id == "parent-1"
        assert ctx.phase == "research"
        assert ctx.service == "svc"

    def test_from_headers_no_trace_id(self):
        ctx = Tracer.from_headers({"Content-Type": "application/json"}, "svc")
        assert ctx is None

    def test_from_headers_empty(self):
        ctx = Tracer.from_headers({}, "svc")
        assert ctx is None

    def test_to_headers_no_context(self):
        t = Tracer()
        assert t.to_headers() == {}

    def test_to_headers_with_context(self):
        t = Tracer()
        t.start_trace("svc", "phase1")
        headers = t.to_headers()
        assert "X-Trace-ID" in headers
        assert headers["X-Trace-ID"].startswith("tt-")
        assert "X-Parent-ID" in headers
        assert headers["X-Trace-Phase"] == "phase1"

    def test_roundtrip_headers(self):
        """to_headers() uses capitalized keys; from_headers() also checks lowercase then uppercase."""
        t = Tracer()
        ctx = t.start_trace("svc1")
        headers = t.to_headers()
        Tracer()
        recovered = Tracer.from_headers(headers, "svc2")
        assert recovered is not None
        assert recovered.trace_id == ctx.trace_id
        assert recovered.service == "svc2"  # service passed separately


# ============================================================================
# Tracer — Span Lifecycle
# ============================================================================


class TestTracerSpanLifecycle:
    def test_start_entry_span(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("http-handle")
        assert span.type == "entry"
        assert span.name == "http-handle"
        assert span in t.root_span.children
        assert t.active_spans[-1] is span  # now active

    def test_start_entry_span_no_context(self):
        t = Tracer()
        with pytest.raises(ValueError, match="No trace context"):
            t.start_entry_span("fail")

    def test_start_internal_span(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_internal_span("process")
        assert span.type == "internal"
        assert span.name == "process"

    def test_start_internal_span_no_context(self):
        t = Tracer()
        with pytest.raises(ValueError, match="No trace context"):
            t.start_internal_span("fail")

    def test_nested_spans(self):
        """entry → internal → internal"""
        t = Tracer()
        t.start_trace("svc")
        entry = t.start_entry_span("request")
        internal1 = t.start_internal_span("auth")
        internal2 = t.start_internal_span("db-query")
        assert t.active_spans[-1] is internal2
        assert internal2 in internal1.children
        assert internal1 in entry.children

    def test_get_active_span(self):
        t = Tracer()
        assert t.get_active_span() is None
        t.start_trace("svc")
        assert t.get_active_span() is t.root_span
        span = t.start_entry_span("work")
        assert t.get_active_span() is span

    def test_finish_span_pops_active(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("work")
        assert t.active_spans[-1] is span
        t.finish_span(span, "success")
        assert span not in t.active_spans
        assert t.active_spans[-1] is t.root_span
        assert span.status == "success"

    def test_finish_span_idempotent(self):
        """Finishing a span already popped should not error."""
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("work")
        t.finish_span(span)
        t.finish_span(span)  # second call — no-op
        assert span not in t.active_spans

    def test_finish_span_error_status(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("work")
        t.finish_span(span, "error", "timeout")
        assert span.status == "error"
        assert span.error == "timeout"

    def test_full_tree_trace(self):
        """Simulate a complete trace with multiple levels."""
        t = Tracer()
        t.start_trace("api", "search")
        entry = t.start_entry_span("/search")
        internal = t.start_internal_span("llm-call")
        t.finish_span(internal, "success")
        internal2 = t.start_internal_span("post-process")
        t.finish_span(internal2, "success")
        t.finish_span(entry, "success")

        record = t.get_trace_record()
        assert record is not None
        assert len(record["spans"]) == 4  # root + entry + 2 internal
        assert record["summary"]["status"] == "success"
        assert record["summary"]["error_count"] == 0

    def test_tree_with_errors(self):
        t = Tracer()
        t.start_trace("svc")
        entry = t.start_entry_span("work")
        internal = t.start_internal_span("fail-step")
        t.finish_span(internal, "error", "crash")
        t.finish_span(entry, "error", "child failed")

        record = t.get_trace_record()
        assert record is not None
        assert record["summary"]["status"] == "failed"
        assert record["summary"]["error_count"] == 2


# ============================================================================
# Tracer — Events
# ============================================================================


class TestTracerEvents:
    def test_record_event(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("work")
        t.record_event("llm.start", {"model": "gpt-4"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "llm.start"
        assert span.events[0]["payload"]["model"] == "gpt-4"

    def test_record_event_multiple(self):
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("work")
        t.record_event("step1")
        t.record_event("step2", {"key": "val"})
        assert len(span.events) == 2

    def test_record_event_no_active_span(self):
        t = Tracer()
        t.record_event("orphan")  # should not raise


# ============================================================================
# Tracer — Trace Record
# ============================================================================


class TestTraceRecord:
    def test_no_context_returns_none(self):
        t = Tracer()
        assert t.get_trace_record() is None

    def test_record_contains_trace_id(self):
        t = Tracer()
        ctx = t.start_trace("svc")
        record = t.get_trace_record()
        assert record is not None
        assert record["trace_id"] == ctx.trace_id

    def test_record_contains_timestamp(self):
        t = Tracer()
        t.start_trace("svc")
        record = t.get_trace_record()
        assert "timestamp" in record
        assert record["timestamp"].endswith("Z")

    def test_flattened_spans_structure(self):
        t = Tracer()
        t.start_trace("svc")
        s1 = t.start_entry_span("work")
        s2 = t.start_internal_span("sub")
        t.finish_span(s2)
        t.finish_span(s1)

        record = t.get_trace_record()
        spans = record["spans"]
        assert len(spans) == 3
        for sp in spans:
            assert "id" in sp
            assert "type" in sp
            assert "name" in sp
            assert "duration_ms" in sp
            assert "status" in sp

    def test_log_does_not_raise(self, capsys):
        t = Tracer()
        t.start_trace("svc")
        t.log()
        captured = capsys.readouterr()
        assert "[Trace]" in captured.out

    def test_log_no_context(self, capsys):
        t = Tracer()
        t.log()  # should not print anything
        captured = capsys.readouterr()
        assert captured.out == ""


# ============================================================================
# Tracer — with_timeout (synchronous)
# ============================================================================


class TestWithTimeout:
    def test_success(self):
        t = Tracer()
        t.start_trace("svc")
        span = Span(id="t1", type="entry", name="test")
        result = t.with_timeout(span, 5000, lambda: 42)
        assert result == 42
        assert span.status == "success"

    def test_timeout_raises(self):
        t = Tracer()
        t.start_trace("svc")
        span = Span(id="t2", type="entry", name="slow")

        def slow_fn():
            time.sleep(10)
            return 1

        with pytest.raises(TimeoutError, match="timed out"):
            t.with_timeout(span, 10, slow_fn)


# ============================================================================
# Tracer — with_timeout_async
# ============================================================================


class TestWithTimeoutAsync:
    @pytest.mark.asyncio
    async def test_success(self):
        """with_timeout_async does NOT auto-finish span on success — caller finishes it."""
        t = Tracer()
        t.start_trace("svc")
        span = Span(id="a1", type="entry", name="async-test")

        async def work():
            return "ok"

        result = await t.with_timeout_async(span, 5000, work)
        assert result == "ok"
        # Span remains pending after success (caller calls finish_span)
        assert span.status == "pending"

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        t = Tracer()
        t.start_trace("svc")
        span = Span(id="a2", type="entry", name="async-slow")

        async def slow():
            await asyncio.sleep(10)
            return 1

        with pytest.raises(TimeoutError):
            await t.with_timeout_async(span, 10, slow)
        assert span.status == "error"
        assert "timed out" in span.error

    @pytest.mark.asyncio
    async def test_coro_raises_exception(self):
        t = Tracer()
        t.start_trace("svc")
        span = Span(id="a3", type="entry", name="async-fail")

        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await t.with_timeout_async(span, 5000, fail)
        assert span.status == "error"
        assert span.error == "boom"


# ============================================================================
# Module-level convenience functions
# ============================================================================


class TestModuleFunctions:
    def test_start_trace(self):
        ctx = start_trace("test-svc")
        assert isinstance(ctx, TraceContext)
        # Verify it used the global tracer
        assert tracer.context is ctx

    def test_with_span_and_timeout(self):
        span = Span(id="m1", type="entry", name="module-test")
        result = with_span_and_timeout(span, "module-test", 5000, lambda: 99)
        assert result == 99
        assert span.status == "success"

    def test_trace_from_headers(self):
        ctx = trace_from_headers({"X-Trace-ID": "ext-abc"}, "svc")
        assert ctx is not None
        assert ctx.trace_id == "ext-abc"

    def test_trace_from_headers_none(self):
        ctx = trace_from_headers({}, "svc")
        assert ctx is None


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_span_with_empty_children_and_events(self):
        s = Span(id="e1", type="entry", name="empty")
        assert s.children == []
        assert s.events == []

    def test_trace_context_tags_mutable(self):
        ctx = TraceContext(trace_id="t1", parent_id="", service="s")
        ctx.tags["key"] = "val"
        assert ctx.tags["key"] == "val"

    def test_from_headers_case_insensitive(self):
        ctx = Tracer.from_headers({"x-trace-id": "abc"}, "svc")
        assert ctx is not None
        assert ctx.trace_id == "abc"

    def test_multiple_active_spans_popped_correctly(self):
        """finish_span should only pop the matching span."""
        t = Tracer()
        t.start_trace("svc")
        s1 = t.start_entry_span("first")
        s2 = t.start_internal_span("second")

        # finish s1 first (inner s2 should still be on stack)
        t.finish_span(s1)
        # s2 was popped too since it was on top... wait, let me check
        # Actually finish_span pops by id, so if we finish s1 when s2 is on top,
        # it will iterate and find s1 idx, pop it. s2 remains.
        # Actually let me think... active_spans = [root, s1, s2]
        # finish_span(s1): idx = 1, pop(1) → [root, s2]
        # So s2 is still active
        assert s2 in t.active_spans

        t.finish_span(s2)
        assert s2 not in t.active_spans
        assert t.active_spans == [t.root_span]

    def test_finish_unrecognized_span(self):
        """Finishing a span not in active_spans should not raise."""
        t = Tracer()
        t.start_trace("svc")
        orphan = Span(id="orphan", type="internal", name="lost")
        t.finish_span(orphan)  # should not raise


# ============================================================================
# Async test — real timeout integration
# ============================================================================


class TestAsyncRealTimeout:
    """These tests verify actual timeout behavior with real coroutines."""

    @pytest.mark.asyncio
    async def test_timeout_with_actual_value(self):
        """with_timeout_async does NOT auto-finish span on success."""
        t = Tracer()
        t.start_trace("svc")
        span = t.start_entry_span("actual-work")

        async def fast():
            await asyncio.sleep(0.001)
            return "done"

        result = await t.with_timeout_async(span, 5000, fast)
        assert result == "done"
        assert span.status == "pending"  # caller finishes

    @pytest.mark.asyncio
    async def test_timeout_with_multiple_coros_independent(self):
        """Multiple async timeout calls — span stays pending on success."""
        t = Tracer()
        t.start_trace("svc")

        async def slowish(secs, val):
            await asyncio.sleep(secs)
            return val

        s1 = Span(id="m1", type="entry", name="fast")
        s2 = Span(id="m2", type="entry", name="slow")

        r1, r2 = await asyncio.gather(
            t.with_timeout_async(s1, 5000, lambda: slowish(0.001, "a")),
            t.with_timeout_async(s2, 5000, lambda: slowish(0.002, "b")),
        )
        assert r1 == "a"
        assert r2 == "b"
        assert s1.status == "pending"  # caller finishes
        assert s2.status == "pending"
