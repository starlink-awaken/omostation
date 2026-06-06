"""Unified Tracing - Python 实现

为 Agora 提供跨语言的 trace 追踪能力
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class TraceContext:
    """Trace 上下文"""

    trace_id: str
    parent_id: str
    service: str
    phase: str = ""
    started_at: float = field(default_factory=time.time)
    tags: dict = field(default_factory=dict)


@dataclass
class Span:
    """Span 操作"""

    id: str
    type: str  # entry, internal, exit
    name: str
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    duration_ms: float = 0.0
    status: str = "pending"  # pending, success, error
    error: str = ""
    events: list[dict] = field(default_factory=list)
    children: list[Span] = field(default_factory=list)

    def finish(self, status: str = "success", error: str = ""):
        """完成 span"""
        self.ended_at = time.time()
        self.duration_ms = (self.ended_at - self.started_at) * 1000
        self.status = status
        self.error = error


@dataclass
class TraceConfig:
    """Tracing 配置"""

    enabled: bool = True
    default_timeout_ms: int = 30000
    phase_timeout_ms: int = 300000
    model_timeout_ms: int = 60000


class Tracer:
    """Tracer 主类"""

    def __init__(self, config: TraceConfig | None = None):
        self.config = config or TraceConfig()
        self.context: TraceContext | None = None
        self.root_span: Span | None = None
        self.active_spans: list[Span] = []

    def start_trace(self, service: str, phase: str = "") -> TraceContext:
        """启动新的 trace session"""
        now = time.strftime("%Y%m%d%H%M%S")
        rand = uuid.uuid4().hex[:4]

        self.context = TraceContext(
            trace_id=f"tt-{now}-{service}{'-' + phase if phase else ''}-{rand}",
            parent_id="",
            service=service,
            phase=phase,
            started_at=time.time(),
            tags={},
        )

        self.root_span = Span(
            id=f"{self.context.trace_id}-root",
            type="entry",
            name="root",
        )
        self.active_spans = [self.root_span]
        return self.context

    def set_context(self, ctx: TraceContext):
        """设置外部传入的 context"""
        self.context = ctx
        self.root_span = Span(
            id=f"{ctx.trace_id}-resume",
            type="entry",
            name="resume",
        )
        self.active_spans = [self.root_span]

    def get_context(self) -> TraceContext | None:
        """获取当前 context"""
        return self.context

    @staticmethod
    def from_headers(headers: dict, service: str) -> TraceContext | None:
        """从 HTTP headers 解析 trace context"""
        trace_id = headers.get("x-trace-id") or headers.get("X-Trace-ID")
        if not trace_id:
            return None

        return TraceContext(
            trace_id=trace_id,
            parent_id=headers.get("x-parent-id", ""),
            service=service,
            phase=headers.get("x-trace-phase", ""),
            started_at=time.time(),
            tags={},
        )

    def to_headers(self) -> dict:
        """转换为 HTTP headers"""
        if not self.context:
            return {}
        return {
            "X-Trace-ID": self.context.trace_id,
            "X-Parent-ID": self.active_spans[-1].id if self.active_spans else "",
            "X-Trace-Phase": self.context.phase or "",
        }

    def start_entry_span(self, name: str) -> Span:
        """启动 entry span"""
        if not self.context:
            raise ValueError("No trace context. Call start_trace() first.")

        span = Span(
            id=f"{self.context.trace_id}-{name}",
            type="entry",
            name=name,
        )

        if self.root_span:
            self.root_span.children.append(span)
        self.active_spans.append(span)
        return span

    def start_internal_span(self, name: str) -> Span:
        """启动 internal span"""
        if not self.context:
            raise ValueError("No trace context. Call start_trace() first.")

        parent = self.active_spans[-1] if self.active_spans else None
        span = Span(
            id=f"{parent.id}-{name}" if parent else f"{self.context.trace_id}-{name}",
            type="internal",
            name=name,
        )

        if parent:
            parent.children.append(span)
        self.active_spans.append(span)
        return span

    def get_active_span(self) -> Span | None:
        """获取当前活跃的 span"""
        return self.active_spans[-1] if self.active_spans else None

    def finish_span(self, span: Span, status: str = "success", error: str = ""):
        """完成 span"""
        span.finish(status, error)

        # 弹出活跃栈
        try:
            idx = next(i for i, s in enumerate(self.active_spans) if s.id == span.id)
            self.active_spans.pop(idx)
        except StopIteration:
            pass

    def record_event(self, name: str, payload: Any = None):
        """记录事件到当前 span"""
        span = self.get_active_span()
        if not span:
            return

        span.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "payload": payload,
            }
        )

    def with_timeout(self, span: Span, timeout_ms: int, fn: Callable[[], T]) -> T:
        """带超时的执行包装（使用线程池，兼容 asyncio 事件循环）"""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            try:
                result = future.result(timeout=timeout_ms / 1000.0)
                return result
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Operation {span.name} timed out after {timeout_ms}ms") from None
            finally:
                self.finish_span(span)

    async def with_timeout_async(self, span: Span, timeout_ms: int, coro_fn: Callable[[], T]) -> T:
        """带超时的异步执行包装 (推荐)"""
        import asyncio

        try:
            result = await asyncio.wait_for(coro_fn(), timeout=timeout_ms / 1000.0)
            return result
        except TimeoutError:
            self.finish_span(span, "error", f"Operation {span.name} timed out")
            raise
        except Exception as e:
            self.finish_span(span, "error", str(e))
            raise

    def get_trace_record(self) -> dict | None:
        """生成 trace record"""
        if not self.context or not self.root_span:
            return None

        return {
            "trace_id": self.context.trace_id,
            "spans": self._flatten_spans(self.root_span),
            "summary": {
                "total_duration_ms": self.root_span.duration_ms,
                "status": "failed" if self._count_errors() > 0 else "success",
                "error_count": self._count_errors(),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _flatten_spans(self, root: Span) -> list[dict]:
        """递归展平 spans"""
        result = [
            {
                "id": root.id,
                "type": root.type,
                "name": root.name,
                "started_at": root.started_at,
                "ended_at": root.ended_at,
                "duration_ms": root.duration_ms,
                "status": root.status,
                "error": root.error,
                "events": root.events,
            }
        ]

        for child in root.children:
            result.extend(self._flatten_spans(child))

        return result

    def _count_errors(self) -> int:
        """递归计数错误"""

        def count(span: Span) -> int:
            cnt = 1 if span.status == "error" else 0
            for child in span.children:
                cnt += count(child)
            return cnt

        return count(self.root_span) if self.root_span else 0

    def log(self):
        """输出到 console"""
        record = self.get_trace_record()
        if record:
            print("[Trace]", record)


# 全局实例
tracer = Tracer()


# 便捷函数
def start_trace(service: str, phase: str = "") -> TraceContext:
    """启动新的 trace"""
    return tracer.start_trace(service, phase)


def with_span_and_timeout(span: Span, operation_name: str, timeout_ms: int, fn: Callable[[], T]) -> T:
    """带超时的执行包装"""
    return tracer.with_timeout(span, timeout_ms, fn)


def trace_from_headers(headers: dict, service: str) -> TraceContext | None:
    """从 headers 启动 trace"""
    return Tracer.from_headers(headers, service)
