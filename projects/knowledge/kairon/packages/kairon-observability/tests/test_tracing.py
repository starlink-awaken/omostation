"""Tests for kairon_observability.tracing — OTLP 追踪集成.

补 tracing 零测试债 (功能 P1). tracing 依赖 opentelemetry (外部包), 用 importorskip 防未装环境."""

import pytest

otlp = pytest.importorskip("opentelemetry")  # 整模块 skip if opentelemetry 未装

from kairon_observability.tracing import get_tracer, setup_tracing


def test_setup_tracing_idempotent():
    """setup_tracing 二次调用该 no-op (_TRACING_INITIALIZED 全局守)."""

    setup_tracing("test-service-a")
    # 二次不报错 (已初始化, 直接 return)
    setup_tracing("test-service-b")


def test_get_tracer_returns_tracer():
    t = get_tracer("test-module")
    assert t is not None


def test_tracing_module_exports():
    """tracing 模块该导出 setup_tracing + get_tracer."""
    from kairon_observability import tracing

    assert hasattr(tracing, "setup_tracing")
    assert hasattr(tracing, "get_tracer")
    assert hasattr(tracing, "_TRACING_INITIALIZED")


def test_get_tracer_auto_init():
    """get_tracer 该 auto-init 如果未 setup (kairon-default-service)."""
    t = get_tracer("auto-init-module")
    assert t is not None
