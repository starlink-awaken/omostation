"""
OpenTelemetry (OTLP) Tracing Module for eCOS v6.1 Phase 2
Provides standard setup for emitting traces to Langfuse (or any OTLP collector).
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

_TRACING_INITIALIZED = False


def setup_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracing for a service."""
    global _TRACING_INITIALIZED

    if _TRACING_INITIALIZED:
        return

    # Phase 2: Langfuse default endpoint if not overridden
    # Langfuse typically uses http://localhost:3000/api/public/otlp/v1/traces
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:3000/api/public/otlp/v1/traces")

    resource = Resource(
        attributes={
            "service.name": service_name,
            "environment": os.environ.get("ECOS_ENV", "development"),
        }
    )

    provider = TracerProvider(resource=resource)

    try:
        # We use HTTP by default for Langfuse compatibility (it supports HTTP/Protobuf well)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        _TRACING_INITIALIZED = True
        logger.info(f"[OTLP] Tracing initialized for '{service_name}', exporting to {otlp_endpoint}")
    except Exception as e:
        logger.error(f"[OTLP] Failed to initialize tracing: {e}")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for the current module."""
    if not _TRACING_INITIALIZED:
        # Optionally auto-initialize if not explicitly done
        setup_tracing("kairon-default-service")
    return trace.get_tracer(name)
