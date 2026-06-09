""" "OpenTelemetry instrumentation bootstrap for the gateway.

Must be imported early to ensure auto-instrumentation hooks apply.
Checks for OTel dependencies; silently no-ops if not installed.
Adapted from agentmesh gateway instrumentation.ts.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_OTEL_INITIALIZED = False


def init_otel(
    service_name: str = "agora-gateway",
    otlp_endpoint: str = "http://localhost:4318/v1/traces",
    enabled: bool = True,
) -> bool:
    """Initialize OpenTelemetry SDK.

    Returns True if OTel was initialized, False if unavailable.
    """
    global _OTEL_INITIALIZED

    if _OTEL_INITIALIZED:
        return True

    if not enabled:
        logger.info("[OTel] Disabled by configuration")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,  # type: ignore[import-not-found]
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]

        resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            }
        )

        provider = TracerProvider(resource=resource)

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        _OTEL_INITIALIZED = True
        logger.info(
            "[OTel] SDK initialized (service: %s, endpoint: %s)", service_name, endpoint
        )
        return True

    except ImportError:
        logger.info(
            "[OTel] OpenTelemetry packages not installed — instrumentation disabled"
        )
        return False
    except Exception as e:
        logger.warning("[OTel] Failed to initialize: %s", e)
        return False


def is_otel_active() -> bool:
    """Check if OTel has been initialized."""
    return _OTEL_INITIALIZED


def get_tracer(name: str = "agora.gateway"):
    """Get an OpenTelemetry tracer instance.

    Returns a no-op tracer if OTel is not initialized.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        import opentelemetry.trace

        return opentelemetry.trace.NoOpTracer()
