"""Tests for Agora OpenTelemetry integration."""

from __future__ import annotations

from agora.otel import _NoOpTracer, get_tracer, init_otel

# ============================================================================
# init_otel
# ============================================================================


class TestInitOtel:
    def test_init_missing_otlp_exporter(self):
        """OTLP exporter not installed — init falls back via ImportError."""
        # In the current test env, opentelemetry is installed but
        # opentelemetry-exporter-otlp-proto-http is NOT. So init_otel
        # hits an ImportError at the OTLP exporter import and returns False.
        result = init_otel()
        assert result is False

    def test_init_import_error(self, monkeypatch):
        """Simulate opentelemetry packages missing entirely."""

        def _raise_import(name, *args, **kwargs):
            raise ImportError(f"no module: {name}")

        monkeypatch.setattr("builtins.__import__", _raise_import)
        result = init_otel()
        assert result is False

    def test_init_unexpected_exception(self, monkeypatch):
        """Simulate a RuntimeError during init."""

        def _fake_import(name, *args, **kwargs):
            if name == "opentelemetry":
                raise RuntimeError("unexpected error")
            return __import__(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _fake_import)
        result = init_otel()
        assert result is False


# ============================================================================
# _NoOpTracer
# ============================================================================


class TestNoOpTracer:
    def test_start_span_returns_self(self):
        t = _NoOpTracer()
        span = t.start_span("test")
        assert span is t

    def test_start_as_current_span_returns_self(self):
        t = _NoOpTracer()
        ctx = t.start_as_current_span("test")
        assert ctx is t

    def test_any_attr_returns_callable(self):
        t = _NoOpTracer()
        result = t.some_random_method("arg", key="val")
        assert result is None

    def test_end_on_span(self):
        t = _NoOpTracer()
        result = t.end()
        assert result is None


# ============================================================================
# get_tracer
# ============================================================================


class TestGetTracer:
    def test_returns_real_tracer_when_available(self):
        tracer = get_tracer("test-module")
        assert tracer is not None

    def test_returns_noop_on_import_error(self, monkeypatch):
        def _raise_import(name, *args, **kwargs):
            raise ImportError(f"no module: {name}")

        monkeypatch.setattr("builtins.__import__", _raise_import)
        tracer = get_tracer("test-module")
        assert isinstance(tracer, _NoOpTracer)

    def test_real_tracer_can_start_span(self):
        tracer = get_tracer("test-module")
        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("key", "value")
        assert span is not None
