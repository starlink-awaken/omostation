"""OpenTelemetry instrumentation for Agora services.

Usage:
    from agora.otel import init_otel
    init_otel()  # call at app startup before any imports

Environment:
    OTEL_SERVICE_NAME     — default: "agora-hub"
    OTEL_EXPORTER_OTLP_ENDPOINT — default: "http://localhost:4318"
"""

import logging
import os

logger = logging.getLogger(__name__)


def init_otel() -> bool:
    """Initialize OpenTelemetry SDK.

    Returns True if OTel was initialized, False if packages not available.
    """
    service_name = os.getenv("OTEL_SERVICE_NAME", "agora-hub")

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,  # type: ignore[import-not-found]
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        logger.info("[OTel] SDK initialized for %s", service_name)
        return True

    except ImportError:
        logger.info("[OTel] Packages not installed — skipping")
        return False
    except Exception as exc:
        logger.warning("[OTel] Init failed: %s", exc)
        return False


class _NoOpTracer:
    """No-op tracer that safely absorbs all calls when OpenTelemetry is not installed."""

    def start_span(self, *args, **kwargs):
        return self

    def start_as_current_span(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def get_tracer(name: str = "agora"):
    """Get a tracer for the given module name.

    Falls back to a no-op tracer if OTel is not initialized.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()
