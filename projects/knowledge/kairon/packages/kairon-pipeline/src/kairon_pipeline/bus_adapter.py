"""kairon-pipeline bus adapter (R61, Month 3).

kairon-pipeline is a D-Harvest data pipeline (sources → extractors → quality
gates → downstream triggers). It already produces internal pipeline events
via its own `__main__` runner, but those events are only visible to whatever
script invoked it. By mirroring high-value events into the agora I0 bus,
downstream consumers in eCOS (omo, metaos, runtime) can react to pipeline
progress without re-running the pipeline.

Adapters here are intentionally thin: the kairon-pipeline event hook
contract is "call this function with a dict payload"; we wrap each call
in a BusEnvelope and publish via agora.bus.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _try_import_bus() -> Any:
    """Lazy import so kairon-pipeline tests can run without agora installed."""
    try:
        from bus_foundation.facade import event as bus_event  # type: ignore[reportMissingImports]

        return bus_event
    except ImportError:
        return None


def emit_event(
    event_type: str,
    source: str = "kairon-pipeline",
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> str | None:
    """Emit a kairon-pipeline event into the agora bus.

    Returns the event type, or None if agora.bus is not importable.
    """
    bus_event = _try_import_bus()
    if bus_event is None:
        logger.debug("agora_bus_unavailable_skipping_event type=%s", event_type)
        return None

    try:
        bus_event.publish(
            topic=event_type,
            payload=payload or {},
            source_uri=f"bos://capability/pipeline/{source}",
            trace_id=trace_id,
        )
        return event_type
    except Exception as e:
        logger.warning("kairon_pipeline_bus_emit_failed type=%s err=%s", event_type, e)
        return None


# Pipeline lifecycle helpers (semantically match kairon-pipeline's internal
# event types so cross-repo consumers see consistent type strings).
def emit_source_ingested(source_name: str, record_count: int, **extra: Any) -> str | None:
    return emit_event(
        event_type="kairon:source:ingested",
        payload={"source": source_name, "record_count": record_count, **extra},
    )


def emit_extraction_completed(pipeline_id: str, extractor: str, duration_ms: int, **extra: Any) -> str | None:
    return emit_event(
        event_type="kairon:extraction:completed",
        payload={"pipeline_id": pipeline_id, "extractor": extractor, "duration_ms": duration_ms, **extra},
    )


def emit_quality_gate_result(
    pipeline_id: str,
    gate: str,
    passed: bool,
    failed_records: int = 0,
    **extra: Any,
) -> str | None:
    return emit_event(
        event_type="kairon:quality_gate:result",
        payload={
            "pipeline_id": pipeline_id,
            "gate": gate,
            "passed": passed,
            "failed_records": failed_records,
            **extra,
        },
    )


def emit_downstream_dispatched(pipeline_id: str, target: str, **extra: Any) -> str | None:
    return emit_event(
        event_type="kairon:downstream:dispatched",
        payload={"pipeline_id": pipeline_id, "target": target, **extra},
    )
